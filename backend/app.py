# backend/app.py
import os
import tempfile
from flask import Flask, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt, JWTManager
from flask_cors import CORS
from passlib.hash import bcrypt
from sqlalchemy import func

from .models import (db, HocPhan, NguoiDung, SinhVien, LopHoc, VaiTro, NganhHoc, ChuongTrinhDaoTao, SystemConfig)
from .importer import FullDataImporter, CurriculumImporter
from .services import analytics_service
from functools import wraps


def create_app():
    """Application Factory: Tạo và cấu hình ứng dụng Flask."""
    app = Flask(__name__)
    CORS(app)  # Kích hoạt CORS cho toàn bộ ứng dụng

    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # Lấy JWT secret từ biến môi trường (an toàn hơn)
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "dev-only-override-change-this")

    db.init_app(app)
    JWTManager(app)

    # ==========================================================
    #                 API ENDPOINTS CHUNG
    # ==========================================================
    @app.route('/login', methods=['POST'])
    def login():
        data = request.get_json(silent=True)
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({"msg": "Thiếu username hoặc password"}), 400

        user = NguoiDung.query.filter_by(TenDangNhap=data['username']).first()
        if user and user.vai_tro_rel and bcrypt.verify(data['password'], user.MatKhauMaHoa):
            role = user.vai_tro_rel.TenVaiTro
            access_token = create_access_token(identity=str(user.MaNguoiDung), additional_claims={"role": role})
            return jsonify(access_token=access_token)

        return jsonify({"msg": "Sai username hoặc password"}), 401

    # ==========================================================
    #                 API ENDPOINTS CHO SINH VIÊN
    # ==========================================================
    @app.route('/api/student/data', methods=['GET'])
    @jwt_required()
    def get_student_data():
        user = db.session.get(NguoiDung, int(get_jwt_identity()))
        if not user or not user.sinh_vien_rel:
            return jsonify({"msg": "Không tìm thấy thông tin sinh viên"}), 404

        sinh_vien = user.sinh_vien_rel
        grades_list = [{
            "HocKy": kq.HocKy, "DiemHe10": kq.DiemHe10, "DiemHe4": kq.DiemHe4, "DiemChu": kq.DiemChu,
            "LaDiemCuoiCung": kq.LaDiemCuoiCung, "MaHP": kq.hoc_phan_rel.MaHP, "TenHP": kq.hoc_phan_rel.TenHP,
            "SoTinChi": kq.hoc_phan_rel.SoTinChi, "TinhDiemTichLuy": kq.hoc_phan_rel.TinhDiemTichLuy
        } for kq in sinh_vien.ket_qua_hoc_tap_rel]

        chuong_trinh_list = []
        if sinh_vien.lop_hoc and sinh_vien.lop_hoc.nganh_hoc:
            for ctdt in sinh_vien.lop_hoc.nganh_hoc.chuong_trinh_dao_tao_rel:
                tien_quyet_list = [tq.MaHP for tq in ctdt.hoc_phan_rel.mon_tien_quyet]
                chuong_trinh_list.append({
                    "MaHP": ctdt.hoc_phan_rel.MaHP, "TenHP": ctdt.hoc_phan_rel.TenHP,
                    "SoTinChi": ctdt.hoc_phan_rel.SoTinChi, "HocKyGoiY": ctdt.HocKyGoiY,
                    "TienQuyet": tien_quyet_list, "KhoiKienThuc": ctdt.hoc_phan_rel.KhoiKienThuc
                })

        lop = sinh_vien.lop_hoc
        nganh = lop.nganh_hoc if lop else None
        khoa = nganh.khoa if nganh else None

        return jsonify({
            "MaSV": sinh_vien.MaSV, "HoTen": sinh_vien.HoTen,
            "NgaySinh": sinh_vien.NgaySinh.strftime('%d/%m/%Y') if sinh_vien.NgaySinh else None,
            "Lop": lop.TenLop if lop else None, "Nganh": nganh.TenNganh if nganh else None,
            "Khoa": khoa.TenKhoa if khoa else None,
            "KetQuaHocTap": grades_list, "ChuongTrinhDaoTao": chuong_trinh_list
        })

    # ==========================================================
    #                 API ENDPOINTS CHO ADMIN
    # ==========================================================
    def admin_required(fn):
        """Decorator kiểm tra quyền Admin và giữ nguyên metadata hàm."""
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            if get_jwt().get("role") != 'Admin':
                return jsonify({"msg": "Yêu cầu quyền Admin!"}), 403
            return fn(*args, **kwargs)
        return wrapper

    @app.route('/api/admin/dashboard-analytics', methods=['GET'])
    @admin_required
    def admin_dashboard_analytics():
        try:
            # Hỗ trợ lọc theo mã ngành (?ma_nganh=CNPM)
            ma_nganh = request.args.get('ma_nganh')
            return jsonify(analytics_service.get_dashboard_analytics(ma_nganh=ma_nganh))
        except Exception as e:
            return jsonify({"msg": f"Lỗi phân tích: {str(e)}"}), 500

    @app.route('/api/admin/import-full-data', methods=['POST'])
    @admin_required
    def admin_import_full_data():
        if 'file' not in request.files or 'ma_nganh' not in request.form:
            return jsonify({"msg": "Thiếu file hoặc mã ngành"}), 400
        file, ma_nganh = request.files['file'], request.form['ma_nganh']
        if not db.session.get(NganhHoc, ma_nganh):
            return jsonify({"msg": f"Mã ngành '{ma_nganh}' không tồn tại."}), 404

        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        try:
            importer = FullDataImporter(tmp_path, ma_nganh)
            success, errors, stats = importer.run()
            if success:
                return jsonify({"msg": "Import thành công!", "errors": errors, "stats": stats}), 200
            else:
                return jsonify({"msg": "Import thất bại.", "errors": errors}), 500
        finally:
            os.remove(tmp_path)

    @app.route('/api/admin/courses', methods=['GET'])
    @admin_required
    def admin_get_all_courses():
        all_courses = HocPhan.query.order_by(HocPhan.TenHP).all()
        return jsonify([{
            "MaHP": hp.MaHP, "TenHP": hp.TenHP, "SoTinChi": hp.SoTinChi, "TinhDiemTichLuy": hp.TinhDiemTichLuy
        } for hp in all_courses])

    @app.route('/api/admin/courses/<string:ma_hp>/toggle-gpa', methods=['PUT'])
    @admin_required
    def admin_toggle_course_gpa(ma_hp):
        hp = db.session.get(HocPhan, ma_hp)
        if not hp:
            return jsonify({"msg": "Không tìm thấy học phần"}), 404
        hp.TinhDiemTichLuy = not hp.TinhDiemTichLuy
        db.session.commit()
        return jsonify({"MaHP": hp.MaHP, "TinhDiemTichLuy": hp.TinhDiemTichLuy})

    @app.route('/api/admin/classes', methods=['GET'])
    @admin_required
    def admin_get_all_classes():
        return jsonify([{"MaLop": c.MaLop, "TenLop": c.TenLop} for c in LopHoc.query.order_by(LopHoc.TenLop).all()])

    @app.route('/api/admin/majors', methods=['GET'])
    @admin_required
    def admin_get_all_majors():
        return jsonify([{"MaNganh": m.MaNganh, "TenNganh": m.TenNganh} for m in NganhHoc.query.order_by(NganhHoc.TenNganh).all()])

    @app.route('/api/admin/configs', methods=['GET'])
    @admin_required
    def admin_get_all_configs():
        return jsonify({c.ConfigKey: c.ConfigValue for c in SystemConfig.query.all()})

    @app.route('/api/admin/configs', methods=['PUT'])
    @admin_required
    def admin_update_configs():
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"msg": "Dữ liệu JSON không hợp lệ"}), 400
        for key, value in data.items():
            config = db.session.get(SystemConfig, key)
            if config:
                config.ConfigValue = str(value)
        db.session.commit()
        return jsonify({"msg": "Cập nhật cấu hình thành công!"})

    @app.route('/api/admin/import-curriculum', methods=['POST'])
    @admin_required
    def import_curriculum():
        if 'file' not in request.files or 'ma_nganh' not in request.form:
            return jsonify({"msg": "Thiếu file hoặc mã ngành"}), 400

        file = request.files['file']
        ma_nganh = request.form['ma_nganh']
        if not db.session.get(NganhHoc, ma_nganh):
            return jsonify({"msg": f"Mã ngành '{ma_nganh}' không tồn tại."}), 404

        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        try:
            importer = CurriculumImporter(tmp_path, ma_nganh)
            success, errors, stats = importer.run()
            if success:
                return jsonify({"msg": "Import Chương trình Đào tạo thành công!", "stats": stats, "errors": errors}), 200
            else:
                return jsonify({"msg": "Import thất bại.", "errors": errors}), 500
        finally:
            os.remove(tmp_path)

    return app


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # Nếu SystemConfig trống thì seed dữ liệu nền
        if db.session.query(func.count(SystemConfig.ConfigKey)).scalar() == 0:
            print("Phát hiện CSDL trống, đang chạy seed dữ liệu nền...")
            from .seed import seed_data
            seed_data(app)
            print("Seed dữ liệu nền thành công.")
    app.run(debug=True, port=5000)

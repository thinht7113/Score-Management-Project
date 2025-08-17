# backend/seed.py
# Seed “tương thích kép”: chạy được cả module lẫn script

import os
import sys

# Nếu chạy trực tiếp (python backend/seed.py) thì bổ sung sys.path để dùng absolute import
if __name__ == "__main__" and __package__ is None:
    # Thêm thư mục gốc dự án vào sys.path
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    # Sau khi thêm, có thể import qua tên package 'backend'
    from backend.app import create_app
    from backend.models import db, VaiTro, NguoiDung, Khoa, NganhHoc, SystemConfig
else:
    # Khi chạy theo module: python -m backend.seed
    from .app import create_app
    from .models import db, VaiTro, NguoiDung, Khoa, NganhHoc, SystemConfig

from passlib.hash import bcrypt


def seed_data(app=None):
    """
    Tạo dữ liệu ban đầu cho hệ thống.
    Gọi trong app context: with app.app_context(): seed_data(app)
    """
    close_app_after = False
    if app is None:
        # Cho phép gọi seed_data() trực tiếp khi chạy file
        app = create_app()
        close_app_after = True

    with app.app_context():
        print("Bắt đầu xóa và tạo lại CSDL...")
        db.drop_all()
        db.create_all()
        print("CSDL đã được làm mới.")

        # 1) Vai trò
        role_admin = VaiTro(TenVaiTro='Admin')
        role_student = VaiTro(TenVaiTro='Sinh viên')
        db.session.add_all([role_admin, role_student])
        db.session.commit()
        print(" -> Đã tạo Vai Trò 'Admin' và 'Sinh viên'.")

        # 2) Admin mặc định
        if not NguoiDung.query.filter_by(TenDangNhap='admin').first():
            hashed_password = bcrypt.hash("admin123")
            admin_user = NguoiDung(
                TenDangNhap='admin',
                MatKhauMaHoa=hashed_password,
                Email='admin@example.com',
                vai_tro_rel=role_admin
            )
            db.session.add(admin_user)
            print(" -> Đã tạo Admin: username='admin', password='admin123'.")

        # 3) Khoa/Ngành mẫu
        khoa_cntt = Khoa(MaKhoa='CNTT', TenKhoa='Công nghệ Thông tin')
        db.session.add(khoa_cntt)
        db.session.commit()
        nganh_cntt = NganhHoc(MaNganh='CNTT', TenNganh='Công nghệ thông tin', TongSoTinChi=140, khoa=khoa_cntt)
        nganh_cnpm = NganhHoc(MaNganh='CNPM', TenNganh='Công nghệ Phần mềm', TongSoTinChi=160, khoa=khoa_cntt)
        db.session.add_all([nganh_cntt, nganh_cnpm])

        # 4) SystemConfig mặc định
        configs = [
            SystemConfig(ConfigKey='GPA_GIOI_THRESHOLD', ConfigValue='3.2', Description='Ngưỡng GPA loại Giỏi'),
            SystemConfig(ConfigKey='GPA_KHA_THRESHOLD', ConfigValue='2.5', Description='Ngưỡng GPA loại Khá'),
            SystemConfig(ConfigKey='GPA_TRUNGBINH_THRESHOLD', ConfigValue='2.0', Description='Ngưỡng GPA loại TB'),
            SystemConfig(ConfigKey='TINCHI_NO_CANHCAO_THRESHOLD', ConfigValue='8', Description='TC nợ để cảnh cáo'),
            SystemConfig(ConfigKey='IMPROVE_CREDIT_LIMIT_PERCENT', ConfigValue='0.05', Description='% TC được cải thiện'),
        ]
        db.session.add_all(configs)

        db.session.commit()
        print("\n===> TẠO DỮ LIỆU NỀN TẢNG THÀNH CÔNG! <===")

    if close_app_after:
        # không bắt buộc, chỉ để nhấn mạnh vòng đời app khi chạy trực tiếp
        pass


if __name__ == '__main__':
    # Chạy trực tiếp file seed
    # - Khi chạy theo module: python -m backend.seed thì __name__ = 'backend.seed' (block này không chạy)
    app = create_app()
    seed_data(app)

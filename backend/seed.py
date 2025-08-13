# backend/seed.py
# (Phiên bản tinh gọn, chỉ tạo dữ liệu nền tảng)

from app import create_app
from models import db, VaiTro, NguoiDung, Khoa, NganhHoc, SystemConfig
from passlib.hash import bcrypt

app = create_app()


def seed_data():
    """
    Tạo dữ liệu ban đầu cho hệ thống.
    Hàm này chỉ nên được chạy một lần khi thiết lập hệ thống mới.
    """
    with app.app_context():
        print("Bắt đầu xóa và tạo lại CSDL...")
        db.drop_all()
        db.create_all()
        print("CSDL đã được làm mới.")

        # --- 1. Tạo các Vai Trò cố định ---
        print("Đang tạo các Vai Trò...")
        role_admin = VaiTro(TenVaiTro='Admin')
        role_student = VaiTro(TenVaiTro='Sinh viên')
        db.session.add_all([role_admin, role_student])
        db.session.commit()
        print(" -> Đã tạo Vai Trò 'Admin' và 'Sinh viên'.")

        # --- 2. Tạo một tài khoản Admin mặc định ---
        print("Đang tạo tài khoản Admin mặc định...")
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

        # --- 3. Tạo dữ liệu nền tảng cho Khoa và Ngành ---
        print("Đang tạo Khoa và Ngành mẫu...")
        khoa_cntt = Khoa(MaKhoa='CNTT', TenKhoa='Công nghệ Thông tin')
        db.session.add(khoa_cntt)
        db.session.commit()

        nganh_cntt = NganhHoc(MaNganh='CNTT', TenNganh='Công nghệ thông tin', TongSoTinChi=140, khoa=khoa_cntt)
        nganh_cnpm = NganhHoc(MaNganh='CNPM', TenNganh='Công nghệ Phần mềm', TongSoTinChi=160, khoa=khoa_cntt)
        db.session.add_all([nganh_cntt, nganh_cnpm])
        print(" -> Đã tạo Khoa 'CNTT' và các ngành 'CNTT', 'CNPM'.")

        # --- 4. Thiết lập Cấu hình hệ thống mặc định ---
        print("Đang thiết lập Cấu hình hệ thống...")
        configs = [
            SystemConfig(ConfigKey='GPA_GIOI_THRESHOLD', ConfigValue='3.2',
                         Description='Ngưỡng GPA tối thiểu để xếp loại Giỏi'),
            SystemConfig(ConfigKey='GPA_KHA_THRESHOLD', ConfigValue='2.5',
                         Description='Ngưỡng GPA tối thiểu để xếp loại Khá'),
            SystemConfig(ConfigKey='GPA_TRUNGBINH_THRESHOLD', ConfigValue='2.0',
                         Description='Ngưỡng GPA tối thiểu để xếp loại Trung bình'),
            SystemConfig(ConfigKey='TINCHI_NO_CANHCAO_THRESHOLD', ConfigValue='8',
                         Description='Số tín chỉ nợ tối thiểu để bị cảnh cáo học vụ'),
            SystemConfig(ConfigKey='IMPROVE_CREDIT_LIMIT_PERCENT', ConfigValue='0.05',
                         Description='Tỷ lệ % tín chỉ được cải thiện cho SV từ loại Giỏi trở lên')
        ]
        db.session.add_all(configs)
        print(" -> Đã tạo các cấu hình mặc định.")

        db.session.commit()
        print("\n===> TẠO DỮ LIỆU NỀN TẢNG THÀNH CÔNG! <===")


if __name__ == '__main__':
    seed_data()
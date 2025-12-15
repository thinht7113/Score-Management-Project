# backend/seed.py
from __future__ import annotations


import os

from passlib.hash import bcrypt

from .app import create_app
from .models import (
    db,
    VaiTro, NguoiDung,
    SystemConfig,
    NganhHoc, LopHoc, HocPhan,
    WarningRule,
    SinhVien,
)


def ensure_role(name: str) -> int:
    r = VaiTro.query.filter(VaiTro.TenVaiTro.ilike(name)).first()
    if r:
        return r.MaVaiTro
    r = VaiTro(TenVaiTro=name)
    db.session.add(r); db.session.commit()
    return r.MaVaiTro

def ensure_user(username: str, role_name: str, email: str, password: str) -> int:
    u = NguoiDung.query.filter_by(TenDangNhap=username).first()
    role_id = ensure_role(role_name)
    if u:
        if u.MaVaiTro != role_id:
            u.MaVaiTro = role_id
            db.session.commit()
        return u.MaNguoiDung
    u = NguoiDung(
        TenDangNhap=username,
        MatKhauMaHoa=bcrypt.hash(password),
        Email=email,
        TrangThai="Hoạt động",
        MaVaiTro=role_id,
    )
    db.session.add(u); db.session.commit()
    return u.MaNguoiDung

def ensure_config(key: str, value: str):
    row = db.session.get(SystemConfig, key)
    if row:
        return
    db.session.add(SystemConfig(ConfigKey=key, ConfigValue=str(value)))
    db.session.commit()

def ensure_major(code: str, name: str):
    r = db.session.get(NganhHoc, code)
    if r:
        return
    db.session.add(NganhHoc(MaNganh=code, TenNganh=name)); db.session.commit()

def ensure_class(code: str, name: str, ma_nganh: str | None):
    r = db.session.get(LopHoc, code)
    if r:
        return
    db.session.add(LopHoc(MaLop=code, TenLop=name, MaNganh=ma_nganh)); db.session.commit()

def ensure_course(mahp: str, tenhp: str, stc: int, gpa: bool = True):
    r = db.session.get(HocPhan, mahp)
    if r:
        return
    db.session.add(HocPhan(MaHP=mahp, TenHP=tenhp, SoTinChi=stc, TinhDiemTichLuy=gpa)); db.session.commit()

def ensure_warning_rule(code: str, name: str, threshold: float, active: bool = True):
    r = WarningRule.query.filter_by(Code=code).first()
    if r:
        changed = False
        if r.Threshold != float(threshold):
            r.Threshold = float(threshold); changed = True
        if r.Active != bool(active):
            r.Active = bool(active); changed = True
        if changed:
            db.session.commit()
        return
    db.session.add(WarningRule(Code=code, Name=name, Threshold=float(threshold), Active=active, Desc=None))
    db.session.commit()

def ensure_student(masv: str, hoten: str, malop: str | None, user_id: int | None):
    sv = db.session.get(SinhVien, masv)
    if sv:
        return
    db.session.add(SinhVien(MaSV=masv, HoTen=hoten, MaLop=malop, MaNguoiDung=user_id))
    db.session.commit()


def run_seed():
    app = create_app()
    with app.app_context():
        db.create_all()

        ensure_role("Admin")
        ensure_role("Cán bộ đào tạo")
        ensure_role("Giảng viên")
        ensure_role("Sinh viên")

        admin_user = os.getenv("SEED_ADMIN_USER", "admin")
        admin_pass = os.getenv("SEED_ADMIN_PASS", "admin123")
        admin_mail = os.getenv("SEED_ADMIN_MAIL", "admin@vui.edu.vn")
        ensure_user(admin_user, "Admin", admin_mail, admin_pass)

        defaults = {
            "EMAIL_DOMAIN": "vui.edu.vn",
            "DEFAULT_MAJOR": "CNTT",
            "GPA_GIOI_THRESHOLD": "3.2",
            "GPA_KHA_THRESHOLD": "2.5",
            "GPA_TRUNGBINH_THRESHOLD": "2.0",
            "TINCHI_NO_CANHCAO_THRESHOLD": "10",
            "RETAKE_POLICY_DEFAULT": "keep-latest",
        }
        for k, v in defaults.items():
            ensure_config(k, v)

        ensure_major("CNTT", "Công nghệ thông tin")
        ensure_class("TT1D22", "TT1D22", "CNTT")


        ensure_warning_rule("GPA_BELOW", "GPA dưới ngưỡng", float(defaults["GPA_TRUNGBINH_THRESHOLD"]))
        ensure_warning_rule("DEBT_OVER", "Nợ tín chỉ vượt ngưỡng", float(defaults["TINCHI_NO_CANHCAO_THRESHOLD"]))


        print("✅ Seed hoàn tất:")
        print(f"  - Admin: {admin_user} / {admin_pass}")
        print("  - Configs:", ", ".join(defaults.keys()))
        print("  - Mẫu: 1 ngành, 1 lớp, 4 học phần, 1 sinh viên")

if __name__ == "__main__":
    run_seed()

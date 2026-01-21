# backend/utils_import/db_utils.py
import json
from datetime import datetime
from flask import request
from flask_jwt_extended import get_jwt_identity
from passlib.hash import bcrypt
from ..models import db, ImportLog, NguoiDung, VaiTro

def audit_import(*, endpoint: str, affected: str, summary: dict, filename: str = None):
    try:
        actor = get_jwt_identity() or ""
    except Exception:
        actor = ""
    try:
        log = ImportLog(
            When=datetime.utcnow(),
            Actor=str(actor),
            Endpoint=endpoint,
            Params=json.dumps(request.args.to_dict(), ensure_ascii=False),
            Filename=filename,
            Summary=json.dumps(summary, ensure_ascii=False),
            AffectedTable=affected,
            InsertedIds=None,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()

def ensure_role_sinhvien_id():
    r = db.session.query(VaiTro).filter(VaiTro.TenVaiTro.in_(["SinhVien", "Sinh Viên", "student"])).first()
    if not r:
        r = VaiTro(TenVaiTro="SinhVien")
        db.session.add(r)
        db.session.flush()
    return r.MaVaiTro

def ensure_student_user(masv: str, email_domain: str) -> int:
    u = NguoiDung.query.filter_by(TenDangNhap=masv).first()
    if u:
        return u.MaNguoiDung

    role_id = ensure_role_sinhvien_id()
    u = NguoiDung(
        TenDangNhap=masv,
        MatKhauMaHoa=bcrypt.hash(masv),
        Email=f"{masv}@{email_domain}",
        TrangThai="Hoạt động",
        MaVaiTro=role_id,
    )
    db.session.add(u)
    db.session.flush()
    return u.MaNguoiDung

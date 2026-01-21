from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from ..models import db, NguoiDung, SinhVien, LopHoc, NganhHoc, HocPhan, KetQuaHocTap, ChuongTrinhDaoTao, Khoa
from ..utils import get_actor_id

bp = Blueprint("student", __name__)

@bp.get("/api/student/data")
@jwt_required()
def student_data():
    uid = get_actor_id()
    u = db.session.get(NguoiDung, uid) if uid else None

    sv = None
    try:
        if u and hasattr(u, "sinh_vien_rel") and u.sinh_vien_rel:
            sv = u.sinh_vien_rel
    except Exception:
        pass
    if not sv and hasattr(SinhVien, "MaNguoiDung"):
        try:
            sv = db.session.query(SinhVien).filter_by(MaNguoiDung=uid).first()
        except Exception:
            sv = None
    if not sv and u and getattr(u, "TenDangNhap", None):
        try:
            sv = db.session.get(SinhVien, u.TenDangNhap)
        except Exception:
            sv = None
    if not sv:
        return jsonify({"msg": "Không tìm thấy thông tin sinh viên"}), 404

    masv = getattr(sv, "MaSV", None) or getattr(sv, "id", None)
    ma_lop = getattr(sv, "MaLop", None) or getattr(sv, "Lop", None)

    # Eager load LopHoc and NganhHoc
    lop = db.session.get(LopHoc, ma_lop) if ma_lop else None
    nganh = db.session.get(NganhHoc, getattr(lop, "MaNganh", None)) if lop else None

    # Optimized: Eager load HocPhan for KetQuaHocTap
    kq_list = db.session.query(KetQuaHocTap)\
        .options(joinedload(KetQuaHocTap.hoc_phan_rel))\
        .filter_by(MaSV=masv).all()

    def _row(kq):
        # hp is already loaded
        hp = kq.hoc_phan_rel
        return {
            "HocKy": getattr(kq, "HocKy", None),
            "MaHP": kq.MaHP,
            "TenHP": getattr(hp, "TenHP", None) or getattr(kq, "TenHP", None),
            "SoTinChi": getattr(hp, "SoTinChi", None) or getattr(kq, "SoTinChi", 0),
            "DiemHe10": getattr(kq, "DiemHe10", None),
            "DiemHe4": getattr(kq, "DiemHe4", None),
            "DiemChu": getattr(kq, "DiemChu", None),
            "TinhDiemTichLuy": (bool(getattr(hp, "TinhDiemTichLuy", True)) if hp
                                else bool(getattr(kq, "TinhDiemTichLuy", True))),
            "LaDiemCuoiCung": getattr(kq, "LaDiemCuoiCung", None),
        }

    items = [_row(kq) for kq in kq_list]

    def _digits_to_int(v):
        if v is None: return None
        s = str(v).strip()
        dg = "".join(ch for ch in s if ch.isdigit())
        return int(dg) if dg else None

    plan = []

    CTDT = ChuongTrinhDaoTao
    if CTDT and hasattr(CTDT, "MaNganh") and hasattr(CTDT, "HocKy"):
        q = db.session.query(CTDT).options(joinedload(CTDT.hoc_phan_rel))
        rows = []
        ma_nganh = getattr(lop, "MaNganh", None)
        if ma_nganh:
            rows = (q.filter(CTDT.MaNganh == ma_nganh)
                    .order_by(CTDT.HocKy, CTDT.MaHP).all())
        if not rows and ma_nganh:
            prefix = str(ma_nganh)[:5]
            rows = (q.filter(CTDT.MaNganh.like(f"{prefix}%"))
                    .order_by(CTDT.HocKy, CTDT.MaHP).all())
        if not rows:
            rows = q.order_by(CTDT.HocKy, CTDT.MaHP).all()

        for r in rows:
            hp = r.hoc_phan_rel
            plan.append({
                "HocKy": _digits_to_int(getattr(r, "HocKy", None)),
                "MaHP": getattr(r, "MaHP", None),
                "TenHP": getattr(hp, "TenHP", None) if hp else None,
                "SoTinChi": (getattr(hp, "SoTinChi", 0) if hp else 0) or getattr(r, "SoTinChi", 0),
            })

    if not plan:
        hk_map_kq = dict(db.session.query(
            KetQuaHocTap.MaHP, func.min(KetQuaHocTap.HocKy)
        ).group_by(KetQuaHocTap.MaHP).all())

        hps = (db.session.query(HocPhan)
               .filter(or_(HocPhan.TinhDiemTichLuy == True, HocPhan.TinhDiemTichLuy.is_(None)))
               .order_by(HocPhan.MaHP).all())

        for hp in hps:
            hk = hk_map_kq.get(hp.MaHP)
            hk_int = _digits_to_int(hk)
            plan.append({
                "HocKy": hk_int,
                "MaHP": hp.MaHP,
                "TenHP": hp.TenHP,
                "SoTinChi": hp.SoTinChi or 0,
            })

    khoa_name = None
    try:
        k = getattr(nganh, "khoa", None)
        if k:
            khoa_name = getattr(k, "TenKhoa", None) or getattr(k, "Name", None)
    except Exception:
        pass
    if not khoa_name:
        try:
            mk = getattr(nganh, "MaKhoa", None)
            if mk:
                k = db.session.get(Khoa, mk)
                if k:
                    khoa_name = getattr(k, "TenKhoa", None) or getattr(k, "Name", None)
        except Exception:
            pass

    email = getattr(u, "Email", None)
    if not email:
        try:
            email = getattr(getattr(sv, "nguoi_dung_rel", None), "Email", None)
        except Exception:
            email = None

    def _hk_key(x):
        try:
            return int(x.get("HocKy") or 0)
        except:
            return 0

    plan.sort(key=lambda x: (_hk_key(x), str(x.get("MaHP") or "")))

    return jsonify({
        "MaSV": masv,
        "HoTen": getattr(sv, "HoTen", None),
        "NgaySinh": (getattr(sv, "NgaySinh", None).strftime("%d/%m/%Y")if getattr(sv, "NgaySinh", None) else None),
        "Lop": getattr(lop, "TenLop", None) or ma_lop,
        "Nganh": getattr(nganh, "TenNganh", None),
        "Khoa": khoa_name,
        "Email":email,
        "KetQuaHocTap": items,
        "ChuongTrinhDaoTao": plan
    })

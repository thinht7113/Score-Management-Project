# -*- coding: utf-8 -*-


from __future__ import annotations
from functools import wraps
from io import BytesIO
from typing import Any, Dict

import sqlalchemy as sa
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from passlib.hash import bcrypt

from .models import (
    db,
    SinhVien, HocPhan, KetQuaHocTap,
    NganhHoc, LopHoc,
    NguoiDung, SystemConfig,
    WarningRule, WarningCase,
    ImportLog,
)

try:
    from . import importer as _importer
except Exception:
    _importer = None

bp = Blueprint("admin_crud", __name__)
crud_bp = bp

def roles_required(*roles: str):
    def deco(fn):
        @wraps(fn)
        @jwt_required()
        def wrapped(*args, **kwargs):
            role = (get_jwt() or {}).get("role")
            if roles and role not in roles:
                return jsonify({"msg": "Forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapped
    return deco

def ok(data: Any = None, **kw):
    res = {"ok": True}
    if data is not None:
        res["data"] = data
    res.update(kw)
    return jsonify(res)

def bad(msg: str, code: int = 400):
    return jsonify({"ok": False, "message": msg}), code

def json_body() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}

def _email_domain() -> str:
    row = db.session.get(SystemConfig, "EMAIL_DOMAIN")
    return (row.ConfigValue if row else "vui.edu.vn")

@bp.get("/api/auth/me")
@jwt_required()
def auth_me():
    claims = get_jwt() or {}
    ident = get_jwt_identity()
    return jsonify({
        "email": claims.get("email") or ident,
        "role": claims.get("role"),
        "sub": ident,
        "user": {
            "email": claims.get("email") or ident,
            "role": claims.get("role"),
            "username": claims.get("username") or claims.get("email") or ident
        }
    })

@bp.get("/api/admin/dashboard-analytics")
@jwt_required()
def dashboard_analytics():
    total_students = db.session.scalar(sa.select(sa.func.count()).select_from(SinhVien)) or 0
    total_courses  = db.session.scalar(sa.select(sa.func.count()).select_from(HocPhan)) or 0

    total_kq = db.session.scalar(sa.select(sa.func.count()).select_from(KetQuaHocTap)) or 0
    pass_kq = 0
    conds = [
        getattr(KetQuaHocTap, "DiemHe10") >= 4.0
    ]
    if hasattr(KetQuaHocTap, "KetQua"):
        conds.append(getattr(KetQuaHocTap, "KetQua").in_(["Đạt", "Pass"]))
    if hasattr(KetQuaHocTap, "DiemChu"):
        conds.append(getattr(KetQuaHocTap, "DiemChu").in_(["A","B","C","D","P"]))
    pass_kq = db.session.scalar(
        sa.select(sa.func.count()).select_from(KetQuaHocTap).where(sa.or_(*conds))
    ) or 0

    return jsonify({"kpi": {
        "total_students": int(total_students),
        "total_courses": int(total_courses),
        "pass_rate": round((pass_kq/total_kq) if total_kq else 0.0, 4),
    }})

@bp.get("/api/admin/users")
@jwt_required()
def users_list():
    rows = db.session.query(NguoiDung).all()
    items = []
    for u in rows:
        role = getattr(getattr(u, "vai_tro_rel", None), "TenVaiTro", None)
        items.append({"TenDangNhap": u.TenDangNhap, "Email": u.Email, "TenVaiTro": role})
    return jsonify({"items": items})

@bp.get("/api/admin/majors")
@jwt_required()
def majors_list():
    rows = NganhHoc.query.order_by(NganhHoc.MaNganh).all()
    return jsonify({"items": [{"MaNganh": x.MaNganh, "TenNganh": x.TenNganh} for x in rows]})

@bp.post("/api/admin/majors")
@roles_required("Admin")
def majors_create():
    data = json_body()
    it = NganhHoc(MaNganh=data.get("MaNganh"), TenNganh=data.get("TenNganh"))
    db.session.add(it)
    try:
        db.session.commit()
        return ok({"MaNganh": it.MaNganh, "TenNganh": it.TenNganh})
    except Exception:
        db.session.rollback()
        return bad("Mã ngành đã tồn tại")

@bp.put("/api/admin/majors/<ma>")
@roles_required("Admin")
def majors_update(ma):
    it = NganhHoc.query.get(ma)
    if not it: return bad("Không tìm thấy ngành", 404)
    it.TenNganh = json_body().get("TenNganh", it.TenNganh)
    db.session.commit(); return ok()

@bp.delete("/api/admin/majors/<ma>")
@roles_required("Admin")
def majors_delete(ma):
    it = NganhHoc.query.get(ma)
    if not it: return bad("Không tìm thấy ngành", 404)
    db.session.delete(it); db.session.commit(); return ok()

@bp.get("/api/admin/classes")
@jwt_required()
def classes_list():
    rows = LopHoc.query.order_by(LopHoc.MaLop).all()
    return jsonify({"items": [{"MaLop": x.MaLop, "TenLop": x.TenLop} for x in rows]})

@bp.post("/api/admin/classes")
@roles_required("Admin")
def classes_create():
    data = json_body()
    it = LopHoc(MaLop=data.get("MaLop"), TenLop=data.get("TenLop") or data.get("Ten"))
    db.session.add(it)
    try:
        db.session.commit(); return ok()
    except Exception:
        db.session.rollback(); return bad("Mã lớp đã tồn tại")

@bp.put("/api/admin/classes/<ma>")
@roles_required("Admin")
def classes_update(ma):
    it = LopHoc.query.get(ma)
    if not it:
        return bad("Không tìm thấy lớp", 404)

    d = json_body()
    new_name = (d.get("TenLop") or it.TenLop or "").strip()

    if new_name == (it.TenLop or "").strip():
        return ok({"message": "Không có thay đổi"})

    it.TenLop = new_name

    import time
    tries = 3
    for i in range(tries):
        try:
            db.session.commit()
            return ok()
        except sa.exc.OperationalError as e:
            msg = str(e).lower()
            db.session.rollback()
            if "database is locked" in msg and i < tries - 1:
                time.sleep(0.25 * (2 ** i))  # backoff: 250ms, 500ms
                continue
            return bad("CSDL đang bận (database is locked). Thử lại sau giây lát.", 503)

@bp.delete("/api/admin/classes/<ma>")
@roles_required("Admin")
def classes_delete(ma):
    it = LopHoc.query.get(ma)
    if not it: return bad("Không tìm thấy lớp", 404)
    db.session.delete(it); db.session.commit(); return ok()

@bp.get("/api/admin/courses")
@jwt_required()
def courses_list():
    rows = HocPhan.query.order_by(HocPhan.MaHP).all()
    items = [{
        "MaHP": x.MaHP,
        "TenHP": x.TenHP,
        "SoTinChi": int(x.SoTinChi or 0),
        "TinhDiemTichLuy": bool(x.TinhDiemTichLuy),
    } for x in rows]
    return jsonify({"items": items})

@bp.post("/api/admin/courses")
@roles_required("Admin")
def courses_create():
    d = json_body()
    it = HocPhan(MaHP=d.get("MaHP"), TenHP=d.get("TenHP"),
                 SoTinChi=int(d.get("SoTinChi") or 0),
                 TinhDiemTichLuy=bool(d.get("TinhDiemTichLuy")) if "TinhDiemTichLuy" in d else True)
    db.session.add(it)
    try:
        db.session.commit(); return ok()
    except Exception:
        db.session.rollback(); return bad("Mã học phần đã tồn tại")

@bp.put("/api/admin/courses/<ma>")
@roles_required("Admin")
def courses_update(ma):
    it = HocPhan.query.get(ma)
    if not it: return bad("Không tìm thấy học phần", 404)
    d = json_body()
    if "TenHP" in d: it.TenHP = d["TenHP"]
    if "SoTinChi" in d: it.SoTinChi = int(d["SoTinChi"] or 0)
    if "TinhDiemTichLuy" in d: it.TinhDiemTichLuy = bool(d["TinhDiemTichLuy"])
    db.session.commit(); return ok()

@bp.delete("/api/admin/courses/<ma>")
@roles_required("Admin")
def courses_delete(ma):
    it = HocPhan.query.get(ma)
    if not it: return bad("Không tìm thấy học phần", 404)
    db.session.delete(it); db.session.commit(); return ok()

def _sv_dict(sv) -> Dict[str, Any]:
    return {
        "MaSV": sv.MaSV,
        "HoTen": sv.HoTen,
        "Lop": getattr(sv, "Lop", None) or getattr(sv, "MaLop", None),
        "Email": getattr(getattr(sv, "nguoi_dung_rel", None), "Email", None)
    }

@bp.get("/api/admin/students")
@jwt_required()
def students_list():
    qstr = (request.args.get("q") or "").strip()
    lop  = (request.args.get("lop") or "").strip()
    page = max(int(request.args.get("page", 1)), 1)
    limit= max(min(int(request.args.get("page_size", 50)), 200), 1)

    q = db.session.query(SinhVien)
    if lop:
        if hasattr(SinhVien, "Lop"):
            q = q.filter(SinhVien.Lop == lop)
        else:
            q = q.filter(SinhVien.MaLop == lop)
    if qstr:
        conds = []
        conds.append(SinhVien.MaSV.ilike(f"%{qstr}%"))
        conds.append(SinhVien.HoTen.ilike(f"%{qstr}%"))
        q = q.filter(sa.or_(*conds))

    total = q.count()
    q = q.order_by(SinhVien.MaSV).offset((page-1)*limit).limit(limit)
    items = [_sv_dict(x) for x in q.all()]
    return jsonify({"items": items, "total": total, "page": page, "page_size": limit})

@bp.get("/api/admin/students/<masv>")
@jwt_required()
def students_get(masv):
    sv = db.session.get(SinhVien, masv)
    if not sv: return bad("Không tìm thấy sinh viên", 404)
    return jsonify(_sv_dict(sv))

@bp.get("/api/admin/students/<masv>/transcript")
@jwt_required()
def students_transcript(masv):
    q = db.session.query(KetQuaHocTap).filter(KetQuaHocTap.MaSV == masv)
    rows = [{
        "MaHP": r.MaHP, "TenHP": getattr(r.hoc_phan_rel, "TenHP", None),
        "SoTinChi": getattr(r.hoc_phan_rel, "SoTinChi", None),
        "DiemHe10": r.DiemHe10, "DiemChu": r.DiemChu, "KetQua": getattr(r, "KetQua", None)
    } for r in q.all()]
    return jsonify({"items": rows})

@bp.post("/api/admin/students")
@roles_required("Admin")
def students_create():
    d = json_body()
    masv = (d.get("MaSV") or "").strip()
    if not masv: return bad("Thiếu MaSV")

    u = NguoiDung.query.filter_by(TenDangNhap=masv).first()
    if not u:
        u = NguoiDung(
            TenDangNhap=masv,
            MatKhauMaHoa=bcrypt.hash(masv),
            Email=f"{masv}@{_email_domain()}",
            TrangThai="Hoạt động",
            MaVaiTro=None
        )
        db.session.add(u); db.session.flush()

    sv = SinhVien(MaSV=masv, HoTen=d.get("HoTen"), MaLop=d.get("Lop") or d.get("MaLop"), MaNguoiDung=u.MaNguoiDung)
    db.session.add(sv)
    try:
        db.session.commit(); return ok()
    except Exception as e:
        db.session.rollback(); return bad(f"Lỗi tạo sinh viên: {e}")

@bp.put("/api/admin/students/<masv>")
@roles_required("Admin")
def students_update(masv):
    sv = db.session.get(SinhVien, masv)
    if not sv: return bad("Không tìm thấy sinh viên", 404)
    d = json_body()
    if "HoTen" in d: sv.HoTen = d["HoTen"]
    if "Lop" in d and hasattr(sv, "Lop"): sv.Lop = d["Lop"]
    if "MaLop" in d and hasattr(sv, "MaLop"): sv.MaLop = d["MaLop"]
    db.session.commit(); return ok()

@bp.delete("/api/admin/students/<masv>")
@roles_required("Admin")
def students_delete(masv):
    sv = db.session.get(SinhVien, masv)
    if not sv: return bad("Không tìm thấy sinh viên", 404)
    db.session.delete(sv); db.session.commit(); return ok()

@bp.get("/api/admin/configs")
@jwt_required()
def configs_get():
    rows = db.session.query(SystemConfig).all()
    values = {x.ConfigKey: x.ConfigValue for x in rows}
    meta   = {x.ConfigKey: x.Description or "" for x in rows}
    return jsonify({"values": values, "meta": meta})

@bp.put("/api/admin/configs")
@roles_required("Admin")
def configs_put():
    values = (json_body().get("values") or {})
    for k, v in values.items():
        row = db.session.get(SystemConfig, k)
        if not row:
            db.session.add(SystemConfig(ConfigKey=k, ConfigValue=str(v)))
        else:
            row.ConfigValue = str(v)
    db.session.commit(); return ok()

@bp.get("/api/admin/warning/rules")
@jwt_required()
def warning_rules():
    rows = db.session.query(WarningRule).order_by(WarningRule.Id).all()
    items = [{"Id": r.Id, "Code": r.Code, "Expr": getattr(r, "Expr", None), "Name": r.Name, "Threshold": r.Threshold} for r in rows]
    return jsonify(items)

@bp.post("/api/admin/warning/rules")
@roles_required("Admin")
def warning_rules_create():
    d = json_body()
    it = WarningRule(Code=d.get("Code"), Name=d.get("Name") or d.get("Code"), Threshold=d.get("Threshold") or 0.0)
    db.session.add(it); db.session.commit(); return ok()

@bp.get("/api/admin/warning/cases")
@jwt_required()
def warning_cases():
    # Join with WarningRule to get code/name
    rows = db.session.query(WarningCase, WarningRule).join(WarningRule, WarningCase.RuleId == WarningRule.Id).order_by(WarningCase.Id.desc()).limit(200).all()
    items = []
    for c, r in rows:
        items.append({
            "Id": c.Id,
            "MaSV": c.MaSV,
            "Lop": getattr(c, "Lop", None) or getattr(c, "MaLop", None), # Model might not have Lop, check if needed
            "RuleCode": r.Code,
            "RuleName": r.Name,
            "Threshold": r.Threshold,
            "Value": c.Value,
            "At": c.CreatedAt.strftime("%Y-%m-%d %H:%M") if c.CreatedAt else ""
        })
    return jsonify({"items": items})

@bp.post("/api/admin/warning/scan")
@roles_required("Admin")
def warning_scan_run():
    from .warning_scan import scan_all_warnings
    try:
        res = scan_all_warnings()
        return jsonify(res)
    except Exception as e:
        return bad(f"Lỗi quét cảnh báo: {e}")

def _import_resp(summary=None, preview=None, warnings=None):
    return jsonify({
        "summary": summary or {"total_rows": 0, "created": 0, "updated": 0, "skipped": 0, "warnings": (warnings or [])},
        "preview": preview or [],
        "warnings": warnings or []
    })

@bp.post("/api/admin/import/grades")
@roles_required("Admin")
def import_grades():
    if _importer and hasattr(_importer, "import_grades"):
        return _importer.import_grades(  # type: ignore
            preview=(request.args.get("preview", "1") == "1"),
            allow_update=(request.args.get("allow_update", "0") == "1"),
            hoc_ky_default=request.args.get("hocky"),
            retake_policy=request.args.get("retake_policy") or "keep-latest",
        )
    return _import_resp()

@bp.post("/api/admin/import/class-roster")
@roles_required("Admin")
def import_roster():
    if _importer and hasattr(_importer, "import_class_roster"):
        return _importer.import_class_roster(  # type: ignore
            preview=(request.args.get("preview", "1") == "1"),
            allow_update=(request.args.get("allow_update", "0") == "1"),
        )
    return _import_resp()

@bp.post("/api/admin/import/curriculum")
@roles_required("Admin")
def import_curriculum():
    if _importer and hasattr(_importer, "import_curriculum"):
        return _importer.import_curriculum(  # type: ignore
            preview=(request.args.get("preview", "1") == "1")
        )
    return _import_resp()

@bp.get("/api/admin/templates/roster.csv")
@jwt_required()
def template_roster_csv():
    buf = BytesIO()
    buf.write("MaSV,HoTen,Lop,Email\r\n".encode("utf-8"))
    buf.write("22A4802010001,Nguyen Van A,TT1D22,a@vui.edu.vn\r\n".encode("utf-8"))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="roster_template.csv", mimetype="text/csv")

@bp.get("/api/admin/templates/grades.xlsx")
@jwt_required()
def template_grades_xlsx():
    buf = BytesIO()
    buf.write("MaSV,MaHP,TenHP,SoTinChi,DiemHe10,KetQua\r\n".encode("utf-8"))
    buf.write("22A4802010001,21TT71583,Cau truc DL&GT,3,8.0,Đạt\r\n".encode("utf-8"))
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="grades_template.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@bp.get("/api/admin/import/logs")
@jwt_required()
def import_logs():
    rows = db.session.query(ImportLog).order_by(ImportLog.When.desc()).limit(200).all()
    items = [{"At": str(r.When), "Actor": r.Actor, "Endpoint": r.Endpoint,
              "Filename": r.Filename, "Summary": r.Summary} for r in rows]
    return jsonify({"items": items})

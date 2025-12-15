# backend/app.py
from __future__ import annotations
import logging
import traceback
from functools import wraps
import io
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from sqlalchemy.engine import Engine
from flask import Flask, jsonify, request, current_app,redirect
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
)
from passlib.context import CryptContext
pwd_ctx = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")
from sqlalchemy import func, case, desc
import os, google.generativeai as genai
import sys,shutil
from .models import (
    db,
    NguoiDung, VaiTro, SinhVien, LopHoc, NganhHoc, HocPhan,
    KetQuaHocTap,
    SystemConfig, ImportLog,
    WarningRule, WarningCase,ChuongTrinhDaoTao,
    Khoa,
)
from .importer import import_curriculum, import_class_roster, import_grades
from .services.analytics_service import get_dashboard_analytics
from .admin_ui import bp as admin_ui_bp
from .admin_crud import crud_bp, roles_required
from sqlalchemy import event
import sqlite3
from dotenv import load_dotenv


ALLOWED_CONFIG_KEYS = [
    "GPA_GIOI_THRESHOLD",
    "GPA_KHA_THRESHOLD",
    "GPA_TRUNGBINH_THRESHOLD",
    "TINCHI_NO_CANHCAO_THRESHOLD",
    "EMAIL_DOMAIN",
    "DEFAULT_MAJOR",
    "RETAKE_POLICY_DEFAULT",
]

CONFIG_META = {
    "GPA_GIOI_THRESHOLD": "Ngưỡng GPA xếp loại Giỏi",
    "GPA_KHA_THRESHOLD": "Ngưỡng GPA xếp loại Khá",
    "GPA_TRUNGBINH_THRESHOLD": "Ngưỡng GPA Cảnh báo",
    "TINCHI_NO_CANHCAO_THRESHOLD": "Số tín chỉ nợ để cảnh báo",
    "EMAIL_DOMAIN": "Tên miền email nội bộ",
    "DEFAULT_MAJOR": "Mã ngành mặc định khi chưa xác định",
    "RETAKE_POLICY_DEFAULT": "Chính sách thi lại mặc định (keep-latest|best)",
}

RUN_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
BASE = Path(getattr(sys, "_MEIPASS", RUN_DIR))

external_env = RUN_DIR / ".env"
embedded_env = BASE / ".env"
env_path = external_env if external_env.exists() else embedded_env

if getattr(sys, "frozen", False) and embedded_env.exists() and not external_env.exists():
    try:
        shutil.copy(embedded_env, external_env)
        env_path = external_env
    except Exception:
        pass

load_dotenv(env_path)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False, separators=(",",":"))

def _is_sqlite_uri(uri: str) -> bool:
    return uri.startswith("sqlite:")
def truthy(x: Any) -> bool:
    return str(x).strip().lower() in ("1","true","yes","y","on")

@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, conn_record):
    if isinstance(dbapi_conn, sqlite3.Connection):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA busy_timeout=30000;")

            try:
                cur.execute("PRAGMA journal_mode;")
                mode = (cur.fetchone() or ("",))[0]
            except Exception:
                mode = ""

            if str(mode).lower() != "wal":
                try:
                    cur.execute("PRAGMA journal_mode=WAL;")
                except sqlite3.OperationalError:
                    pass

            cur.execute("PRAGMA synchronous=NORMAL;")
        finally:
            try:
                cur.close()
            except Exception:
                pass

def _actor_id() -> Optional[int]:
    try:
        ident = get_jwt_identity()
        if ident is None:
            return None
        return int(str(ident))
    except Exception:
        return None

def _actor_username() -> Optional[str]:
    try:
        claims = get_jwt()
        return claims.get("username")
    except Exception:
        return None

def _audit_db(endpoint: str, summary: Dict[str, Any], *, filename: Optional[str]=None, affected: Optional[str]=None):

    try:
        db.session.add(ImportLog(
            When = datetime.now(timezone.utc),  # tránh DeprecationWarning
            Actor = _actor_username() or str(_actor_id() or ""),
            Endpoint = endpoint,
            Params = json.dumps({"q": request.args.to_dict(), "body": request.get_json(silent=True)}, ensure_ascii=False),
            Filename = filename,
            Summary = json.dumps(summary, ensure_ascii=False),
            AffectedTable = affected,
            InsertedIds = None,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

def _ensure_warning_rule(code: str, name: str, threshold: float) -> WarningRule:
    r = WarningRule.query.filter_by(Code=code).first()
    if r:
        return r
    r = WarningRule(Code=code, Name=name, Threshold=float(threshold), Active=True, Desc=None)
    db.session.add(r); db.session.commit()
    return r

def audit(endpoint_name: str):

    def _decorator(view_func):
        @wraps(view_func)
        def _wrapped(*args, **kwargs):
            fname = None
            try:
                f = request.files.get("file")
                if f:
                    fname = getattr(f, "filename", None)
            except Exception:
                pass

            status = 200
            try:
                rv = view_func(*args, **kwargs)
                if isinstance(rv, tuple) and len(rv) >= 2 and isinstance(rv[1], int):
                    status = rv[1]
                return rv
            finally:
                try:
                    _audit_db(endpoint_name, {"status": status}, filename=fname, affected=None)
                except Exception as e:
                    # Không để log làm hỏng request
                    print(f"[AUDIT] failed: {e}")
        return _wrapped
    return _decorator



def create_app() -> Flask:
    app = Flask(__name__)

    basedir = os.path.dirname(__file__)
    db_path = os.path.join(basedir, "app.db")
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{db_path}")
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("SECRET_KEY", os.getenv("SECRET_KEY", "dev-secret"))
    app.config.setdefault("JWT_SECRET_KEY", os.getenv("JWT_SECRET_KEY", "dev-jwt"))
    app.config.setdefault("MAX_CONTENT_LENGTH", 50 * 1024 * 1024)
    app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {})
    app.config["SQLALCHEMY_ENGINE_OPTIONS"].setdefault("connect_args", {})
    app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"].update({"timeout": 30})
    app.register_blueprint(admin_ui_bp)
    app.register_blueprint(crud_bp)
    CORS(app, supports_credentials=True)
    db.init_app(app)
    jwt = JWTManager(app)
    RUN_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    db_path = RUN_DIR / "app.db"
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{db_path.as_posix()}")

    @app.post("/login")
    def login():
        body = request.get_json(silent=True) or {}
        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()
        if not username or not password:
            return jsonify({"msg": "Thiếu username hoặc password"}), 400

        user = NguoiDung.query.filter_by(TenDangNhap=username).first()
        if not user:
            return jsonify({"msg": "Sai username hoặc password"}), 400

        ok = False
        stored = user.MatKhauMaHoa or ""
        try:
            if stored and stored.startswith("$"):
                ok = pwd_ctx.verify(password, stored)
            else:
                ok = (password == stored)
                if ok:
                    user.MatKhauMaHoa = pwd_ctx.hash(password)
                    db.session.commit()
        except Exception:
            ok = False

        if not ok:
            return jsonify({"msg": "Sai username hoặc password"}), 400

        role = user.vai_tro_rel.TenVaiTro if user.vai_tro_rel else "Sinh viên"

        token = create_access_token(identity=str(user.MaNguoiDung),
                                    additional_claims={"username": username, "role": role})

        _audit_db("POST /login", {"login": "ok"}, filename=None, affected="Auth")
        return jsonify({"access_token": token, "user": {"username": username, "role": role}})

    @app.post("/api/auth/login")
    def api_auth_login():
        return login()

    @app.get("/api/auth/me")
    @jwt_required()
    def me():
        uid = _actor_id()
        u = db.session.get(NguoiDung, uid) if uid else None
        role = u.vai_tro_rel.TenVaiTro if (u and u.vai_tro_rel) else get_jwt().get("role")
        return jsonify({"user": {"id": uid, "username": (u.TenDangNhap if u else get_jwt().get("username")), "role": role}})

    @app.get("/")
    def root():
        return redirect("/admin/", code=302)


    @app.get("/api/analytics/kpi")
    @jwt_required()
    def analytics_kpi():
        ma_nganh = request.args.get("MaNganh")
        data = get_dashboard_analytics(ma_nganh=ma_nganh)
        return jsonify(data)

    @app.get("/api/analytics/top-fails")
    @jwt_required()
    def analytics_top_fails():
        ma_nganh = request.args.get("MaNganh")
        data = get_dashboard_analytics(ma_nganh=ma_nganh) or {}
        return jsonify({"items": data.get("top_failing_courses", [])})

    @app.get("/api/admin/dashboard-analytics")
    @roles_required("Admin", "Cán bộ đào tạo")
    def dashboard_analytics():
        import sqlalchemy as sa
        total_students = db.session.scalar(sa.select(sa.func.count()).select_from(SinhVien)) or 0
        total_courses  = db.session.scalar(sa.select(sa.func.count()).select_from(HocPhan)) or 0
        total_kq       = db.session.scalar(sa.select(sa.func.count()).select_from(KetQuaHocTap)) or 0
        pass_kq = db.session.scalar(
            sa.select(sa.func.count()).where(
                sa.or_(KetQuaHocTap.KetQua.in_(["Đạt","Pass"]), KetQuaHocTap.DiemHe10 >= 4.0)
            ).select_from(KetQuaHocTap)
        ) or 0
        pass_rate = (pass_kq/total_kq) if total_kq else 0.0
        return {"kpi":{"total_students": total_students, "total_courses": total_courses, "pass_rate": round(pass_rate,4)}}


    @app.post("/api/admin/import/curriculum")
    @roles_required("Admin")
    @audit("POST /api/admin/import/curriculum")
    def api_import_curriculum():
        rv = import_curriculum()
        if isinstance(rv, tuple):
            data, code = rv
            return (data if hasattr(data, "response") else jsonify(data), code)
        return rv if hasattr(rv, "response") else jsonify(rv)

    @app.post("/api/admin/import/class-roster")
    @roles_required("Admin", "Cán bộ đào tạo")
    @audit("POST /api/admin/import/class-roster")
    def api_import_roster():
        rv = import_class_roster()
        if isinstance(rv, tuple):
            data, code = rv
            return (data if hasattr(data, "response") else jsonify(data), code)
        return rv if hasattr(rv, "response") else jsonify(rv)

    @app.post("/api/admin/import/grades")
    @roles_required("Admin", "Cán bộ đào tạo")
    @audit("POST /api/admin/import/grades")
    def api_import_grades():
        rv = import_grades()
        if isinstance(rv, tuple):
            data, code = rv
            return (data if hasattr(data, "response") else jsonify(data), code)
        return rv if hasattr(rv, "response") else jsonify(rv)
    @app.get("/api/admin/configs")
    @jwt_required()
    def api_get_configs():
        values = {k: (db.session.get(SystemConfig, k).ConfigValue if db.session.get(SystemConfig, k) else "") for k in ALLOWED_CONFIG_KEYS}
        return jsonify({"values": values, "meta": CONFIG_META})

    @app.put("/api/admin/configs")
    @jwt_required()
    def api_put_configs():
        body = request.get_json(silent=True) or {}
        changed = {}
        for k, v in (body.get("values") or {}).items():
            if k not in ALLOWED_CONFIG_KEYS:
                continue
            row = db.session.get(SystemConfig, k)
            if not row:
                row = SystemConfig(ConfigKey=k, ConfigValue=str(v))
                db.session.add(row)
            else:
                row.ConfigValue = str(v)
            changed[k] = str(v)
        db.session.commit()
        _audit_db("PUT /api/admin/configs", {"changed": changed}, affected="SystemConfig")
        return jsonify({"msg": "OK", "changed": changed})

    @app.get("/api/admin/import/logs")
    @jwt_required()
    def api_import_logs():
        rows = (ImportLog.query.order_by(ImportLog.When.desc()).limit(50).all())
        items = [{
            "RunId": r.RunId,
            "At": r.When.isoformat(timespec="seconds"),
            "Actor": r.Actor, "Endpoint": r.Endpoint,
            "Params": r.Params, "Filename": r.Filename,
            "Summary": r.Summary, "AffectedTable": r.AffectedTable,
            "InsertedIds": r.InsertedIds
        } for r in rows]
        return jsonify({"items": items})

    @app.post("/api/admin/warning/scan")
    @jwt_required()
    def warning_scan():
        cfg = {c.ConfigKey: c.ConfigValue for c in SystemConfig.query.all()}
        gpa_th = float(cfg.get("GPA_TRUNGBINH_THRESHOLD", 2.0))
        debt_th = float(cfg.get("TINCHI_NO_CANHCAO_THRESHOLD", 10))

        r_gpa = _ensure_warning_rule("GPA_BELOW", "GPA dưới ngưỡng", gpa_th)
        r_debt = _ensure_warning_rule("DEBT_OVER", "Nợ tín chỉ vượt ngưỡng", debt_th)

        sub = (db.session.query(
                    KetQuaHocTap.MaSV.label("MaSV"),
                    func.sum((KetQuaHocTap.DiemHe4 * (case((HocPhan.SoTinChi != None, HocPhan.SoTinChi), else_=0)))).label("S"),
                    func.sum(case((HocPhan.SoTinChi != None, HocPhan.SoTinChi), else_=0)).label("W"),
                    func.sum(case((KetQuaHocTap.DiemHe4 < 1.0, HocPhan.SoTinChi), else_=0)).label("DebtTC"),
                )
                .join(HocPhan, HocPhan.MaHP == KetQuaHocTap.MaHP, isouter=True)
                .filter(KetQuaHocTap.LaDiemCuoiCung.is_(True))
                .group_by(KetQuaHocTap.MaSV)
                ).subquery()

        q = (db.session.query(
                SinhVien.MaSV, SinhVien.HoTen,
                (sub.c.S / func.nullif(sub.c.W, 0)).label("GPA4"),
                sub.c.DebtTC
            )
            .join(sub, sub.c.MaSV == SinhVien.MaSV, isouter=True))

        ma_lop = request.args.get("MaLop")
        if ma_lop:
            q = q.filter(SinhVien.MaLop == ma_lop)

        affected = 0
        for masv, hoten, gpa4, debttc in q.all():
            gpa4 = float(gpa4 or 0.0); debttc = float(debttc or 0.0)
            if gpa4 > 0 and gpa4 < r_gpa.Threshold:
                exists = WarningCase.query.filter_by(RuleId=r_gpa.Id, MaSV=masv, Status="open").first()
                if not exists:
                    db.session.add(WarningCase(RuleId=r_gpa.Id, MaSV=masv, Value=gpa4, Level="critical", Status="open"))
                    affected += 1
            if debttc >= r_debt.Threshold:
                exists = WarningCase.query.filter_by(RuleId=r_debt.Id, MaSV=masv, Status="open").first()
                if not exists:
                    db.session.add(WarningCase(RuleId=r_debt.Id, MaSV=masv, Value=debttc, Level="warning", Status="open"))
                    affected += 1

        db.session.commit()
        _audit_db("POST /api/admin/warning/scan", {"created_cases": affected}, affected="WarningCase")
        return jsonify({"created_cases": affected})

    @app.get("/api/admin/warning/cases")
    @jwt_required()
    def warning_cases():
        page = max(1, int(request.args.get("page", 1)))
        size = max(1, min(100, int(request.args.get("size", 20))))
        status = (request.args.get("status") or "open").strip()
        q = WarningCase.query
        if status:
            q = q.filter(WarningCase.Status == status)
        total = q.count()
        rows = q.order_by(desc(WarningCase.Id)).offset((page-1)*size).limit(size).all()
        return jsonify({"total": total, "items": [
            {"Id": r.Id, "RuleId": r.RuleId, "MaSV": r.MaSV, "Value": r.Value, "Level": r.Level,
              "Status": r.Status, "At": r.CreatedAt.isoformat()} for r in rows
        ]})

    @app.put("/api/admin/warning/cases/<int:cid>/close")
    @jwt_required()
    def warning_close(cid: int):
        r = db.session.get(WarningCase, cid)
        if not r:
            return jsonify({"msg": "Không tìm thấy case"}), 404
        r.Status = "closed"; r.ClosedAt = datetime.now(timezone.utc)
        db.session.commit()
        _audit_db("PUT /api/admin/warning/cases/<id>/close", {"closed": cid}, affected="WarningCase")
        return jsonify({"msg": "OK"})

    @app.get("/api/admin/warning/rules")
    @jwt_required()
    def warning_rules_list():
        rows = WarningRule.query.order_by(WarningRule.Code).all()
        return jsonify([{
            "Id": r.Id, "Code": r.Code, "Name": r.Name,
            "Threshold": r.Threshold, "Active": r.Active
        } for r in rows])

    @app.post("/api/admin/warning/rules")
    @jwt_required()
    def warning_rules_create():
        b = request.get_json(silent=True) or {}
        code = (b.get("Code") or "").strip().upper()
        name = (b.get("Name") or "").strip()
        th = float(b.get("Threshold") or 0)
        if not code or not name:
            return jsonify({"msg": "Thiếu Code/Name"}), 400
        if WarningRule.query.filter_by(Code=code).first():
            return jsonify({"msg": "Code đã tồn tại"}), 409
        r = WarningRule(Code=code, Name=name, Threshold=th, Active=True)
        db.session.add(r); db.session.commit()
        _audit_db("POST /api/admin/warning/rules", {"inserted": code}, affected="WarningRule")
        return jsonify({"msg": "OK", "Id": r.Id}), 201

    @app.delete("/api/admin/warning/rules/<int:rid>")
    @jwt_required()
    def warning_rules_delete(rid: int):
        r = db.session.get(WarningRule, rid)
        if not r:
            return jsonify({"msg": "Không tồn tại"}), 404
        db.session.delete(r); db.session.commit()
        _audit_db("DELETE /api/admin/warning/rules/<id>", {"deleted": rid}, affected="WarningRule")
        return jsonify({"msg": "OK"})

    @app.get("/api/admin/export/students.csv")
    @jwt_required()
    def export_students_csv():
        q = (db.session.query(SinhVien.MaSV, SinhVien.HoTen, LopHoc.TenLop, NganhHoc.TenNganh)
             .join(LopHoc, LopHoc.MaLop == SinhVien.MaLop, isouter=True)
             .join(NganhHoc, NganhHoc.MaNganh == LopHoc.MaNganh, isouter=True))
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["MaSV","HoTen","Lop","Nganh"])
        for msv, ht, lop, nganh in q.all():
            w.writerow([msv, ht, lop or "", nganh or ""])
        from flask import Response
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=students.csv"})

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/api/me")
    @jwt_required()
    def me_compat():
        return me()

    @app.get("/api/student/data")
    @jwt_required()
    def student_data_compat():
        from sqlalchemy import func, or_

        uid = _actor_id()
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
        lop = db.session.get(LopHoc, ma_lop) if ma_lop else None
        nganh = db.session.get(NganhHoc, getattr(lop, "MaNganh", None)) if lop else None

        kq_list = db.session.query(KetQuaHocTap).filter_by(MaSV=masv).all()

        def _row(kq):
            mahp = getattr(kq, "MaHP", None)
            hp = db.session.get(HocPhan, mahp) if mahp else None
            return {
                "HocKy": getattr(kq, "HocKy", None),
                "MaHP": mahp,
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
            q = db.session.query(CTDT)
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
                hp = db.session.get(HocPhan, getattr(r, "MaHP", None))
                plan.append({
                    "HocKy": _digits_to_int(getattr(r, "HocKy", None)),
                    "MaHP": getattr(r, "MaHP", None),
                    "TenHP": getattr(hp, "TenHP", None) or getattr(r, "hoc_phan_rel", None).TenHP if hasattr(r,
                                                                                                             "hoc_phan_rel") and r.hoc_phan_rel else None,
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

    @app.get("/api/admin/classes")
    @roles_required("Admin", "Cán bộ đào tạo")
    def admin_get_all_classes_compat():
        rows = LopHoc.query.order_by(LopHoc.TenLop).all()
        return jsonify([{"MaLop": r.MaLop, "TenLop": r.TenLop} for r in rows])

    @app.get("/api/admin/majors")
    @roles_required("Admin", "Cán bộ đào tạo")
    def admin_get_all_majors_compat():
        rows = NganhHoc.query.order_by(NganhHoc.TenNganh).all()
        return jsonify([{"MaNganh": r.MaNganh, "TenNganh": r.TenNganh} for r in rows])

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise RuntimeError("Thiếu GEMINI_API_KEY trong environment/.env")

    genai.configure(api_key=GEMINI_API_KEY)
    MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

    SYSTEM_PROMPT = (
        "Bạn là cố vấn học tập cho sinh viên Việt Nam. "
        "Trả lời ngắn gọn, rõ ràng; dùng gạch đầu dòng; tập trung tư vấn đăng ký học phần và cải thiện GPA."
        "Các nội dung cần biết:CPA(Cumulative Point Average) là điểm trung bình tích lũy của toàn bộ quá trình học tập từ đầu đến thời điểm hiện tại, phản ánh tổng thể năng lực học thuật,GPA (Grade Point Average) là Là điểm trung bình các môn học đạt được trong một khóa học hoặc kỳ học cụ thể. Đây là thước đo kết quả học tập trong một giai đoạn."
    )

    @app.post("/api/advisor/gemini")
    def advisor_gemini():
        try:
            data = request.get_json(force=True) or {}
            history = data.get("messages", [])
            use_ctx = bool(data.get("use_context"))
            ctx = data.get("context") if use_ctx else None

            app.logger.info("[advisor] use_ctx=%s, messages=%d", use_ctx, len(history))
            if use_ctx and ctx:
                app.logger.info("[advisor] ctx keys: %s", list(ctx.keys()))

            parts = [{"text": SYSTEM_PROMPT}]
            if use_ctx and ctx:
                parts.append({"text": "DỮ LIỆU HỌC TẬP JSON (chỉ dùng lập luận, không lặp lại):"})
                try:
                    parts.append({"text": json.dumps(ctx, ensure_ascii=False)[:5000]})
                except Exception:
                    pass

            for m in history:
                r = (m.get("role") or "user")
                t = (m.get("text") or "")
                if not t:
                    continue
                parts.append({"text": ("USER: " if r == "user" else "AI: ") + t})

            model = genai.GenerativeModel(MODEL_NAME)
            resp = model.generate_content(parts)
            text = (getattr(resp, "text", "") or "").strip() or "Mình chưa nhận được nội dung khả dụng."
            return jsonify({"text": text})

        except Exception as e:
            app.logger.exception("[advisor] ERROR: %s", e)
            return jsonify({
                "detail": f"{type(e).__name__}: {e}",
                "trace": traceback.format_exc(limit=5),
            }), 500
    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        if SystemConfig.query.count() == 0:
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
                db.session.add(SystemConfig(ConfigKey=k, ConfigValue=str(v)))
            db.session.commit()
    app.run(debug=True, port=5000, use_reloader=False, threaded=False)

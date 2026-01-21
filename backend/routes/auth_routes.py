from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required, get_jwt
from passlib.context import CryptContext
from ..models import db, NguoiDung
from ..utils import audit_db, get_actor_id

bp = Blueprint("auth", __name__)

pwd_ctx = CryptContext(schemes=["bcrypt", "pbkdf2_sha256"], deprecated="auto")

@bp.post("/login")
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

    audit_db("POST /login", {"login": "ok"}, filename=None, affected="Auth")
    return jsonify({"access_token": token, "user": {"username": username, "role": role}})

@bp.post("/api/auth/login")
def api_auth_login():
    return login()

@bp.get("/api/auth/me")
@jwt_required()
def me():
    uid = get_actor_id()
    u = db.session.get(NguoiDung, uid) if uid else None
    role = u.vai_tro_rel.TenVaiTro if (u and u.vai_tro_rel) else get_jwt().get("role")
    return jsonify({"user": {"id": uid, "username": (u.TenDangNhap if u else get_jwt().get("username")), "role": role}})

@bp.get("/api/me")
@jwt_required()
def me_compat():
    return me()

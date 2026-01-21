import json
from datetime import datetime, timezone
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, get_jwt, jwt_required
from .models import db, ImportLog

def get_actor_id():
    try:
        ident = get_jwt_identity()
        if ident is None:
            return None
        return int(str(ident))
    except Exception:
        return None

def get_actor_username():
    try:
        claims = get_jwt()
        return claims.get("username")
    except Exception:
        return None

def audit_db(endpoint: str, summary: dict, *, filename: str=None, affected: str=None):
    try:
        db.session.add(ImportLog(
            When = datetime.now(timezone.utc),
            Actor = get_actor_username() or str(get_actor_id() or ""),
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
                    audit_db(endpoint_name, {"status": status}, filename=fname, affected=None)
                except Exception as e:
                    print(f"[AUDIT] failed: {e}")
        return _wrapped
    return _decorator

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

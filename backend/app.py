from __future__ import annotations
import logging
import sys
import shutil
import os
import sqlite3
from pathlib import Path

from flask import Flask, redirect
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from sqlalchemy import event
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

from .models import db, SystemConfig
from .admin_ui import bp as admin_ui_bp
from .admin_crud import bp as admin_crud_bp
from .routes.auth_routes import bp as auth_bp
from .routes.student_routes import bp as student_bp
from .routes.advisor_routes import bp as advisor_bp
from .routes.analytics_routes import bp as analytics_bp

# Environment setup
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

def create_app() -> Flask:
    app = Flask(__name__)

    basedir = os.path.dirname(__file__)
    db_path = os.path.join(basedir, "app.db")

    # Check if frozen/packaged
    RUN_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    db_path_frozen = RUN_DIR / "app.db"

    # Use frozen path if likely running packaged, otherwise local
    if getattr(sys, "frozen", False):
         app.config.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{db_path_frozen.as_posix()}")
    else:
         app.config.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{db_path}")

    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("SECRET_KEY", os.getenv("SECRET_KEY", "dev-secret"))
    app.config.setdefault("JWT_SECRET_KEY", os.getenv("JWT_SECRET_KEY", "dev-jwt"))
    app.config.setdefault("MAX_CONTENT_LENGTH", 50 * 1024 * 1024)
    app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {})
    app.config["SQLALCHEMY_ENGINE_OPTIONS"].setdefault("connect_args", {})
    app.config["SQLALCHEMY_ENGINE_OPTIONS"]["connect_args"].update({"timeout": 30})

    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    CORS(app, supports_credentials=True)

    # Register Blueprints
    app.register_blueprint(admin_ui_bp)
    app.register_blueprint(admin_crud_bp) # usually prefix /api/admin or similar, but defined in bp itself
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(advisor_bp)
    app.register_blueprint(analytics_bp)

    @app.get("/")
    def root():
        return redirect("/admin/", code=302)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        # Initial seeding for dev
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

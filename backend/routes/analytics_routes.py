from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func, or_
from ..models import db, SinhVien, HocPhan, KetQuaHocTap
from ..services.analytics_service import get_dashboard_analytics
from ..utils import roles_required

bp = Blueprint("analytics", __name__)

@bp.get("/api/analytics/kpi")
@jwt_required()
def analytics_kpi():
    ma_nganh = request.args.get("MaNganh")
    data = get_dashboard_analytics(ma_nganh=ma_nganh)
    return jsonify(data)

@bp.get("/api/analytics/top-fails")
@jwt_required()
def analytics_top_fails():
    ma_nganh = request.args.get("MaNganh")
    data = get_dashboard_analytics(ma_nganh=ma_nganh) or {}
    return jsonify({"items": data.get("top_failing_courses", [])})

@bp.get("/api/admin/dashboard-analytics")
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
    return jsonify({"kpi":{"total_students": total_students, "total_courses": total_courses, "pass_rate": round(pass_rate,4)}})

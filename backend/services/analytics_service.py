# backend/services/analytics_service.py
from sqlalchemy import func, case, and_, desc
from ..models import db, SinhVien, KetQuaHocTap, HocPhan, SystemConfig, LopHoc

def _cfg_float(dct, key, default):
    try:
        return float(dct.get(key, default))
    except Exception:
        return float(default)

def get_system_configs():
    cfg = {c.ConfigKey: c.ConfigValue for c in SystemConfig.query.all()}
    return {
        "GPA_WARN_THRESHOLD": _cfg_float(cfg, "GPA_TRUNGBINH_THRESHOLD", 2.0),
        "DEBT_WARN_TINCHI" : _cfg_float(cfg, "TINCHI_NO_CANHCAO_THRESHOLD", 10.0),
    }

def get_dashboard_analytics(ma_nganh=None):
    q_sv = db.session.query(func.count(SinhVien.MaSV))
    if ma_nganh:
        q_sv = q_sv.join(LopHoc, LopHoc.MaLop == SinhVien.MaLop, isouter=True)\
                   .filter(LopHoc.MaNganh == ma_nganh)
    total_students = int(q_sv.scalar() or 0)
    total_courses  = int(db.session.query(func.count(HocPhan.MaHP)).scalar() or 0)

    total_kq = db.session.query(func.count(KetQuaHocTap.MaKQ)).scalar() or 1
    pass_kq  = db.session.query(func.count(KetQuaHocTap.MaKQ))\
                         .filter(KetQuaHocTap.DiemHe4 >= 2.0).scalar() or 0
    pass_rate = float(pass_kq) / float(total_kq) * 100.0

    cfg = get_system_configs()
    sub = (db.session.query(
                KetQuaHocTap.MaSV.label("MaSV"),
                func.sum((KetQuaHocTap.DiemHe4* (case((HocPhan.SoTinChi != None, HocPhan.SoTinChi), else_=0)))).label("S"),
                func.sum(case((HocPhan.SoTinChi != None, HocPhan.SoTinChi), else_=0)).label("W"),
                func.sum(case((KetQuaHocTap.DiemHe4 < 1.0, HocPhan.SoTinChi), else_=0)).label("DebtTC"),
            )
            .join(HocPhan, HocPhan.MaHP == KetQuaHocTap.MaHP, isouter=True)
            .filter(KetQuaHocTap.LaDiemCuoiCung.is_(True))
            .group_by(KetQuaHocTap.MaSV)
            ).subquery()

    q_risk = (db.session.query(
                SinhVien.MaSV, SinhVien.HoTen, SinhVien.MaLop,
                (sub.c.S / func.nullif(sub.c.W, 0)).label("GPA4"),
                sub.c.DebtTC
            )
            .join(sub, sub.c.MaSV == SinhVien.MaSV, isouter=True)
            .order_by(desc("DebtTC"))
            .limit(50)
            )

    if ma_nganh:
        q_risk = q_risk.join(LopHoc, LopHoc.MaLop == SinhVien.MaLop, isouter=True)\
                       .filter(LopHoc.MaNganh == ma_nganh)

    students_at_risk = []
    for r in q_risk:
        gpa = float(r.GPA4 or 0.0)
        debt = int(r.DebtTC or 0)
        if gpa <= cfg["GPA_WARN_THRESHOLD"] or debt >= cfg["DEBT_WARN_TINCHI"]:
            students_at_risk.append({
                "MaSV": r.MaSV, "HoTen": r.HoTen, "Lop": r.MaLop,
                "Rule": "GPA_BELOW" if gpa <= cfg["GPA_WARN_THRESHOLD"] else "DEBT_OVER",
                "Value": round(gpa, 2) if gpa <= cfg["GPA_WARN_THRESHOLD"] else debt,
            })

    q_top = (db.session.query(
                KetQuaHocTap.MaHP.label("MaHP"),
                func.count(KetQuaHocTap.MaKQ).label("N"),
                func.sum(case((KetQuaHocTap.DiemHe4 == 0, 1), else_=0)).label("F"))
             .join(HocPhan, HocPhan.MaHP == KetQuaHocTap.MaHP)
             .filter(KetQuaHocTap.LaDiemCuoiCung.is_(True), HocPhan.TinhDiemTichLuy.is_(True))
             .group_by(KetQuaHocTap.MaHP)
             .order_by((func.sum(case((KetQuaHocTap.DiemHe4 == 0, 1), else_=0))*1.0/func.count(KetQuaHocTap.MaKQ)).desc())
             .limit(10)
            )
    name_map = {hp.MaHP: hp.TenHP for hp in HocPhan.query.all()}
    top_failing_courses = [{
        "MaHP": m, "TenHP": name_map.get(m, ""),
        "failure_rate": (float(f or 0)/float(max(1, n)))*100.0,
        "total": int(n)
    } for (m, n, f) in q_top.all()]

    return {
        "kpis": {
            "total_students": total_students,
            "total_courses": total_courses,
            "pass_rate": pass_rate
        },
        "students_at_risk": students_at_risk,
        "top_failing_courses": top_failing_courses
    }

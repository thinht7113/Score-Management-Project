# backend/services/analytics_service.py

from sqlalchemy import func, case, and_
from ..models import db, SinhVien, KetQuaHocTap, HocPhan, SystemConfig, LopHoc


def get_system_configs():
    """
    Tải và chuyển đổi các cấu hình hệ thống từ chuỗi sang đúng kiểu dữ liệu.
    Có thể cache kết quả trong môi trường production.
    """
    configs = SystemConfig.query.all()
    config_map = {c.ConfigKey: c.ConfigValue for c in configs}
    try:
        return {
            'gpa_excellent': float(config_map.get('GPA_GIOI_THRESHOLD', 3.6)),
            'gpa_good': float(config_map.get('GPA_KHA_THRESHOLD', 2.5)),
            'gpa_average': float(config_map.get('GPA_TRUNGBINH_THRESHOLD', 2.0)),
            'credits_warning': int(config_map.get('TINCHI_NO_CANHCAO_THRESHOLD', 8))
        }
    except (ValueError, TypeError):
        # Giá trị mặc định an toàn
        return {'gpa_excellent': 3.6, 'gpa_good': 2.5, 'gpa_average': 2.0, 'credits_warning': 8}


def get_dashboard_analytics(ma_nganh=None):
    """
    Tính toán và tổng hợp các chỉ số cho Dashboard Admin.
    Hỗ trợ lọc theo mã ngành nếu truyền ma_nganh.
    """
    cfg = get_system_configs()

    # --- 1) Subquery GPA & Tín chỉ nợ cho mỗi SV ---
    gpa_subq = db.session.query(
        KetQuaHocTap.MaSV,
        (func.sum(KetQuaHocTap.DiemHe4 * HocPhan.SoTinChi) / func.sum(HocPhan.SoTinChi)).label('gpa'),
        func.sum(case((KetQuaHocTap.DiemHe4 == 0, HocPhan.SoTinChi), else_=0)).label('credits_debt')
    ).join(HocPhan, HocPhan.MaHP == KetQuaHocTap.MaHP) \
     .filter(HocPhan.TinhDiemTichLuy.is_(True),
             KetQuaHocTap.LaDiemCuoiCung.is_(True)) \
     .group_by(KetQuaHocTap.MaSV) \
     .subquery()

    # --- 2) Thống kê SV theo ngưỡng ---
    student_stats_q = db.session.query(
        func.count(SinhVien.MaSV).label('total_students'),
        func.sum(case((gpa_subq.c.gpa >= cfg['gpa_excellent'], 1), else_=0)).label('excellent_students'),
        func.sum(case((and_(gpa_subq.c.gpa >= cfg['gpa_good'], gpa_subq.c.gpa < cfg['gpa_excellent']), 1), else_=0)).label('good_students'),
        func.sum(case((and_(gpa_subq.c.gpa >= cfg['gpa_average'], gpa_subq.c.gpa < cfg['gpa_good']), 1), else_=0)).label('average_students'),
        func.sum(case((gpa_subq.c.gpa < cfg['gpa_average'], 1), else_=0)).label('weak_students'),
    ).select_from(SinhVien).join(gpa_subq, SinhVien.MaSV == gpa_subq.c.MaSV, isouter=True)

    if ma_nganh:
        student_stats_q = student_stats_q.join(LopHoc, SinhVien.MaLop == LopHoc.MaLop).filter(LopHoc.MaNganh == ma_nganh)

    student_stats = student_stats_q.one_or_none()

    # --- 3) SV có nguy cơ (gpa < trung bình) ---
    students_at_risk_q = db.session.query(
        SinhVien.HoTen, gpa_subq.c.gpa, gpa_subq.c.credits_debt
    ).join(gpa_subq, SinhVien.MaSV == gpa_subq.c.MaSV) \
     .filter(gpa_subq.c.gpa < cfg['gpa_average']) \
     .order_by(gpa_subq.c.gpa.asc()) \
     .limit(5)

    if ma_nganh:
        students_at_risk_q = students_at_risk_q.join(LopHoc, SinhVien.MaLop == LopHoc.MaLop).filter(LopHoc.MaNganh == ma_nganh)

    students_at_risk = students_at_risk_q.all()

    # --- 4) Top môn có tỷ lệ trượt cao (tính thật) ---
    # failed = điểm hệ 4 == 0; total = tổng lần ghi nhận điểm cuối cùng của môn; chỉ tính môn được tính tích lũy
    course_fail_q = db.session.query(
        HocPhan.MaHP,
        HocPhan.TenHP,
        func.count(KetQuaHocTap.MaKQ).label('total'),
        func.sum(case((KetQuaHocTap.DiemHe4 == 0, 1), else_=0)).label('failed')
    ).join(HocPhan, HocPhan.MaHP == KetQuaHocTap.MaHP) \
     .join(SinhVien, SinhVien.MaSV == KetQuaHocTap.MaSV) \
     .join(LopHoc, LopHoc.MaLop == SinhVien.MaLop, isouter=True) \
     .filter(KetQuaHocTap.LaDiemCuoiCung.is_(True),
             HocPhan.TinhDiemTichLuy.is_(True))

    if ma_nganh:
        course_fail_q = course_fail_q.filter(LopHoc.MaNganh == ma_nganh)

    course_fail_q = course_fail_q.group_by(HocPhan.MaHP, HocPhan.TenHP) \
                                 .having(func.count(KetQuaHocTap.MaKQ) > 0) \
                                 .order_by((func.sum(case((KetQuaHocTap.DiemHe4 == 0, 1), else_=0)) * 1.0 /
                                            func.count(KetQuaHocTap.MaKQ)).desc()) \
                                 .limit(10)

    course_fail_rows = course_fail_q.all()
    top_failing_courses = [{
        "MaHP": r.MaHP,
        "TenHP": r.TenHP,
        "failure_rate": round((float(r.failed) / float(r.total)) * 100.0, 2) if r.total else 0.0,
        "failed": int(r.failed),
        "total": int(r.total),
    } for r in course_fail_rows]

    # --- 5) Tổng hợp kết quả ---
    return {
        "kpis": {
            "total_students": student_stats.total_students if student_stats else 0,
            "excellent_students": student_stats.excellent_students if student_stats else 0,
            "good_students": student_stats.good_students if student_stats else 0,
            "average_students": student_stats.average_students if student_stats else 0,
            "weak_students": student_stats.weak_students if student_stats else 0,
        },
        "students_at_risk": [
            {"HoTen": sv.HoTen, "gpa": round(sv.gpa, 2) if sv.gpa else 0, "credits_debt": sv.credits_debt}
            for sv in students_at_risk
        ],
        "top_failing_courses": top_failing_courses
    }

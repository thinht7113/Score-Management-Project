# backend/services/analytics_service.py

from backend.models import db, SinhVien, KetQuaHocTap, HocPhan, SystemConfig, LopHoc
from sqlalchemy import func, case, and_


def get_system_configs():
    """
    Tải và chuyển đổi các cấu hình hệ thống từ chuỗi sang đúng kiểu dữ liệu.
    Hàm này có thể cache kết quả để tăng hiệu năng trong môi trường thực tế.
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
        # Trả về giá trị mặc định an toàn nếu cấu hình trong CSDL bị lỗi
        return {
            'gpa_excellent': 3.6, 'gpa_good': 2.5, 'gpa_average': 2.0, 'credits_warning': 8
        }


def get_dashboard_analytics(ma_nganh=None):
    """
    Tính toán và tổng hợp TẤT CẢ các chỉ số cần thiết cho Dashboard Admin.
    Thực hiện các truy vấn phức tạp nhưng hiệu quả để giảm tải cho CSDL.
    """
    configs = get_system_configs()

    # --- 1. Subquery: Tính toán GPA và Tín chỉ nợ cho mỗi sinh viên ---
    # Đây là nền tảng cho mọi tính toán sau này.
    gpa_subquery = db.session.query(
        KetQuaHocTap.MaSV,
        (
                func.sum(KetQuaHocTap.DiemHe4 * HocPhan.SoTinChi) /
                func.sum(HocPhan.SoTinChi)
        ).label('gpa'),
        func.sum(
            case((KetQuaHocTap.DiemHe4 == 0, HocPhan.SoTinChi), else_=0)
        ).label('credits_debt')
    ).join(HocPhan, HocPhan.MaHP == KetQuaHocTap.MaHP
           ).filter(
        HocPhan.TinhDiemTichLuy == True,
        KetQuaHocTap.LaDiemCuoiCung == True
    ).group_by(KetQuaHocTap.MaSV).subquery()

    # --- 2. Thống kê Sinh viên ---
    # Query chính để đếm tổng số SV, SV xuất sắc, SV bị cảnh cáo
    student_stats_query = db.session.query(
        func.count(SinhVien.MaSV).label('total_students'),
        func.sum(case((gpa_subquery.c.gpa >= configs['gpa_excellent'], 1), else_=0)).label('excellent_students'),
        func.sum(
            case((and_(gpa_subquery.c.gpa >= configs['gpa_good'], gpa_subquery.c.gpa < configs['gpa_excellent']), 1),
                 else_=0)).label('good_students'),
        func.sum(case((and_(gpa_subquery.c.gpa >= configs['gpa_average'], gpa_subquery.c.gpa < configs['gpa_good']), 1),
                      else_=0)).label('average_students'),
        func.sum(case((gpa_subquery.c.gpa < configs['gpa_average'], 1), else_=0)).label('weak_students')
    ).select_from(SinhVien).join(gpa_subquery, SinhVien.MaSV == gpa_subquery.c.MaSV, isouter=True)

    # Áp dụng bộ lọc ngành nếu được cung cấp
    if ma_nganh:
        student_stats_query = student_stats_query.join(LopHoc, SinhVien.MaLop == LopHoc.MaLop).filter(
            LopHoc.MaNganh == ma_nganh)

    student_stats = student_stats_query.one_or_none()

    # --- 3. Lấy danh sách Sinh viên cần quan tâm ---
    students_at_risk_query = db.session.query(
        SinhVien.HoTen, gpa_subquery.c.gpa, gpa_subquery.c.credits_debt
    ).join(gpa_subquery, SinhVien.MaSV == gpa_subquery.c.MaSV
           ).filter(
        gpa_subquery.c.gpa < configs['gpa_average']
    ).order_by(gpa_subquery.c.gpa.asc()).limit(5)
    if ma_nganh: students_at_risk_query = students_at_risk_query.join(LopHoc, SinhVien.MaLop == LopHoc.MaLop).filter(
        LopHoc.MaNganh == ma_nganh)
    students_at_risk = students_at_risk_query.all()

    # --- 4. Top các môn có tỷ lệ trượt cao nhất ---
    # ... (Logic này phức tạp và sẽ được triển khai sau, tạm thời trả về dữ liệu giả)
    top_failing_courses = [
        {"TenHP": "Triết học Mác - Lênin", "failure_rate": 15.2},
        {"TenHP": "Giải tích 2", "failure_rate": 12.8}
    ]

    # --- 5. Tổng hợp kết quả ---
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
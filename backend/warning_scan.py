import sqlalchemy as sa
from .models import db, SinhVien, KetQuaHocTap, WarningRule, WarningCase, HocPhan
from datetime import datetime

def scan_all_warnings():
    """
    Quét toàn bộ sinh viên và áp dụng các rule cảnh báo đang active.
    Trả về: {"total_cases": int, "new_cases": int}
    """
    # 1. Lấy danh sách rules
    rules = WarningRule.query.filter_by(Active=True).all()
    if not rules:
        return {"msg": "Không có rule nào được kích hoạt"}

    # 2. Xóa các warning cũ (đang open) của các rule này để tái tạo (hoặc giữ lại tùy business logic)
    # Ở đây chọn cách: Xóa các cảnh báo OPEN cũ của các rule này, sau đó tạo mới dựa trên dữ liệu hiện tại.
    # Để đơn giản và tránh duplicate ngày qua ngày.
    rule_ids = [r.Id for r in rules]
    db.session.query(WarningCase).filter(
        WarningCase.RuleId.in_(rule_ids),
        WarningCase.Status == "open"
    ).delete(synchronize_session=False)

    # 3. Lấy tất cả sinh viên & kết quả học tập
    # Để tối ưu, ta có thể load eager hoặc query aggregate. 
    # Tuy nhiên với số lượng SV nhỏ (< vài ngàn), loop query cũng tạm chấp nhận được.
    # Tốt hơn là query aggregate.

    new_cases_count = 0
    now = datetime.utcnow()

    # Pre-fetch data for "GPA" rules or "Fail Count" rules
    # Tính toán chỉ số cho từng sinh viên
    # a. GPA / Avg Score
    # Lưu ý: Hệ thống dùng DiemHe4 và DiemHe10.
    
    # Query: MaSV, Sum(Diem*TinChi), Sum(TinChi), Count(Fail)
    # Cần logic tính điểm:
    #   - GPA (Hệ 4): Sum(DiemHe4 * SoTinChi) / Sum(SoTinChi)
    #   - AVG (Hệ 10): Sum(DiemHe10 * SoTinChi) / Sum(SoTinChi) (hoặc avg đơn thuần tùy quy chế)
    #   - FAIL: Số môn F (DiemHe10 < 4.0)

    # Query: MaSV, Sum(Diem*TinChi), Sum(TinChi), Count(Fail)
    
    # Sử dụng select statement với join để lấy SoTinChi từ bảng HocPhan
    stmt = sa.select(
        KetQuaHocTap.MaSV, 
        KetQuaHocTap.DiemHe10, 
        KetQuaHocTap.DiemHe4, 
        sa.func.coalesce(KetQuaHocTap.DiemChu, ""),
        HocPhan.SoTinChi
    ).select_from(KetQuaHocTap).join(HocPhan, KetQuaHocTap.MaHP == HocPhan.MaHP)
    
    rows = db.session.execute(stmt).all()

    # Aggregate in memory (python) faster for complex logic than SQL sometimes 
    # Data struct: sv_stats = { 'SV01': { 'sum_p4': 0, 'sum_p10': 0, 'sum_tc': 0, 'fail_cnt': 0, 'fails_credit': 0 } }
    sv_stats = {}

    for masv, d10, d4, dchu, stc in rows:
        if masv not in sv_stats:
            sv_stats[masv] = {'p4':0.0, 'p10':0.0, 'tc':0, 'fails':0, 'fails_credit':0}
        
        stat = sv_stats[masv]
        d10 = d10 or 0.0
        d4 = d4 or 0.0
        stc = int(stc or 0)
        
        stat['tc'] += stc
        stat['p10'] += d10 * stc
        stat['p4'] += d4 * stc
        
        # Fail logic: DiemHe10 < 4.0 or DiemChu = F
        if d10 < 4.0 or dchu == 'F':
            stat['fails'] += 1
            stat['fails_credit'] += stc

    # Apply rules
    cases_to_add = []
    
    for r in rules:
        code = (r.Code or "").upper().strip()
        th = r.Threshold
        
        for masv, stat in sv_stats.items():
            val = 0.0
            is_warn = False
            msg = ""
            
            total_tc = stat['tc']
            if code == "GPA_BELOW":
                # GPA he 4
                val = (stat['p4'] / total_tc) if total_tc > 0 else 0.0
                if val < th:
                    is_warn = True
                    msg = f"GPA tích lũy: {val:.2f} < {th}"
            
            elif code == "AVG_BELOW":
                # AVG he 10
                val = (stat['p10'] / total_tc) if total_tc > 0 else 0.0
                if val < th:
                    is_warn = True
                    msg = f"TBCHT (hệ 10): {val:.2f} < {th}"
            
            elif code == "FAIL_COUNT":
                val = float(stat['fails'])
                if val >= th: # Warning if fails >= threshold
                    is_warn = True
                    msg = f"Số môn nợ: {int(val)} >= {int(th)}"
            
            elif code == "DEBT_OVER":
                # Logic nợ tín chỉ: Tổng tín chỉ của các môn bị F (chưa qua)
                # Fail logic: DiemHe10 < 4.0 or DiemChu = F
                # Cần tính tổng tín chỉ fails
                fails_credit = 0
                # Cần loop lại chi tiết môn học để tính chính xác (hoặc tính trong loop ban đầu)
                # Đoạn code trên chỉ đếm số môn fails (fails count).
                # Ta cần sửa logic gom nhóm ban đầu để tính fails_credit
                val = float(stat.get('fails_credit', 0))
                if val >= th:
                    is_warn = True
                    # msg = f"Nợ tín chỉ: {int(val)} >= {int(th)}" # Model không có Message

            if is_warn:
                cases_to_add.append(WarningCase(
                    RuleId=r.Id,
                    MaSV=masv,
                    Value=round(val, 2),
                    Level="warning",
                    # Message=msg, # Bỏ vì model chưa có field này
                    Status="open",
                    CreatedAt=now
                ))
                new_cases_count += 1

    if cases_to_add:
        db.session.add_all(cases_to_add)
        db.session.commit()

    return {"ok": True, "created": new_cases_count}

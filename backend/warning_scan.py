import sqlalchemy as sa
from .models import db, SinhVien, KetQuaHocTap, WarningRule, WarningCase, HocPhan
from datetime import datetime

def scan_all_warnings():
    
    
    rules = WarningRule.query.filter_by(Active=True).all()
    if not rules:
        return {"msg": "Không có rule nào được kích hoạt"}
    rule_ids = [r.Id for r in rules]
    db.session.query(WarningCase).filter(
        WarningCase.RuleId.in_(rule_ids),
        WarningCase.Status == "open"
    ).delete(synchronize_session=False)

    new_cases_count = 0
    now = datetime.utcnow()
    stmt = sa.select(
        KetQuaHocTap.MaSV, 
        KetQuaHocTap.DiemHe10, 
        KetQuaHocTap.DiemHe4, 
        sa.func.coalesce(KetQuaHocTap.DiemChu, ""),
        HocPhan.SoTinChi
    ).select_from(KetQuaHocTap).join(HocPhan, KetQuaHocTap.MaHP == HocPhan.MaHP)
    
    rows = db.session.execute(stmt).all()
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

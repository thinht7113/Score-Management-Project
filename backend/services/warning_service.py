from sqlalchemy import func, case
from ..models import db, SystemConfig, WarningRule, WarningCase, KetQuaHocTap, HocPhan, SinhVien

def _ensure_warning_rule(code: str, name: str, threshold: float) -> WarningRule:
    r = WarningRule.query.filter_by(Code=code).first()
    if r:
        return r
    r = WarningRule(Code=code, Name=name, Threshold=float(threshold), Active=True, Desc=None)
    db.session.add(r)
    db.session.commit()
    return r

def scan_warnings(ma_lop=None):
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

    if ma_lop:
        q = q.filter(SinhVien.MaLop == ma_lop)

    affected = 0
    # Optimization: Fetch existing open cases to avoid N+1 queries for existence check
    # But for now, let's just use the loop as it is not too bad if cases are few.
    # Actually, we can just query all open cases for these rules.

    # Let's keep it simple and close to original for now, but improved structure.

    for masv, hoten, gpa4, debttc in q.all():
        gpa4 = float(gpa4 or 0.0)
        debttc = float(debttc or 0.0)

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
    return affected

# student/data/frames.py
from __future__ import annotations
import pandas as pd
import numpy as np

def _col(df: pd.DataFrame, name: str, dtype="float64"):
    return df[name] if name in df.columns else pd.Series(index=df.index, dtype=dtype)

def _keyify_hp(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.upper().str.replace(r"\s+", "", regex=True)

def _fmt_bool(s: pd.Series, default=True) -> pd.Series:
    try:
        return s.fillna(default).astype(bool)
    except Exception:
        return pd.Series([default] * len(s), index=s.index, dtype="bool")

def from_student_payload(payload: dict):
    payload = payload or {}

    g = pd.DataFrame(payload.get("KetQuaHocTap") or [])
    g["MaHP"]      = _col(g, "MaHP", dtype="object")
    g["MaHP_key"]  = _keyify_hp(g["MaHP"])
    g["TenHP"]     = _col(g, "TenHP", dtype="object")
    g["SoTinChi"]  = pd.to_numeric(_col(g, "SoTinChi"), errors="coerce").fillna(0).astype(int)
    g["DiemHe10"]  = pd.to_numeric(_col(g, "DiemHe10"), errors="coerce")
    g["DiemHe4"]   = pd.to_numeric(_col(g, "DiemHe4"),  errors="coerce")
    g["HocKy_raw"] = pd.to_numeric(_col(g, "HocKy"),    errors="coerce")
    g["TinhDiemTichLuy"] = _fmt_bool(g["TinhDiemTichLuy"]) if "TinhDiemTichLuy" in g.columns else True

    p = pd.DataFrame(
        payload.get("ChuongTrinhDaoTao")
        or payload.get("LoTrinh")
        or payload.get("Curriculum")
        or []
    )
    if not p.empty:
        p["MaHP"]      = _col(p, "MaHP", dtype="object")
        p["MaHP_key"]  = _keyify_hp(p["MaHP"])
        p["TenHP"]     = _col(p, "TenHP", dtype="object")
        p["SoTinChi"]  = pd.to_numeric(_col(p, "SoTinChi"), errors="coerce").fillna(0).astype(int)
        p_hk           = pd.to_numeric(_col(p, "HocKy"),   errors="coerce")
        p_hk_goiy      = pd.to_numeric(_col(p, "HKGoiY"),  errors="coerce")
        p["HocKy"]     = p_hk.fillna(p_hk_goiy)
        # map kỳ từ CTDT theo MaHP_key
        hk_map = p.dropna(subset=["MaHP_key", "HocKy"]).set_index("MaHP_key")["HocKy"]
        g["HocKy_CTDT"] = g["MaHP_key"].map(hk_map)
    else:
        g["HocKy_CTDT"] = pd.Series(index=g.index, dtype="float64")

    g["HocKy"] = g["HocKy_CTDT"].where(g["HocKy_CTDT"].notna(), g["HocKy_raw"])

    profile = {k: v for k, v in payload.items()
               if k not in ("KetQuaHocTap", "ChuongTrinhDaoTao", "LoTrinh", "Curriculum")}

    return g, p, profile

def gpa10(df: pd.DataFrame) -> float:
    if df is None or df.empty: return 0.0
    d = df[(df.get("TinhDiemTichLuy", True) == True) & df["DiemHe10"].notna() & (df["SoTinChi"] > 0)]
    if d.empty: return 0.0
    return float((d["DiemHe10"] * d["SoTinChi"]).sum() / d["SoTinChi"].sum())

def gpa4_from10(x):
    if x is None or (isinstance(x, float) and np.isnan(x)): return np.nan
    v = float(x)
    if v >= 8.5: return 4.0
    if v >= 8.0: return 3.5
    if v >= 7.0: return 3.0
    if v >= 6.0: return 2.5
    if v >= 5.0: return 2.0
    if v >= 4.0: return 1.5
    return 0.0

def credits(df: pd.DataFrame):
    if df is None or df.empty: return (0, 0, 0)
    d = df[df.get("TinhDiemTichLuy", True) == True]
    passed = d[(d["DiemHe10"].notna()) & (d["DiemHe10"] >= 4.0)]["SoTinChi"].sum()
    debt   = d[(d["DiemHe10"].notna()) & (d["DiemHe10"] <  4.0)]["SoTinChi"].sum()
    total  = d["SoTinChi"].sum()
    return int(passed), int(debt), int(total)

def gpa_by_semester(df: pd.DataFrame):
    if df is None or df.empty: return []
    d = df[(df["HocKy"].notna()) & (df["DiemHe10"].notna()) & (df["SoTinChi"] > 0)]
    if d.empty: return []
    wsum = (d["DiemHe10"] * d["SoTinChi"]).groupby(d["HocKy"]).sum()
    csum = d["SoTinChi"].groupby(d["HocKy"]).sum()
    g = (wsum / csum).astype(float).sort_index()
    return [(int(k), float(round(v, 2))) for k, v in g.items()]

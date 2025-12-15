from io import BytesIO
import math
import re
import pandas as pd
from unicodedata import normalize as ucnorm

def _norm(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = ucnorm("NFKD", s).encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"\s+", " ", s).strip().lower()

def parse_decimal_vn(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    s = str(x).strip()
    if s == "":
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def he10_to_he4(d10):
    if d10 is None:
        return None
    try:
        d10 = float(d10)
    except Exception:
        return None
    return round(d10 * 0.4, 2)

def he4_to_chu(d4):
    if d4 is None:
        return None
    if d4 >= 3.7: return "A"
    if d4 >= 3.2: return "B+"
    if d4 >= 2.7: return "B"
    if d4 >= 2.3: return "C+"
    if d4 >= 2.0: return "C"
    if d4 >= 1.5: return "D+"
    if d4 >= 1.0: return "D"
    return "F"

def read_excel_from_request(flask_request, field_name="file"):
    if field_name not in flask_request.files:
        raise ValueError("Thiếu file (multipart field 'file').")
    f = flask_request.files[field_name]
    raw = f.read()
    if not raw:
        raise ValueError("File rỗng.")
    name = (f.filename or "").lower()
    bio = BytesIO(raw)
    if name.endswith(".csv"):
        return pd.read_csv(bio)
    return pd.read_excel(bio, sheet_name=0, header=None)

def clean_header_rows(df: pd.DataFrame, header_row_idx: int | None = None) -> pd.DataFrame:
    hints = {"masv", "mssv", "ma sv", "mã sv", "mã sinh viên", "hoc ky", "học kỳ",
             "ten hp", "tên học phần", "mahp", "mã hp", "diem", "điểm"}
    choose = None
    limit = min(10, len(df))
    for i in range(limit):
        vals = [str(x).strip() for x in df.iloc[i].tolist()]
        normed = { _norm(v) for v in vals if v }
        if normed & hints:
            choose = i
            break
    if choose is None:
        best, best_i = -1, 0
        for i in range(limit):
            score = sum(1 for v in df.iloc[i].tolist() if str(v).strip())
            if score > best:
                best, best_i = score, i
        choose = best_i

    df.columns = [str(x).strip() for x in df.iloc[choose]]
    df = df.iloc[choose+1:].reset_index(drop=True)
    return df


def guess_grades_format(df: pd.DataFrame):
    cols = [_norm(c) for c in df.columns]
    has_masv = "masv" in cols
    has_subj_col = any(c in cols for c in ["mahp", "tenhp"])
    has_score_col = any(c in cols for c in ["diem", "diemhe10", "diemhe4"])
    if has_masv and has_subj_col and has_score_col:
        return "TALL"

    fixed = {"masv", "hoten", "lop", "nganh", "hocky", "diem", "diemhe10", "diemhe4"}
    unknown_cols = [c for c in cols if c not in fixed]
    if has_masv and len(unknown_cols) >= 2:
        return "WIDE"

    return "UNKNOWN"
_COL_ALIASES = {
    "masv": {"ma sv", "mssv", "mã sv", "ma so sv", "student id", "ma sinh vien", "mã sinh viên"},
    "hoten": {"ho ten","họ tên","họ và tên","ten","name","ho va ten"},
    "lop": {"lop","lớp","lớp học","class","ma lop","mã lớp","ma_lop"},
    "nganh": {"nganh","ngành","mã ngành","ma nganh","major"},
    "mahp": {"ma hp", "mamh", "ma mon", "mã hp", "mã học phần", "ma hoc phan"},
    "tenhp": {"ten hp", "mon", "ten mon", "tên môn", "hoc phan", "ten hoc phan", "tên học phần"},
    "hocky": {"hoc ky", "học kỳ", "hk", "term", "semester"},
    "diem": {"diem", "diem tk", "diem tong ket", "điểm tổng kết", "tk(10)", "tk 10", "final", "score", "diem he10", "diemhe10", "he10"},
    "diemhe4": {"diem he4", "diemhe4", "gpa4", "he4"},
}

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for c in df.columns:
        nc = _norm(c)
        found = None
        for std, aliases in _COL_ALIASES.items():
            if nc == std or nc in aliases:
                found = std; break
        mapping[c] = found or c
    df = df.rename(columns=mapping)
    return df

def suggest_subject_alias(raw_name: str, list_hp: list[tuple[str, str]]):
    name = _norm(raw_name)
    best = None; best_score = 0
    for mahp, tenhp in list_hp:
        for cand in (mahp, tenhp):
            candn = _norm(cand)
            score = len(set(name.split()) & set(candn.split()))
            if score > best_score:
                best_score = score; best = (mahp, tenhp)
    return best if best_score >= 1 else None

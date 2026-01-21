# backend/utils_import/excel_utils.py
import io
import pandas as pd
import unicodedata
import re
import math
from datetime import datetime, timedelta
from flask import request

def get_file_df():
    f = request.files.get("file")
    if not f:
        raise ValueError("Thiếu file (form field 'file')")
    filename = f.filename or "upload.xlsx"
    content = f.read()
    buf = io.BytesIO(content)
    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(buf)
        else:
            df = pd.read_excel(buf, dtype=str)
    except Exception as e:
        raise ValueError(f"Lỗi đọc file: {e}")
    return df, filename

def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()

def norm_key(s: str) -> str:
    s = norm_text(s)
    s = re.sub(r'[\s\u00A0\u200B-\u200D\uFEFF]+', '', s)
    for ch in (" ", "_", "-", ".", "/"):
        s = s.replace(ch, "")
    return s

def parse_date(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=float(v))).date()
        except Exception:
            pass
    dt = pd.to_datetime(str(v).replace("-", "/"), dayfirst=True, errors="coerce")
    return None if pd.isna(dt) else dt.date()

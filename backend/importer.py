# backend/importer.py
from __future__ import annotations
import io
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity
from numpy import select
from passlib.hash import bcrypt
from sqlalchemy import func
from difflib import SequenceMatcher
from .models import (
    db,
    HocPhan, LopHoc, NganhHoc,
    NguoiDung, VaiTro,
    SinhVien, KetQuaHocTap,
    SystemConfig, ImportLog, GradeAuditLog,ChuongTrinhDaoTao
)


@dataclass
class ImportSummary:
    rows_seen: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[Dict[str, Any]] = None
    suggestions: List[str] = None
    sample_rows: List[Dict[str, Any]] = None
    detected_format: Optional[str] = None  # TALL|WIDE|None

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)



def _actor_id() -> int:
    try:
        ident = get_jwt_identity()
        return int(ident) if ident is not None else 0
    except Exception:
        return 0


def _get_file_df() -> Tuple[pd.DataFrame, str]:
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


def _audit_import(*, endpoint: str, affected: str, summary: Dict[str, Any], filename: Optional[str] = None):
    try:
        actor = get_jwt_identity() or ""
    except Exception:
        actor = ""
    try:
        log = ImportLog(
            When=datetime.utcnow(),
            Actor=str(actor),
            Endpoint=endpoint,
            Params=json.dumps(request.args.to_dict(), ensure_ascii=False),
            Filename=filename,
            Summary=json.dumps(summary, ensure_ascii=False),
            AffectedTable=affected,
            InsertedIds=None,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _ensure_student_user(masv: str, email_domain: str) -> int:
    u = NguoiDung.query.filter_by(TenDangNhap=masv).first()
    if u:
        return u.MaNguoiDung
    vr = VaiTro.query.filter_by(TenVaiTro="Sinh viên").first()
    u = NguoiDung(
        TenDangNhap=masv,
        MatKhauMaHoa=bcrypt.hash(masv),
        Email=f"{masv}@{email_domain}",
        TrangThai="Hoạt động",
        MaVaiTro=vr.MaVaiTro if vr else None,
    )
    db.session.add(u); db.session.flush()
    return u.MaNguoiDung


def _retake_apply_policy(masv: str, mahp: str, new_rec: KetQuaHocTap, policy: str = "keep-latest"):
    policy = (policy or "keep-latest").strip().lower()
    existing = KetQuaHocTap.query.filter_by(MaSV=masv, MaHP=mahp).order_by(KetQuaHocTap.MaKQ.asc()).all()
    if not existing:
        new_rec.LaDiemCuoiCung = True
        return
    if policy == "best":
        all_recs = existing + [new_rec]
        best = max(all_recs, key=lambda r: (r.DiemHe4 or 0.0, r.HocKy or ""))
        for r in all_recs:
            r.LaDiemCuoiCung = (r is best)
    else:
        for r in existing:
            r.LaDiemCuoiCung = False
        new_rec.LaDiemCuoiCung = True



def import_curriculum(*, preview: bool = True, allow_update: bool = True, replace: bool = False):

    ma_nganh = (request.args.get("manganh") or "").strip().upper()
    if not ma_nganh:
        return jsonify({"msg": "Thiếu tham số 'manganh'."}), 400

    if request.args.get("preview") is not None:
        preview = str(request.args.get("preview")).lower() in ("1", "true", "yes", "y")
    if request.args.get("replace") is not None:
        replace = str(request.args.get("replace")).lower() in ("1", "true", "yes", "y")

    ng = db.session.get(NganhHoc, ma_nganh)
    if not ng:
        return jsonify({"msg": f"Ngành '{ma_nganh}' không tồn tại."}), 400

    try:
        df, filename = _get_file_df()
    except NameError:
        f = request.files.get("file")
        if not f:
            return jsonify({"msg": "Thiếu file upload (form field 'file')."}), 400
        filename = f.filename
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(f)
        else:
            df = pd.read_csv(f)
    except Exception as e:
        return jsonify({"msg": f"Lỗi đọc file: {e}"}), 400

    import re, unicodedata
    def _norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", str(s or ""))
        s = "".join(c for c in s if not unicodedata.combining(c))
        s = re.sub(r"\s+", "", s.lower())
        return s

    colmap = {_norm(c): c for c in df.columns}

    def _col(*aliases):
        for a in aliases:
            key = _norm(a)
            if key in colmap:
                return colmap[key]
        return None

    col_ma  = _col("Mã học phần", "mahp", "mãhp", "mamon", "mahocphan", "ma_mon")
    col_ten = _col("Tên học phần", "tenhp", "tênhp", "tenmon", "tenhocphan", "ten_mon")
    col_hk  = _col("Kỳ thứ", "kithu", "kythu", "hocky", "học kỳ", "hk")
    col_stc = _col("Số tín chỉ", "sotinchi", "stc", "so tc", "so_tin_chi")

    if not (col_ma and col_ten and col_hk and col_stc):
        return jsonify({"msg": "Thiếu cột bắt buộc: 'Mã học phần','Tên học phần','Kỳ thứ','Số tín chỉ'."}), 400

    df = df.copy()
    df["_rowno"] = df.index + 2
    df[col_ma]  = df[col_ma].astype(str).str.strip().str.upper()
    df[col_ten] = df[col_ten].astype(str).str.strip()

    df = df[(df[col_ma] != "") & (df[col_ten] != "")]
    df = df.drop_duplicates(subset=[col_ma], keep="last")

    if replace:
        db.session.query(ChuongTrinhDaoTao).filter(
            ChuongTrinhDaoTao.MaNganh == ma_nganh
        ).delete(synchronize_session=False)

    hp_by_code = {x.MaHP: x for x in db.session.execute(select(HocPhan)).scalars().all()}
    ct_by_key  = {(x.MaNganh, x.MaHP): x for x in db.session.execute(
                    select(ChuongTrinhDaoTao).where(ChuongTrinhDaoTao.MaNganh == ma_nganh)
                  ).scalars().all()}

    stats = {
        "rows": int(df.shape[0]),
        "hp_inserted": 0, "hp_updated": 0,
        "ct_inserted": 0, "ct_updated": 0,
        "skipped": 0, "errors": []
    }

    for _, row in df.iterrows():
        mahp  = row[col_ma]
        tenhp = row[col_ten]
        rowno = int(row["_rowno"])

        try:
            hk = int(str(row[col_hk]).strip())
        except Exception:
            stats["skipped"] += 1
            stats["errors"].append({"row": rowno, "error": "Kỳ thứ không hợp lệ"})
            continue

        try:
            stc = int(str(row[col_stc]).strip())
        except Exception:
            stats["skipped"] += 1
            stats["errors"].append({"row": rowno, "error": "Số tín chỉ không hợp lệ"})
            continue

        hp = hp_by_code.get(mahp)
        if hp is None:
            hp = HocPhan(MaHP=mahp, TenHP=tenhp, SoTinChi=stc, TinhDiemTichLuy=True)
            db.session.add(hp)
            hp_by_code[mahp] = hp
            stats["hp_inserted"] += 1
        else:
            if allow_update:
                changed = False
                if hp.TenHP != tenhp:
                    hp.TenHP = tenhp; changed = True
                if hp.SoTinChi != stc:
                    hp.SoTinChi = stc; changed = True
                if changed:
                    stats["hp_updated"] += 1

        ct = ct_by_key.get((ma_nganh, mahp))
        if ct is None:
            ct = ChuongTrinhDaoTao(MaNganh=ma_nganh, MaHP=mahp, HocKy=hk, LaMonBatBuoc=True)
            db.session.add(ct)
            ct_by_key[(ma_nganh, mahp)] = ct
            stats["ct_inserted"] += 1
        else:
            if allow_update and ct.HocKy != hk:
                ct.HocKy = hk
                stats["ct_updated"] += 1

    if preview:
        db.session.rollback()
    else:
        db.session.commit()

    try:
        _audit_import(
            endpoint="/api/admin/import/curriculum",
            affected="HocPhan,ChuongTrinhDaoTao",
            summary=stats, filename=filename
        )
    except Exception:
        pass

    return jsonify({
        "file": filename,
        "manganh": ma_nganh,
        "preview": preview,
        "replace": replace,
        **stats
    }), 200

def import_class_roster(*, preview: bool = True, allow_update: bool = True):

    import io, math, unicodedata
    from datetime import datetime, timedelta
    import pandas as pd
    from flask import request, jsonify
    from passlib.hash import bcrypt

    HEADER_TOKENS = {
        "masinhvien": {"masinhvien", "ma sinh vien", "masv", "mssv", "studentid", "id", "mã sinh viên"},
        "hovaten": {"hovaten", "ho va ten", "hoten", "ten", "fullname", "name", "họ và tên"},
        "ngaysinh": {"ngaysinh", "ngay sinh", "dob", "dateofbirth", "ngày sinh"},
        "noisinh": {"noisinh", "noi sinh", "quequan", "que quan", "birthplace", "nơi sinh"},
    }


    def _is_header_like(masv_txt: str, hoten_txt: str, ngs_raw: str, nois_txt: str) -> bool:
        m = _norm_key(masv_txt or "")
        h = _norm_key(hoten_txt or "")
        d = _norm_key(ngs_raw or "")
        n = _norm_key(nois_txt or "")
        return (
                m in HEADER_TOKENS["masinhvien"] or
                h in HEADER_TOKENS["hovaten"] or
                d in HEADER_TOKENS["ngaysinh"] or
                n in HEADER_TOKENS["noisinh"]
        )
    def _norm_text(s: str) -> str:
        s = unicodedata.normalize("NFKD", s or "")
        s = "".join(c for c in s if not unicodedata.combining(c))
        return s.strip().lower()

    def _norm_key(s: str) -> str:
        s = _norm_text(s)
        for ch in (" ", "_", "-", ".", "/"):
            s = s.replace(ch, "")
        return s

    def _parse_date(v):
        if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "":
            return None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            try:
                return (datetime(1899, 12, 30) + timedelta(days=float(v))).date()
            except Exception:
                pass
        dt = pd.to_datetime(str(v).replace("-", "/"), dayfirst=True, errors="coerce")
        return None if pd.isna(dt) else dt.date()

    def _email_domain() -> str:
        row = db.session.get(SystemConfig, "EMAIL_DOMAIN")
        return row.ConfigValue if row else "vui.edu.vn"

    def _ensure_role_sinhvien_id():
        r = db.session.query(VaiTro).filter(VaiTro.TenVaiTro.in_(["SinhVien", "Sinh Viên", "student"])).first()
        if not r:
            r = VaiTro(TenVaiTro="SinhVien"); db.session.add(r); db.session.flush()
        return r.MaVaiTro

    def _ensure_user_for_sv(masv: str, email_domain: str) -> int:
        u = db.session.query(NguoiDung).filter_by(TenDangNhap=masv).first()
        if u: return u.MaNguoiDung
        u = NguoiDung(
            TenDangNhap=masv,
            MatKhauMaHoa=bcrypt.hash(masv),
            Email=f"{masv}@{email_domain}".lower(),
            TrangThai="Hoạt động",
            MaVaiTro=_ensure_role_sinhvien_id(),
        )
        db.session.add(u); db.session.flush()
        return u.MaNguoiDung

    lop = (request.args.get("lop") or "").strip().upper()
    if not lop:
        payload = {
            "summary": {"total_rows": 0, "created": 0, "updated": 0, "skipped": 0,
                        "warnings": ["Thiếu tham số 'lop' trên URL"]},
            "preview": [], "warnings": ["Thiếu tham số 'lop' trên URL"], "file": None
        }
        return jsonify(payload), 400

    lop_row = db.session.get(LopHoc, lop)
    if not lop_row:
        payload = {
            "summary": {"total_rows": 0, "created": 0, "updated": 0, "skipped": 0,
                        "warnings": [f"Lớp '{lop}' chưa tồn tại trong Danh mục → hãy tạo trước."]},
            "preview": [], "warnings": [f"Lớp '{lop}' chưa tồn tại trong Danh mục → hãy tạo trước."], "file": None
        }
        return jsonify(payload), 400

    if "file" not in request.files or not request.files["file"].filename:
        payload = {
            "summary": {"total_rows": 0, "created": 0, "updated": 0, "skipped": 0,
                        "warnings": ["Chưa chọn tệp để nhập"]},
            "preview": [], "warnings": ["Chưa chọn tệp để nhập"], "file": None
        }
        return jsonify(payload), 400

    up = request.files["file"]; fname = up.filename; raw = up.read()
    try:
        if fname.lower().endswith(".csv"):
            df = pd.read_csv(io.BytesIO(raw), dtype=object, encoding="utf-8")
        else:
            df = pd.read_excel(io.BytesIO(raw), dtype=object)
    except Exception as e:
        payload = {
            "summary": {"total_rows": 0, "created": 0, "updated": 0, "skipped": 0,
                        "warnings": [f"Lỗi đọc file: {e}"]},
            "preview": [], "warnings": [f"Lỗi đọc file: {e}"], "file": fname
        }
        return jsonify(payload), 400

    cols = { _norm_key(c): c for c in df.columns }
    need_map = {
        "masinhvien": ["mã sinh viên","masinhvien","ma sinh vien","masv","mssv","studentid","id"],
        "hovaten":    ["họ và tên","hovaten","ho va ten","hoten","ten","fullname","name"],
        "ngaysinh":   ["ngày sinh","ngaysinh","ngay sinh","ns","dob","dateofbirth"],
        "noisinh":    ["nơi sinh","noisinh","noi sinh","quequan","que quan","birthplace"],
    }
    resolved = {}
    for key, aliases in need_map.items():
        for a in aliases:
            k = _norm_key(a)
            if k in cols: resolved[key] = cols[k]; break

    missing = [k for k in need_map if k not in resolved]
    if missing:
        label = {"masinhvien":"Mã sinh viên","hovaten":"Họ và tên","ngaysinh":"Ngày sinh","noisinh":"Nơi sinh"}
        warn = [f"Thiếu cột: {', '.join(label[m] for m in missing)}"]
        payload = {"summary":{"total_rows":0,"created":0,"updated":0,"skipped":0,"warnings":warn},
                   "preview":[], "warnings":warn, "file": fname}
        return jsonify(payload), 400

    email_domain = _email_domain()

    total=0; created=0; updated=0; skipped=0
    warnings=[]; preview_rows=[]

    for i, row in df.iterrows():
        masv = str(row[resolved["masinhvien"]]).strip() if pd.notna(row[resolved["masinhvien"]]) else ""
        hoten = str(row[resolved["hovaten"]]).strip() if pd.notna(row[resolved["hovaten"]]) else ""
        ngs_raw = str(row[resolved["ngaysinh"]]).strip() if pd.notna(row[resolved["ngaysinh"]]) else ""
        nois = str(row[resolved["noisinh"]]).strip() if pd.notna(row[resolved["noisinh"]]) else ""

        if _is_header_like(masv, hoten, ngs_raw, nois):
            skipped += 1
            warnings.append(f"Dòng {i + 2}: bỏ qua vì trùng tiêu đề cột")
            continue

        ngs = _parse_date(ngs_raw) if ngs_raw else None

        if not masv and not hoten:
            continue
        total += 1

        if not masv or not hoten:
            skipped += 1
            warnings.append(f"Dòng {i+2}: Thiếu Mã SV hoặc Họ tên")
            continue

        uid = _ensure_user_for_sv(masv, email_domain)
        sv = db.session.get(SinhVien, masv)
        if not sv:
            sv = SinhVien(MaSV=masv, HoTen=hoten, NgaySinh=ngs, NoiSinh=nois, MaLop=lop, MaNguoiDung=uid)
            if hasattr(SinhVien, "Lop"): setattr(sv, "Lop", lop)
            db.session.add(sv); created += 1
        else:
            changed = False
            if allow_update:
                if hoten and sv.HoTen != hoten: sv.HoTen = hoten; changed = True
                if ngs and getattr(sv, "NgaySinh", None) != ngs: sv.NgaySinh = ngs; changed = True
                if nois is not None and getattr(sv, "NoiSinh", None) != nois: sv.NoiSinh = nois; changed = True
                if hasattr(SinhVien, "MaLop") and getattr(sv, "MaLop", None) != lop:
                    sv.MaLop = lop; changed = True
                if hasattr(SinhVien, "Lop") and getattr(sv, "Lop", None) != lop:
                    sv.Lop = lop; changed = True
            if changed: updated += 1
            else: skipped += 1

        if len(preview_rows) < 10:
            preview_rows.append({
                "Mã sinh viên": masv,
                "Họ và tên": hoten,
                "Ngày sinh": (ngs.isoformat() if ngs else None),
                "Nơi sinh": nois,
                "Tên lớp (chọn)": lop,
            })

    summary = {"total_rows": total, "created": created, "updated": updated, "skipped": skipped, "warnings": warnings}

    if preview:
        db.session.rollback()
        return jsonify({"summary": summary, "preview": preview_rows, "warnings": warnings, "file": fname}), 200

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        summary["warnings"].append(f"Lỗi commit DB: {e}")
        return jsonify({"summary": summary, "preview": preview_rows, "warnings": summary["warnings"], "file": fname}), 400

    try:
        db.session.add(ImportLog(Endpoint="/api/admin/import/class-roster",
                                 Summary=json.dumps(summary, ensure_ascii=False),
                                 Filename=fname, AffectedTable="SinhVien"))
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({"summary": summary, "preview": preview_rows, "warnings": warnings, "file": fname}), 200


def import_grades(*, preview: bool = True,
                  allow_update: bool = True,
                  hoc_ky_default: str | None = None,
                  retake_policy: str = "keep-latest"):

    import re, unicodedata, math
    import pandas as pd
    from flask import request, jsonify
    from passlib.hash import bcrypt
    from decimal import Decimal, ROUND_HALF_UP
    EPS = Decimal("0.05")
    tbc_policy = (request.args.get("tbc_policy") or "calc_only").strip().lower()

    def _norm_subject_name(s: str) -> str:
        s = _norm_key(str(s))
        s = re.sub(r'^(diem|diemmon|mon|hp|hocphan|tbc|tbcht|tbcht4|gpa|xeploai)+', '', s)
        s = re.sub(r'\(.*?\)', '', s)
        s = re.sub(r'(lan|thi|hk)\d+$', '', s)
        s = re.sub(r'_{2,}', '_', s).strip('_')
        s = s.replace('lt', 'laptrinh')  # 'LT C' -> 'laptrinhc'
        return s
    def _fuzzy_pick_subject(key_norm: str, by_ten: dict, threshold: float = 0.78):
        best, score = None, 0.0
        for k, h in by_ten.items():
            overlap = len(set(k.split('_')) & set(key_norm.split('_')))
            r = SequenceMatcher(a=k, b=key_norm).ratio() + overlap * 0.05
            if r > score:
                best, score = h, r
        return best if score >= threshold else None

    def _is_meta_header(key_norm: str) -> bool:
        if key_norm in {'stt', 'masv', 'mssv', 'hovaten', 'hoten', 'ngaysinh', 'noisinh', 'tenlop', 'lop',
                        'tbcht10', 'tbhk', 'sohpno', 'sotcno', 'ngaytonghop', 'nguoitonghop'}:
            return True
        if re.match(r'^(tbc|tbcht|tbcht4|gpa|xeploai|xeploai10|xeploai4)$', key_norm):
            return True
        if 'tbc' in key_norm or 'ht4' in key_norm or 'xeploai' in key_norm or 'thang10' in key_norm or 'thang4' in key_norm:
            return True
        return False

    def _norm_text(s: str) -> str:
        s = unicodedata.normalize("NFKD", s or "")
        s = "".join(c for c in s if not unicodedata.combining(c))
        return s.strip().lower()
    def _norm_key(s: str) -> str:
        s = _norm_text(s)
        s = re.sub(r'[\s\u00A0\u200B-\u200D\uFEFF]+', '', s)
        for ch in ("_", "-", ".", "/"):
            s = s.replace(ch, "")
        return s

    def _num_2(x) -> float | None:
        if x is None:
            return None
        s = str(x).strip()
        if s == "":
            return None
        s = s.replace(",", ".")
        s = re.sub(r"[^0-9.\-]", "", s)
        try:
            v = Decimal(s)
        except Exception:
            try:
                v = Decimal(str(float(s)))
            except Exception:
                return None
        return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def _parse_date(v):
        if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "":
            return None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            from datetime import datetime, timedelta
            try: return (datetime(1899,12,30)+timedelta(days=float(v))).date()
            except Exception: pass
        dt = pd.to_datetime(str(v).replace("-","/"), dayfirst=True, errors="coerce")
        return None if pd.isna(dt) else dt.date()

    def _grade_letter(v: float) -> tuple[str, float, str]:
        if v >= 8.5:   return "A", 4.0, "Đạt"
        if v >= 7.8:   return "B+", 3.5, "Đạt"
        if v >= 7.0:   return "B",  3.0, "Đạt"
        if v >= 6.3:   return "C+", 2.5, "Đạt"
        if v >= 5.5:   return "C",  2.0, "Đạt"
        if v >= 4.8:   return "D+", 1.5, "Đạt"
        if v >= 4.0:   return "D",  1.0, "Đạt"
        return "F", 0.0, "Không đạt"

    def _email_domain() -> str:
        row = db.session.get(SystemConfig, "EMAIL_DOMAIN")
        return row.ConfigValue if row else "vui.edu.vn"

    def _ensure_role_sinhvien_id():
        r = db.session.query(VaiTro).filter(VaiTro.TenVaiTro.in_(["SinhVien","Sinh Viên","student"])).first()
        if not r:
            r = VaiTro(TenVaiTro="SinhVien"); db.session.add(r); db.session.flush()
        return r.MaVaiTro

    def _ensure_user_and_student(masv: str, ho_ten: str|None, ngay_sinh, noi_sinh, lop: str|None):
        u = db.session.query(NguoiDung).filter_by(TenDangNhap=masv).first()
        if not u:
            u = NguoiDung(TenDangNhap=masv, MatKhauMaHoa=bcrypt.hash(masv),
                          Email=f"{masv}@{_email_domain()}".lower(),
                          TrangThai="Hoạt động", MaVaiTro=_ensure_role_sinhvien_id())
            db.session.add(u); db.session.flush()
        sv = db.session.get(SinhVien, masv)
        if not sv:
            sv = SinhVien(MaSV=masv, HoTen=(ho_ten or masv), MaNguoiDung=u.MaNguoiDung)
            if ngay_sinh: setattr(sv, "NgaySinh", ngay_sinh)
            if noi_sinh is not None: setattr(sv, "NoiSinh", noi_sinh)
            if lop:
                if hasattr(SinhVien,"MaLop"): setattr(sv,"MaLop",lop)
                if hasattr(SinhVien,"Lop"):   setattr(sv,"Lop",lop)
            db.session.add(sv)

    def _hp_lookup_builder():
        all_hp = db.session.query(HocPhan).all()
        by_ma = {(h.MaHP or "").strip().upper(): h for h in all_hp}
        by_ten = {_norm_subject_name(h.TenHP or ""): h for h in all_hp if h.TenHP}
        return by_ma, by_ten

    def _build_ctdt_hocky_map_for_lop(lop_code: str) -> dict[str, int]:
        if not lop_code:
            return {}
        lop_row = db.session.get(LopHoc, lop_code)
        if not lop_row or not getattr(lop_row, "MaNganh", None):
            return {}
        ma_nganh = lop_row.MaNganh
        rows = (
            db.session.query(ChuongTrinhDaoTao.MaHP, func.min(ChuongTrinhDaoTao.HocKy))
            .filter(ChuongTrinhDaoTao.MaNganh == ma_nganh)
            .group_by(ChuongTrinhDaoTao.MaHP)
            .all()
        )
        return {mahp: (int(hk) if hk is not None else None) for (mahp, hk) in rows}

    lop = (request.args.get("lop") or "").strip().upper()
    if lop and not db.session.get(LopHoc, lop):
        return jsonify({"summary":{"total_rows":0,"created":0,"updated":0,"skipped":0,
                                   "warnings":[f"Lớp '{lop}' chưa tồn tại trong Danh mục → hãy tạo trước."]},
                        "preview":[], "warnings":[f"Lớp '{lop}' chưa tồn tại trong Danh mục → hãy tạo trước."], "file":None}), 400

    ctdt_map = _build_ctdt_hocky_map_for_lop(lop)

    try:
        df, fname = _get_file_df()
    except Exception as e:
        return jsonify({"summary":{"total_rows":0,"created":0,"updated":0,"skipped":0,"warnings":[str(e)]},
                        "preview":[], "warnings":[str(e)], "file":None}), 400

    cols_norm = {_norm_key(c): c for c in df.columns}
    alias = {
        "stt": {"stt","so","sott","sothutu"},
        "masv": {"masv","ma sv","mssv","masinhvien","ma sinh vien","id","studentid","mãsinhviên"},
        "hoten": {"hovaten","ho va ten","hoten","ten","fullname","name","họ và tên"},
        "ngaysinh": {"ngaysinh","ngay sinh","dob","dateofbirth","ngày sinh"},
        "noisinh": {"noisinh","noi sinh","quequan","que quan","birthplace","nơi sinh"},
        "tenlop": {"tenlop","ten lop","lop","malop"},
        "tbcht10": {"tbcht10","tbc ht10","tbcht 10","tbc he 10","tbc10","gpa10"},
        "sohpno": {"sohpno","so hp no","somonno","nohp"},
        "sotcno": {"sotinchino","so tin chi no","sotcno","notinchi"},
    }
    def _col(key):
        for a in alias.get(key,set()):
            k=_norm_key(a)
            if k in cols_norm: return cols_norm[k]
        return None

    col_masv  = _col("masv")
    col_hoten = _col("hoten")
    col_ngs   = _col("ngaysinh")
    col_nois  = _col("noisinh")
    col_tb10  = _col("tbcht10")
    col_sohp  = _col("sohpno")
    col_sotc  = _col("sotcno")
    if not col_masv:
        return jsonify({"summary":{"total_rows":0,"created":0,"updated":0,"skipped":0,
                                   "warnings":["Thiếu cột Mã sinh viên"]},
                        "preview":[], "warnings":["Thiếu cột Mã sinh viên"], "file":fname}), 400

    META_KEYS = {
        _norm_key("STT"), _norm_key("Mã sinh viên"), _norm_key("Họ và tên"),
        _norm_key("Ngày sinh"), _norm_key("Nơi sinh"), _norm_key("Tên lớp"),
        _norm_key("TBC HT10"), _norm_key("Số HP nợ"), _norm_key("Số tín chỉ nợ"),
        _norm_key("Ngày tổng hợp"), _norm_key("Người tổng hợp")
    }
    for k in ("stt", "masv", "hoten", "ngaysinh", "noisinh", "tenlop", "tbcht10", "sohpno", "sotcno"):
        for a in alias.get(k, set()):
            META_KEYS.add(_norm_key(a))
    start_idx = list(df.columns).index(col_masv) + 1 if col_masv in df.columns else 0
    subject_cols = []
    for idx, c in enumerate(df.columns):
        if idx < start_idx:
            continue
        key = _norm_key(str(c))
        if _is_meta_header(key):
            continue
        subject_cols.append(c)
    by_ma, by_ten = _hp_lookup_builder()

    total=0; created=0; updated=0; skipped=0
    warnings=[]; preview_rows=[]
    hoc_ky = (request.args.get("hocky") or hoc_ky_default or "").strip() or "HK"

    def _format_hk_for_save(hk_val):
        return str(hk_val) if hk_val is not None else None

    header_tokens = {"masinhvien","ma sinh vien","mssv","mã sinh viên","hovaten","họ và tên",
                     "ngaysinh","ngay sinh","nơi sinh","noisinh","tbc ht10","số hp nợ","số tín chỉ nợ"}

    for i, row in df.iterrows():
        masv = str(row[col_masv]).strip() if pd.notna(row[col_masv]) else ""
        if not masv: continue
        if _norm_key(masv) in header_tokens:
            skipped += 1; warnings.append(f"Dòng {i+2}: bỏ qua vì trùng tiêu đề"); continue

        total += 1
        hoten = (str(row[col_hoten]).strip() if (col_hoten and pd.notna(row[col_hoten])) else None)
        ngs   = _parse_date(row[col_ngs]) if (col_ngs and pd.notna(row[col_ngs])) else None
        nois  = (str(row[col_nois]).strip() if (col_nois and pd.notna(row[col_nois])) else None)
        tb10  = _num_2(row[col_tb10]) if (col_tb10 and pd.notna(row[col_tb10])) else None

        sohp=None
        if col_sohp and pd.notna(row[col_sohp]):
            try: sohp=int(str(row[col_sohp]).strip())
            except Exception: sohp=None
        sotcno=None
        if col_sotc and pd.notna(row[col_sotc]):
            try: sotcno=int(str(row[col_sotc]).strip())
            except Exception: sotcno=None

        sv_exist = db.session.get(SinhVien, masv)
        if not sv_exist:
            if not lop:
                skipped += 1
                warnings.append(f"Dòng {i+2}: MaSV '{masv}' chưa có, thiếu ?lop để gán lớp → bỏ qua")
                continue
            _ensure_user_and_student(masv, hoten, ngs, nois, lop)
        else:
            try:
                if tb10 is not None:
                    for attr in ("TBCHe10","TBCHT10","TBC_HT10","GPA10","DiemTBC10"):
                        if hasattr(sv_exist, attr): setattr(sv_exist, attr, tb10); break
                if sohp is not None:
                    for attr in ("SoHPNo","SoMonNo","SoHocPhanNo"):
                        if hasattr(sv_exist, attr): setattr(sv_exist, attr, sohp); break
                if sotcno is not None:
                    for attr in ("SoTinChiNo","SoTCNo"):
                        if hasattr(sv_exist, attr): setattr(sv_exist, attr, sotcno); break
            except Exception:
                pass

        w_sum=Decimal("0"); w_cnt=Decimal("0")
        for col in subject_cols:
            key = _norm_key(str(col))
            if key in META_KEYS:
                continue

            raw = row[col]
            if pd.isna(raw):
                continue
            v = _num_2(raw)
            if v is None or not (0.0 <= v <= 10.0):
                warnings.append(f"Dòng {i + 2}: Điểm không hợp lệ '{raw}' ở môn '{col}'")
                continue

            subj_key = _norm_subject_name(str(col))
            hobj = by_ten.get(subj_key)
            if not hobj:
                cand = _fuzzy_pick_subject(subj_key, by_ten)
                if cand:
                    hobj = cand
                    warnings.append(f"[gợi ý] Cột '{col}' khớp gần với học phần '{cand.TenHP}' (fuzzy)")

            if not hobj:
                warnings.append(
                    f"Dòng {i + 2}: Không khớp học phần cho cột '{col}' (norm='{subj_key}'). "
                    f"→ Kiểm tra TenHP trong Danh mục HọcPhan hoặc chuẩn hoá tiêu đề cột."
                )
                continue
            mahp = hobj.MaHP

            hk_from_ctdt = ctdt_map.get(mahp)
            if hk_from_ctdt is not None:
                hk_for_row = _format_hk_for_save(hk_from_ctdt)
            else:
                hk_for_row = hoc_ky

            diemchu, he4, kq = _grade_letter(v)
            stc = int(hobj.SoTinChi or 0)
            if stc>0:
                w_sum += Decimal(str(v))*Decimal(str(stc))
                w_cnt += Decimal(str(stc))

            rec = (db.session.query(KetQuaHocTap)
                   .filter(KetQuaHocTap.MaSV==masv,
                           KetQuaHocTap.MaHP==mahp,
                           KetQuaHocTap.HocKy==hk_for_row)
                   .first())
            if rec:
                if allow_update:
                    rec.DiemHe10 = float(v)
                    if hasattr(rec,"DiemHe4"):  rec.DiemHe4  = he4
                    if hasattr(rec,"DiemChu"):  rec.DiemChu  = diemchu
                    if hasattr(rec,"KetQua"):   rec.KetQua   = kq
                    if hasattr(rec,"TinhDiemTichLuy"): rec.TinhDiemTichLuy = bool(hobj.TinhDiemTichLuy)
                    updated += 1
                else:
                    skipped += 1
            else:
                obj = KetQuaHocTap(MaSV=masv, MaHP=mahp, HocKy=hk_for_row, DiemHe10=float(v))
                if hasattr(obj,"DiemHe4"):  obj.DiemHe4  = he4
                if hasattr(obj,"DiemChu"):  obj.DiemChu  = diemchu
                if hasattr(obj,"KetQua"):   obj.KetQua   = kq
                if hasattr(obj,"TinhDiemTichLuy"): obj.TinhDiemTichLuy = bool(hobj.TinhDiemTichLuy)
                db.session.add(obj); created += 1

        chosen = None
        calc = None
        if w_cnt > 0:
            calc = (w_sum / w_cnt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if tb10 is not None:
            if calc is not None and abs(Decimal(str(tb10)) - calc) > EPS:
                warnings.append(
                    f"MaSV {masv}: TBC_HT10 file = {tb10}, tính lại = {float(calc)} (lệch)"
                )
            chosen = Decimal(str(tb10))
        else:
            chosen = calc

        if not preview and chosen is not None:
            val = float(Decimal(chosen).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
            sv_row = db.session.get(SinhVien, masv)
            if sv_row:
                for attr in ("TBCHe10", "TBCHT10", "TBC_HT10", "GPA10", "DiemTBC10"):
                    if hasattr(sv_row, attr):
                        setattr(sv_row, attr, val)
                        break

        if len(preview_rows) < 80:
            preview_rows.append({"MaSV":masv,"HoTen":hoten,"TBC_HT10(file)":tb10,"SoHPNo":sohp,"SoTCNo":sotcno})

    summary={"total_rows":total,"created":created,"updated":updated,"skipped":skipped,"warnings":warnings}

    if preview:
        db.session.rollback()
        return jsonify({"summary":summary,"preview":preview_rows,"warnings":warnings,"file":fname}), 200

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        summary["warnings"].append(f"Lỗi commit DB: {e}")
        return jsonify({"summary":summary,"preview":preview_rows,"warnings":summary["warnings"],"file":fname}), 400

    _audit_import(endpoint="/api/admin/import/grades", affected="KetQuaHocTap", summary=summary, filename=fname)
    return jsonify({"summary":summary,"preview":preview_rows,"warnings":warnings,"file":fname}), 200
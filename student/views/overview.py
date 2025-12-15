# student/views/overview.py
from __future__ import annotations
import customtkinter as ctk
import pandas as pd
from ..widgets.charts import donut, hbar_labeled, line_semester
from ..widgets.cards import KPICard, WarningCard, Section
from ..data.frames import gpa10, credits, gpa_by_semester
from ..theme.tokens import TOKENS

_POSSIBLE_NAME_KEYS = [
    "HoTen","hoten","Ho_ten",
    "TenSinhVien","TenSV","ten","name",
    "full_name","FullName","Full_Name",
    "displayName","display_name","student_name"
]
def _dbg(tag, *a):
    try:
        print(f"[overview] {tag}:", *a)
    except Exception:
        pass
def _find_app_from_widget(w):
    cur = w
    visited = 0
    while cur is not None and visited < 10:
        if hasattr(cur, "app"):
            return getattr(cur, "app")
        cur = getattr(cur, "master", None)
        visited += 1
    return None
def _pluck_name_from_mapping(m: dict | None) -> str | None:
    if not isinstance(m, dict):
        return None
    for k in _POSSIBLE_NAME_KEYS:
        v = m.get(k)
        if v: return str(v)
    for k in ("SinhVien", "sinhvien", "student", "profile", "user", "me","data", "result", "payload"):
        v = m.get(k)
        if isinstance(v, dict):
            n = _pluck_name_from_mapping(v)
            if n: return n
    return None

def _name_from_df(df: pd.DataFrame) -> str | None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    for k in _POSSIBLE_NAME_KEYS + ["Ho_ten"]:
        if k in df.columns:
            s = df[k].dropna().astype(str)
            if not s.empty:
                return s.iloc[0]
    return None

def _resolve_student_name(explicit_profile: dict | None, grades_df: pd.DataFrame) -> str | None:
    name = _pluck_name_from_mapping(explicit_profile)
    if name: return name
    try:
        from ..state.store import AppState
        for obj in (getattr(AppState, "student_profile", None),
                    getattr(AppState, "profile", None),
                    getattr(AppState, "user", None)):
            name = _pluck_name_from_mapping(obj)
            if name: return name
    except Exception:
        pass
    return _name_from_df(grades_df)

def _short(s: str, n=36):
    s = str(s or "")
    return (s[:n-1] + "…") if len(s) > n else s


def letter_from_10(x: float) -> str:
    if x >= 9.0:  return "A+"
    if x >= 8.5:  return "A"
    if x >= 8.0:  return "B+"
    if x >= 7.0:  return "B"
    if x >= 6.5:  return "C+"
    if x >= 5.5:  return "C"
    if x >= 5.0:  return "D+"
    if x >= 4.0:  return "D"
    return "F"

def grade_color(letter: str) -> str:
    if letter in ("A+", "A"): return TOKENS["color"]["success"]
    if letter in ("B+", "B"): return TOKENS["color"]["primary"]
    if letter in ("C+", "C"): return TOKENS["color"]["warning"]
    return TOKENS["color"]["danger"]

def get_student_name(profile: dict | None) -> str | None:
    if not profile: return None
    for k in ("HoTen", "hoten", "TenSinhVien", "ten", "name"):
        v = profile.get(k)
        if v: return str(v)
    return None

class View(ctk.CTkFrame):
    def __init__(self, master, grades_df: pd.DataFrame, profile: dict | None = None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.grades_df = grades_df
        self.profile = profile

        if self.profile is None:
            try:
                from ..state.store import AppState  # optional
                self.profile = getattr(AppState, "profile", None)
            except Exception:
                self.profile = None
        try:
            _dbg("init.profile.type", type(self.profile).__name__)
            _dbg("init.profile.keys", list(self.profile.keys()) if isinstance(self.profile, dict) else None)
        except Exception:
            pass
        try:
            _dbg("init.df.columns", list(self.grades_df.columns)[:16])
        except Exception:
            pass
        self._build()


    def _build(self):
        app = _find_app_from_widget(self)
        app_state = getattr(app, "app_state", None) if app else None

        try:
            _dbg("app_state.present", app_state is not None)
            if app_state is not None:
                _dbg("app_state.token.present", bool(getattr(app_state, "token", None)))
                _dbg("app_state.profile.keys",
                     list(getattr(app_state, "profile", {}).keys()) if isinstance(app_state.profile, dict) else None)
        except Exception:
            pass

        if (not self.profile) and app_state and isinstance(app_state.profile, dict) and app_state.profile:
            self.profile = app_state.profile

        student_name = _resolve_student_name(self.profile, self.grades_df)
        _dbg("resolve.result", student_name)

        if not student_name:
            token = getattr(app_state, "token", None) if app_state else None
            _dbg("token.present(instance)", bool(token))
            if token:
                try:
                    from ..api.client import APIClient
                    ok, payload = APIClient().fetch_student_data(token)
                    _dbg("api.ok", ok)
                    if ok and isinstance(payload, dict):
                        try:
                            _dbg("payload.keys", list(payload.keys()))
                        except Exception:
                            pass

                        def _pick(m):
                            if not isinstance(m, dict):
                                return None
                            for k in ("HoTen", "hoten", "Ho_ten", "TenSinhVien", "TenSV", "ten", "name",
                                      "full_name", "FullName", "Full_Name", "displayName", "display_name",
                                      "student_name"):
                                if m.get(k):
                                    _dbg("pick.key", k, "->", str(m[k]))
                                    return str(m[k])
                            for nest in ("SinhVien", "sinhvien", "student", "profile", "user", "me",
                                         "data", "result", "payload"):
                                sub = m.get(nest)
                                if isinstance(sub, dict):
                                    _dbg("pick.descend", nest)
                                    n = _pick(sub)
                                    if n: return n
                            return None

                        student_name = _pick(payload)
                        _dbg("pick.result", student_name)

                        if student_name and app_state and (not app_state.profile):
                            app_state.profile = {"HoTen": student_name, "MaSV": payload.get("MaSV")}
                except Exception as e:
                    _dbg("api.exception", type(e).__name__, str(e))


        student_name = f"Xin chào, {student_name}" if student_name else " "
        _dbg("final.student_name", student_name)

        ctk.CTkLabel(self, text=student_name, font=ctk.CTkFont(size=20, weight="bold")) \
            .pack(anchor="w", padx=8, pady=(8, 6))

        sc = ctk.CTkScrollableFrame(self, fg_color="transparent")
        sc.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        row1 = ctk.CTkFrame(sc, fg_color="transparent")
        row1.pack(fill="x", padx=8, pady=(0,6))
        row1.grid_columnconfigure((0,1,2), weight=1, uniform="kpi")

        gpa = gpa10(self.grades_df)
        g_letter = letter_from_10(gpa)
        p, debt, total = credits(self.grades_df)

        donut_card = ctk.CTkFrame(row1, corner_radius=16, fg_color="#FFFFFF")
        donut_card.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        donut_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(donut_card, text="CPA tích lũy (10)", text_color="#6B7280")\
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10,0))
        donut(donut_card, gpa, maximum=10.0).grid(row=1, column=0, sticky="w", padx=6, pady=6)

        ctk.CTkLabel(
            donut_card,
            text=g_letter,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=grade_color(g_letter)
        ).grid(row=1, column=1, sticky="w", padx=(0,6))

        KPICard(row1, "Tín chỉ đạt", p, color=TOKENS["color"]["success"]).grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        KPICard(row1, "Tín chỉ nợ", debt, color=TOKENS["color"]["danger"]).grid(row=0, column=2, sticky="nsew", padx=6, pady=6)

        if debt > 0:
            WarningCard(sc, text="Bạn đang có tín chỉ nợ, ưu tiên đăng ký học phần cần cải thiện.")\
                .pack(fill="x", padx=8, pady=(0,6))

        sec = Section(sc, "Xu hướng GPA theo kỳ")
        sec.pack(fill="x", padx=8, pady=(4,6))
        items = gpa_by_semester(self.grades_df)
        sem_labels = [f"Học kỳ{int(k)}" for k, _ in items]
        sem_values = [v for _, v in items]
        line_semester(sec, sem_labels, sem_values).grid(row=1, column=0, sticky="ew", padx=8, pady=(0,10))

        row3 = ctk.CTkFrame(sc, fg_color="transparent")
        row3.pack(fill="x", padx=8, pady=(0,8))
        row3.grid_columnconfigure((0,1), weight=1, uniform="top")

        df = self.grades_df.copy()
        df = df[pd.notnull(df["DiemHe10"])]
        top_good = df.sort_values("DiemHe10", ascending=False).head(5).copy()
        top_bad  = df.sort_values("DiemHe10", ascending=True).head(5).copy()

        def pack_top(section_title, data, col):
            box = Section(row3, section_title)
            box.grid(row=0, column=col, sticky="nsew", padx=6, pady=6)
            labels = [_short(f"{r['MaHP']} · {r['TenHP']}") for _, r in data.iterrows()]
            values = [float(r["DiemHe10"]) for _, r in data.iterrows()]
            info   = [f"{str(r.get('DiemChu') or '-')}/{float(r['DiemHe10']):.1f} · {int(r.get('SoTinChi',0))}TC"
                      for _, r in data.iterrows()]
            hbar_labeled(box, labels, values, right_text=info).grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,10))

        pack_top("Top 5 điểm cao", top_good, 0)
        pack_top("Top 5 cần cải thiện", top_bad, 1)

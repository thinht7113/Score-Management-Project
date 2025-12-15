# frontend_student/views/shell.py
from __future__ import annotations
import customtkinter as ctk
from tkinter import filedialog, messagebox
from ..theme.tokens import TOKENS
from ..data.frames import from_student_payload
from . import overview, transcript, curriculum, analytics, simulator, advisor, profile

_C = TOKENS.get("color", {})
COLOR_SURFACE_ALT = _C.get("surface_alt", "#0F172A")
COLOR_SURFACE      = _C.get("surface", "#111827")
COLOR_TEXT         = _C.get("text", "#E5E7EB")
COLOR_BORDER       = _C.get("border", "#334155")
COLOR_MUTED        = _C.get("muted", "#9CA3AF")
COLOR_PRIMARY      = _C.get("primary", "#3B82F6")
COLOR_ACTIVE_BG    = _C.get("active_bg", "#245DB0")
COLOR_HOVER_BG     = _C.get("hover_bg", "#245DB0")
COLOR_INDICATOR    = _C.get("indicator", COLOR_PRIMARY)


def _student_name_from_profile(prof: dict | None) -> str | None:
    if not isinstance(prof, dict):
        return None
    for k in ("HoTen","hoten","TenSinhVien","TenSV","ten","name","full_name","FullName"):
        v = prof.get(k)
        if v: return str(v)
    for nest in ("SinhVien","student","profile","user","me"):
        sub = prof.get(nest)
        if isinstance(sub, dict):
            n = _student_name_from_profile(sub)
            if n: return n
    return None

class SidebarItem(ctk.CTkFrame):
    def __init__(self, master, key: str, text: str, icon_text: str, on_click, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.key = key
        self.on_click = on_click

        self.box = ctk.CTkFrame(self, fg_color="transparent", corner_radius=10)
        self.box.pack(fill="x", padx=6, pady=3)

        self.indicator = ctk.CTkFrame(self.box, width=4, height=36, fg_color="transparent", corner_radius=3)
        self.indicator.pack(side="left", padx=(6, 10), pady=4)

        safe_icon = (icon_text or "").replace("\ufe0f", "")

        self.btn = ctk.CTkButton(
            self.box,
            text=f"{safe_icon} {text}",
            command=lambda: self.on_click(self.key),
            anchor="w",
            fg_color="transparent",
            hover=True,
            hover_color=COLOR_HOVER_BG,
            text_color=COLOR_TEXT,
            corner_radius=10,
            height=36
        )
        self.btn.pack(side="left", fill="x", expand=True, pady=4)

    def set_active(self, active: bool):
        self._active = bool(active)
        if self._active:
            self.box.configure(fg_color=COLOR_ACTIVE_BG)
            self.indicator.configure(fg_color=COLOR_INDICATOR)
            self.btn.configure(text_color="#FFFFFF")
        else:
            self.box.configure(fg_color="transparent")
            self.indicator.configure(fg_color="transparent")
            self.btn.configure(text_color=COLOR_TEXT)

    def _hover(self, is_in: bool):
        if self._active:
            return
        self.box.configure(fg_color=COLOR_HOVER_BG if is_in else "transparent")
        self.btn.configure(text_color="#FFFFFF" if is_in else COLOR_TEXT)


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_nav, **kw):
        super().__init__(master, fg_color=COLOR_SURFACE_ALT, corner_radius=16, **kw)
        self.on_nav = on_nav
        self._items = []
        self._active_key = None

        title = ctk.CTkLabel(self, text="📚  Student", text_color=COLOR_MUTED,font=ctk.CTkFont(size=14, weight="bold"))
        title.pack(anchor="w", padx=14, pady=(12, 6))

        nav_defs = [
            ("overview","Tổng quan","🏠"),
            ("transcript","Bảng điểm","📄"),
            ("curriculum","Chương trình học", "🗺️"),
            ("analytics","Phân tích","📈"),
            ("simulator","Mô phỏng GPA","🧮"),
            ("advisor","Cố vấn AI","🤖"),
            ("profile","Hồ sơ","👤"),
        ]
        for key, label, icon in nav_defs:
            it = SidebarItem(self, key, label, icon, on_click=self._on_click)
            it.pack(fill="x")
            self._items.append(it)

        ctk.CTkLabel(self, text="", fg_color="transparent").pack(pady=6)

    def _on_click(self, key: str):
        self.set_active(key)
        self.on_nav(key)

    def set_active(self, key: str):
        self._active_key = key
        for it in self._items:
            it.set_active(it.key == key)


class Header(ctk.CTkFrame):
    def __init__(self, master, on_export_xlsx, on_export_pdf, on_logout):
        super().__init__(master, fg_color="transparent")
        self.title = ctk.CTkLabel(self, text="Tổng quan", font=ctk.CTkFont(size=20, weight="bold"))
        self.title.pack(side="left")
        ctk.CTkButton(self, text="Đăng xuất", fg_color="#EF4444", hover_color="#DC2626",command=on_logout).pack(side="right", padx=(6, 0))
        ctk.CTkButton(self, text="Export PDF", command=on_export_pdf).pack(side="right")
        ctk.CTkButton(self, text="Export Excel", command=on_export_xlsx).pack(side="right", padx=(6, 0))


class ShellView(ctk.CTkFrame):
    def __init__(self, master, app=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app
        self.sidebar = None; self.header=None; self.content=None
        self._current = None
        self._payload_cache = None
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(1, weight=1)

        self.sidebar = Sidebar(self, on_nav=self.switch_tab, width=220)
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=8, pady=8)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(2,8), pady=8)
        main.grid_rowconfigure(1, weight=1); main.grid_columnconfigure(0, weight=1)

        self.header = Header(main, on_export_xlsx=self._export_excel, on_export_pdf=self._export_pdf,on_logout=self._logout,)
        self.header.grid(row=0, column=0, sticky="ew", padx=6, pady=(0,8))

        self.content = ctk.CTkFrame(main, fg_color=COLOR_SURFACE_ALT, corner_radius=18)
        self.content.grid(row=1, column=0, sticky="nsew")

        self.switch_tab("overview")

    def _logout(self):
        if not messagebox.askyesno("Đăng xuất", "Bạn có chắc muốn đăng xuất?"):
            return

        self._payload_cache = None
        try:
            self.app.login_view.reset(message="")
        except Exception:
            pass
        self.app.show_view("login")
        try:
            st = getattr(self.app, "app_state", None)
            if st is not None:
                try:
                    st.token = ""
                except Exception:
                    pass
                try:
                    st.profile = {}
                except Exception:
                    pass
                try:
                    st.grades_df = None
                except Exception:
                    pass
                try:
                    st.plan_df = None
                except Exception:
                    pass
        except Exception:
            pass

        self.app.show_view("login")

    def on_show(self):
        if getattr(self.app, "app_state", None) and self.app.app_state.token and self._payload_cache is None:
            ok, data = self.app.api_client.fetch_student_data(self.app.app_state.token)
            if ok and isinstance(data, dict):
                self._payload_cache = data
                self.switch_tab(self._current or "overview")

    def switch_tab(self, tab):
        self._current = tab
        title_map = {
            "overview":"Tổng quan","transcript":"Bảng điểm","curriculum":"Khung chương trình học",
            "analytics":"Phân tích","simulator":"Mô phỏng","advisor":"Cố vấn AI","profile":"Hồ sơ"
        }
        try: self.header.title.configure(text=title_map.get(tab, tab))
        except Exception: pass

        try: self.sidebar.set_active(tab)
        except Exception: pass

        for w in self.content.winfo_children():
            try: w.destroy()
            except Exception: pass

        g, p, prof = from_student_payload(self._payload_cache or {})
        self.app.app_state.grades_df = g; self.app.app_state.plan_df = p; self.app.app_state.profile = prof

        if tab == "overview":
            overview.View(self.content, grades_df=g).pack(fill="both", expand=True, padx=8, pady=8)
        elif tab == "transcript":
            transcript.View(self.content, grades_df=g).pack(fill="both", expand=True, padx=8, pady=8)
        elif tab == "curriculum":
            curriculum.View(self.content, plan_df=p, grades_df=g).pack(fill="both", expand=True, padx=8, pady=8)
        elif tab == "analytics":
            analytics.View(self.content, grades_df=g).pack(fill="both", expand=True, padx=8, pady=8)
        elif tab == "simulator":
            simulator.View(self.content, grades_df=g, plan_df=p).pack(fill="both", expand=True, padx=8, pady=8)
        elif tab == "advisor":
            advisor.View(self.content, grades_df=g, plan_df=p, profile=prof, app=self.app) \
                .pack(fill="both", expand=True, padx=8, pady=8)
        elif tab == "profile":
            profile.View(self.content, profile=prof, grades_df=g).pack(fill="both", expand=True, padx=8, pady=8)
        else:
            ctk.CTkLabel(self.content, text="(Đang phát triển)", text_color="#6B7280").pack(pady=18)

    def _export_excel(self):
        import pandas as pd
        g = self.app.app_state.grades_df; p = self.app.app_state.plan_df
        if g is None: messagebox.showwarning("Export","Chưa có dữ liệu."); return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel","*.xlsx")], initialfile="student_report.xlsx")
        if not path: return
        with pd.ExcelWriter(path) as w:
            g.to_excel(w, index=False, sheet_name="Grades")
            if p is not None and not p.empty: p.to_excel(w, index=False, sheet_name="Curriculum")
        messagebox.showinfo("Export","Đã xuất Excel.")

    def _export_pdf(self):
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.pyplot as plt
        g = self.app.app_state.grades_df
        if g is None or g.empty: messagebox.showwarning("Export","Chưa có dữ liệu."); return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF","*.pdf")], initialfile="student_report.pdf")
        if not path: return
        with PdfPages(path) as pdf:
            fig, ax = plt.subplots(figsize=(7.5,3.5), dpi=120)
            ax.axis("off")
            ax.text(0.01, 0.95, "Báo cáo học tập", fontsize=14, weight="bold")
            ax.text(0.01, 0.90, f"Tổng số môn: {len(g)}")
            ax.text(0.01, 0.86, f"Tín chỉ: {int(g['SoTinChi'].sum())}")
            pdf.savefig(fig); plt.close(fig)
        messagebox.showinfo("Export","Đã xuất PDF.")

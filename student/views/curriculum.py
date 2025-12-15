# student/views/curriculum.py
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk
import pandas as pd

GREEN = "#10B981"
RED   = "#EF4444"
GREY  = "#9CA3AF"

def _norm_semester(s):
    if pd.isna(s): return None
    try:
        return int(float(s))
    except Exception:
        try:
            return int(str(s).strip().split()[-1])
        except Exception:
            return None

class Chip(ctk.CTkFrame):
    def __init__(self, master, text: str, bg="#E5E7EB", fg="white"):
        super().__init__(master, corner_radius=18, fg_color=bg)
        ctk.CTkLabel(self, text=text, text_color=fg, font=ctk.CTkFont(size=12)).pack(padx=12, pady=6)

class View(ctk.CTkFrame):
    def __init__(self, master, grades_df: pd.DataFrame,
                 curriculum_df: pd.DataFrame | None = None, plan_df: pd.DataFrame | None = None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.grades_df = grades_df.copy()
        if curriculum_df is None and plan_df is not None: curriculum_df = plan_df
        self.curriculum_df = curriculum_df.copy() if curriculum_df is not None else None
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)
        wrap = ctk.CTkFrame(self, fg_color="transparent"); wrap.grid(row=0, column=0, sticky="nsew", padx=8, pady=(36,0))
        wrap.grid_rowconfigure(0, weight=1); wrap.grid_columnconfigure(0, weight=1)

        sc = ctk.CTkScrollableFrame(wrap, fg_color="transparent"); sc.grid(row=0, column=0, sticky="nsew")

        bg = self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        self.canvas = tk.Canvas(sc, highlightthickness=0, bg=bg); self.canvas.pack(fill="x", expand=False)
        self.inner = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.win = self.canvas.create_window((0,0), window=self.inner, anchor="nw")

        self.hbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.hbar.grid(row=1, column=0, sticky="ew", padx=8, pady=(6,10))
        self.canvas.configure(xscrollcommand=self.hbar.set)

        cur = self._prepare_data()
        for sem in sorted(cur["HocKy"].dropna().unique()):
            block = ctk.CTkFrame(self.inner, fg_color="transparent"); block.pack(fill="x", padx=4, pady=(0,4))
            ctk.CTkLabel(block, text=f"Học kỳ {int(sem)}", font=ctk.CTkFont(size=14, weight="bold"))\
                .pack(anchor="w", padx=6, pady=(6,2))
            row = ctk.CTkFrame(block, fg_color="transparent"); row.pack(fill="x", padx=0, pady=(0,8))
            for _, r in cur[cur["HocKy"] == sem].iterrows():
                label = f"{r['MaHP']} · {r['TenHP']} · {int(r.get('SoTinChi',0))} TC"
                color = GREY
                if pd.notnull(r.get("DiemHe10")):
                    color = GREEN if float(r["DiemHe10"]) >= 4.0 else RED
                Chip(row, text=label, bg=color, fg="white").pack(side="left", padx=8, pady=6)

        self.inner.bind("<Configure>", self._sync_scrollregion)
        self.after(80, self._fit_canvas_height)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<Shift-MouseWheel>", self._on_shift_wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<Shift-MouseWheel>"))

    # ============ Scroll helpers ============
    def _sync_scrollregion(self, _evt=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    def _fit_canvas_height(self):
        try:
            h = self.inner.winfo_reqheight()
            if h > 0: self.canvas.configure(height=h)
            self._sync_scrollregion()
        except Exception: pass
    def _on_shift_wheel(self, event):
        self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")

    # ============ Data join ============
    def _prepare_data(self) -> pd.DataFrame:
        g = self.grades_df.copy()
        for c in ["MaHP","TenHP","SoTinChi","DiemHe10","DiemChu","HocKy"]:
            if c not in g.columns: g[c] = None
        g["HocKy"] = pd.to_numeric(g["HocKy"], errors="coerce")

        if self.curriculum_df is not None and not self.curriculum_df.empty:
            cdf = self.curriculum_df.copy()
            for c in ["MaHP","TenHP","SoTinChi","HocKy","HKGoiY"]:
                if c not in cdf.columns: cdf[c] = None
            cdf["HocKy"] = pd.to_numeric(cdf["HocKy"], errors="coerce")\
                .fillna(pd.to_numeric(cdf["HKGoiY"], errors="coerce"))
            cur = cdf.merge(g[["MaHP","DiemHe10","DiemChu"]], on="MaHP", how="left")
        else:
            cur = g[["MaHP","TenHP","SoTinChi","HocKy","DiemHe10","DiemChu"]].copy()

        cur = cur[pd.notnull(cur["MaHP"]) & pd.notnull(cur["TenHP"])]
        cur["HocKy"] = pd.to_numeric(cur["HocKy"], errors="coerce")
        cur = cur[pd.notnull(cur["HocKy"])].sort_values(["HocKy","TenHP"]).reset_index(drop=True)
        return cur

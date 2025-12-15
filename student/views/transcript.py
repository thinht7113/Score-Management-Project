# student/views/transcript.py
from __future__ import annotations

import math

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import pandas as pd

def _fmt(x, digits=2):
    try:
        v = float(x)
        return f"{v:.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return "" if pd.isna(x) else str(x)

def _gpa10_weighted(df: pd.DataFrame) -> float:
    d = df[(pd.notnull(df["DiemHe10"])) & (df["SoTinChi"] > 0)]
    if d.empty: return 0.0
    return float((d["DiemHe10"] * d["SoTinChi"]).sum() / d["SoTinChi"].sum())
def _hk_summary_label(hk):
    try:
        f = float(hk)
        if pd.notna(f) and math.isfinite(f):
            return f"Tổng kết HK{int(f)}:"
    except Exception:
        pass
    return "Tổng kết:"

class View(ctk.CTkFrame):
    def __init__(self, master, grades_df: pd.DataFrame, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.df_all = grades_df.copy()
        for c in ["HocKy","MaHP","TenHP","SoTinChi","DiemHe10","DiemHe4","DiemChu","TinhDiemTichLuy"]:
            if c not in self.df_all.columns:
                self.df_all[c] = None
        self._build()


    def _build(self):


        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(0,6))

        sems = sorted([int(x) for x in self.df_all["HocKy"].dropna().unique()]) or []
        sem_labels = [f"Học kỳ {n}" for n in sems]
        self.sem_var = tk.StringVar(value="Tất cả")

        ctk.CTkLabel(toolbar, text="Kỳ:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0,6))
        ctk.CTkOptionMenu(
            toolbar,
            values=["Tất cả"] + sem_labels,
            variable=self.sem_var,
            command=lambda _=None: self._rebuild(),
            font=ctk.CTkFont(size=12),
            width=150, height=34
        ).pack(side="left")

        self.fail_only = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            toolbar,
            text="Chỉ hiển thị môn CHƯA ĐẠT (<4.0)",
            variable=self.fail_only,
            command=self._rebuild,
            font=ctk.CTkFont(size=12),
            checkbox_height=18, checkbox_width=18, height=34
        ).pack(side="left", padx=12)

        self.q = tk.StringVar()
        ctk.CTkLabel(toolbar, text="Tìm:", font=ctk.CTkFont(size=12)).pack(side="right", padx=(0,6))
        ent = ctk.CTkEntry(toolbar, textvariable=self.q, placeholder_text="Tìm mã/tên học phần…",
                           width=300, height=34, font=ctk.CTkFont(size=12))
        ent.pack(side="right")
        ent.bind("<KeyRelease>", lambda e: self._rebuild())

        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=10, pady=(0,10))
        box.grid_rowconfigure(0, weight=1); box.grid_columnconfigure(0, weight=1)

        style = ttk.Style(box)
        style.configure("Grade.Treeview",
                        font=("Segoe UI", 11),
                        rowheight=30,
                        background="#FFFFFF",
                        fieldbackground="#FFFFFF",
                        borderwidth=0)
        style.configure("Grade.Treeview.Heading",
                        font=("Segoe UI Semibold", 11),
                        background="#F3F4F6")
        style.map("Grade.Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", "#111827")])

        cols = [
            ("HocKy", "Học kỳ", 80, "center"),
            ("MaHP",      "Mã HP",  110, "center"),
            ("TenHP",     "Học phần", 420, "w"),
            ("SoTinChi",  "TC",     60, "e"),
            ("DiemHe10",  "Điểm 10", 90, "e"),
            ("DiemHe4",   "Điểm 4",  80, "e"),
            ("DiemChu",   "Điểm chữ", 90, "center"),
        ]
        self.tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings", style="Grade.Treeview")
        vsb = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        for key, title, width, anchor in cols:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=40, anchor=anchor)

        self.tree.tag_configure("group",   background="#F3F4F6", font=("Segoe UI Semibold", 11))
        self.tree.tag_configure("summary", background="#F9FAFB", foreground="#374151", font=("Segoe UI Italic", 11))
        self.tree.tag_configure("pass",    background="#F0FAF6", foreground="#065F46")
        self.tree.tag_configure("fail",    background="#FEF2F2", foreground="#991B1B")
        self.tree.tag_configure("odd",     background="#FBFDFF")

        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(fill="x", padx=10, pady=(0,8))
        self.kpi_lbl = ctk.CTkLabel(self.footer, text="", font=ctk.CTkFont(size=12))
        self.kpi_lbl.pack(anchor="e")

        self._rebuild()

    def _filtered_df(self) -> pd.DataFrame:
        df = self.df_all.copy()

        sem = self.sem_var.get()
        if sem != "Tất cả":
            try:
                sem_num = int(str(sem).split()[-1])
                df = df[df["HocKy"] == sem_num]
            except Exception:
                pass

        if self.fail_only.get():
            df = df[pd.notnull(df["DiemHe10"]) & (df["DiemHe10"] < 4.0)]

        qq = (self.q.get() or "").strip().lower()
        if qq:
            df = df[df.apply(lambda r: (qq in str(r.get("MaHP","")).lower()) or
                                       (qq in str(r.get("TenHP","")).lower()), axis=1)]
        return df

    def _rebuild(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        df = self._filtered_df()
        try:
            df = df.sort_values(["HocKy", "TenHP"]).reset_index(drop=True)
        except Exception:
            pass

        zebra = False
        total_tc = int(df.get("SoTinChi", pd.Series(dtype=int)).sum() or 0)
        gpa_all = _gpa10_weighted(df)

        for hk, g in df.groupby("HocKy", dropna=False):
            hk_text = f" HỌC KỲ {int(hk)} " if pd.notna(hk) else " HỌC KỲ "
            self.tree.insert("", "end", values=[hk_text,"","","","","",""], tags=("group",))
            for _, r in g.iterrows():
                tags = []
                if pd.notnull(r.get("DiemHe10")):
                    tags.append("pass" if float(r["DiemHe10"]) >= 4.0 else "fail")
                if zebra: tags.append("odd")
                zebra = not zebra
                self.tree.insert("", "end", values=[
                    r.get("HocKy",""),
                    r.get("MaHP",""),
                    r.get("TenHP",""),
                    int(r.get("SoTinChi",0)) if pd.notnull(r.get("SoTinChi")) else "",
                    _fmt(r.get("DiemHe10"), 2),
                    _fmt(r.get("DiemHe4"), 1),
                    r.get("DiemChu","") or "",
                ], tags=tuple(tags))

            gpa_sem = _gpa10_weighted(g)
            tc_sem = int(g.get("SoTinChi", pd.Series(dtype=int)).sum() or 0)
            self.tree.insert("", "end",
                             values=["", "", _hk_summary_label(hk),
                                     tc_sem, f"{gpa_sem:.2f}", "", ""],
                             tags=("summary",))

        self.kpi_lbl.configure(text=f"GPA (10) toàn bộ: {gpa_all:.2f}   |   Tổng tín chỉ: {total_tc}")

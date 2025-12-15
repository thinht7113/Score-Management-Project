# frontend_student/views/profile.py
from __future__ import annotations
import customtkinter as ctk
import pandas as pd
from ..data.frames import gpa10, credits

class View(ctk.CTkFrame):
    def __init__(self, master, profile: dict, grades_df: pd.DataFrame, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.profile = profile or {}
        self.df = grades_df.copy() if grades_df is not None else None
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Hồ sơ sinh viên", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=10, pady=(10,4))
        card = ctk.CTkFrame(self, corner_radius=16); card.pack(fill="x", padx=10, pady=8)
        grid = ctk.CTkFrame(card, fg_color="transparent"); grid.pack(fill="x", padx=14, pady=14)
        grid.grid_columnconfigure((0,2), weight=0); grid.grid_columnconfigure((1,3), weight=1)
        def row(r, label, val):
            ctk.CTkLabel(grid, text=label, text_color="#6B7280").grid(row=r, column=0, sticky="w", padx=(0,8), pady=3)
            ctk.CTkLabel(grid, text=str(val or "—")).grid(row=r, column=1, sticky="w", pady=3)
        row(0,"Mã SV", self.profile.get("MaSV"))
        row(1,"Họ tên", self.profile.get("HoTen"))
        row(2,"Lớp", self.profile.get("Lop"))
        row(3,"Ngành", self.profile.get("Nganh"))
        row(4,"Khoa", self.profile.get("Khoa"))
        row(5,"Email", self.profile.get("Email"))

        if self.df is not None and not self.df.empty:
            p, debt, total = credits(self.df)
            g = gpa10(self.df)
            meta = ctk.CTkFrame(self, corner_radius=16); meta.pack(fill="x", padx=10, pady=(0,8))
            for i, (k,v) in enumerate([("CPA tích lũy (10)", f"{g:.2f}"), ("TC đạt", p), ("TC nợ", debt)]):
                box = ctk.CTkFrame(meta, corner_radius=12); box.grid(row=0, column=i, sticky="nsew", padx=6, pady=6)
                meta.grid_columnconfigure(i, weight=1)
                ctk.CTkLabel(box, text=k, text_color="#6B7280").pack(anchor="w", padx=12, pady=(10,2))
                ctk.CTkLabel(box, text=str(v), font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=12, pady=(0,12))

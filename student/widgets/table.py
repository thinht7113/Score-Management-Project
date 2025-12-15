# frontend_student/widgets/table.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import pandas as pd

class DataFrameTable(ctk.CTkFrame):
    def __init__(self, master, df: pd.DataFrame, *, height=16, columns=None, searchable=True, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._df = df.copy()
        cols = columns or list(df.columns)

        if searchable:
            top = ctk.CTkFrame(self, fg_color="transparent")
            top.pack(fill="x", padx=2, pady=(2,0))
            ctk.CTkLabel(top, text="Tìm:").pack(side="left", padx=(2,6))
            self._q = tk.StringVar()
            ent = ctk.CTkEntry(top, textvariable=self._q, placeholder_text="nhập từ khóa…", width=220)
            ent.pack(side="left", padx=(0,6))
            ent.bind("<KeyRelease>", lambda e: self._apply_filter())

        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=height)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.grid_rowconfigure(0, weight=1); wrap.grid_columnconfigure(0, weight=1)

        for c in cols:
            self.tree.heading(c, text=str(c), command=lambda cc=c: self._sort(cc, False))
            self.tree.column(c, width=max(80, int(len(str(c))*9)))

        self._populate(self._df)

    def _populate(self, df):
        self.tree.delete(*self.tree.get_children())
        for _, row in df.iterrows():
            vals = [row.get(c, "") if isinstance(row, dict) else row[c] for c in self.tree["columns"]]
            self.tree.insert("", "end", values=[("" if pd.isna(v) else v) for v in vals])

    def _sort(self, col, reverse):
        try: sorted_df = self._df.sort_values(by=col, ascending=not reverse)
        except Exception: sorted_df = self._df
        self._populate(sorted_df)
        self.tree.heading(col, command=lambda: self._sort(col, not reverse))

    def _apply_filter(self):
        q = (self._q.get() if hasattr(self, "_q") else "").strip().lower()
        if not q:
            self._populate(self._df); return
        mask = self._df.apply(lambda r: any(q in str(v).lower() for v in r.values), axis=1)
        self._populate(self._df[mask])

    def set_df(self, df: pd.DataFrame):
        self._df = df.copy(); self._populate(self._df)

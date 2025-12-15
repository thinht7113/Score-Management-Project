# frontend_student/widgets/forms.py
from __future__ import annotations
import customtkinter as ctk

class FilterRow(ctk.CTkFrame):
    def __init__(self, master, *, semesters: list[str], on_change, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on = on_change
        ctk.CTkLabel(self, text="Lọc:").pack(side="left", padx=(4,6))
        self.var = ctk.StringVar(value="Tất cả")
        ctk.CTkOptionMenu(self, values=["Tất cả"] + semesters, variable=self.var,
                          command=lambda _v=None: self._on(self.var.get())).pack(side="left")

class Toggle(ctk.CTkFrame):
    def __init__(self, master, text, default=False, on_toggle=None):
        super().__init__(master, fg_color="transparent")
        self.var = ctk.BooleanVar(value=default)
        self.chk = ctk.CTkCheckBox(self, text=text, variable=self.var, command=lambda: on_toggle and on_toggle(self.var.get()))
        self.chk.pack(side="left")

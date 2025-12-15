# student/widgets/cards.py
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk

# Màu trung tính; nếu bạn đã có TOKENS thì có thể thay bằng TOKENS["color"][...]
SURFACE = "#FFFFFF"
MUTED   = "#6B7280"

class KPICard(ctk.CTkFrame):
    """
    Thẻ KPI đơn giản:
      - title: nhãn nhỏ phía trên
      - value: giá trị lớn
      - color: màu chữ cho value (tùy chọn)
    Có các hàm cập nhật: set_value(value) và set(value).
    """
    def __init__(self, master, title: str, value: str | int | float = "—",
                 color: str | None = None, **kw):
        super().__init__(master, corner_radius=16, fg_color=SURFACE, **kw)
        self.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(self, text=title, text_color=MUTED,
                                        font=ctk.CTkFont(size=12))
        self.title_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 0))

        self._value_var = tk.StringVar(value=str(value))
        self.value_label = ctk.CTkLabel(self, textvariable=self._value_var,
                                        font=ctk.CTkFont(size=24, weight="bold"))
        if color:
            self.value_label.configure(text_color=color)
        self.value_label.grid(row=1, column=0, sticky="w", padx=12, pady=(2, 12))

    # --- API cập nhật giá trị ---
    def set_value(self, v):
        self._value_var.set(str(v))

    def set(self, v):  # alias tiện dụng
        self.set_value(v)


class WarningCard(ctk.CTkFrame):
    """Banner cảnh báo ngắn gọn."""
    def __init__(self, master, text: str, **kw):
        super().__init__(master, corner_radius=12, fg_color="#FEF3C7", **kw)
        ctk.CTkLabel(self, text=text, text_color="#92400E",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=10)


class Section(ctk.CTkFrame):
    """
    Khối chứa có tiêu đề, dùng grid:
      - header ở (row=0, col=0)
      - nội dung tự đặt ở các hàng sau
    """
    def __init__(self, master, title: str, **kw):
        super().__init__(master, corner_radius=12, fg_color="#F7F9FC", **kw)
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#111827").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 0))

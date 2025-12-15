#student/views/login.py
from __future__ import annotations
import customtkinter as ctk
from tkinter import messagebox
import os, json


class LoginView(ctk.CTkFrame):
    def __init__(self, master, app=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.app = app
        self.api = getattr(app, "api_client", None)
        self._cfg_path = os.path.join(os.getcwd(), "student_settings.json")
        self._cfg = self._load_cfg()

        for i in range(3):
            self.grid_rowconfigure(i, weight=1)
            self.grid_columnconfigure(i, weight=1)

        self.card = ctk.CTkFrame(self, corner_radius=18, fg_color=("#FFFFFF","#0B1220"))
        self.card.grid(row=1, column=1, sticky="nsew", padx=32, pady=32)
        self.card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self.card, text="Hỗ trợ học tập", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, pady=(18,2))
        ctk.CTkLabel(self.card, text="Đăng nhập để tiếp tục").grid(row=1, column=0)

        form = ctk.CTkFrame(self.card, fg_color="transparent")
        form.grid(row=2, column=0, sticky="ew", padx=24, pady=(16,8))
        form.grid_columnconfigure(0, weight=1)
        self.ent_user = ctk.CTkEntry(form, placeholder_text="Mã sinh viên / Username")
        self.ent_pass = ctk.CTkEntry(form, placeholder_text="Mật khẩu", show="•")
        self.ent_user.grid(row=0, column=0, sticky="ew", pady=6)
        self.ent_pass.grid(row=1, column=0, sticky="ew", pady=6)

        self.lbl_error = ctk.CTkLabel(self.card, text="", text_color="red")
        self.lbl_error.grid(row=3, column=0, sticky="w", padx=24)

        self.btn_login = ctk.CTkButton(self.card, text="Đăng nhập", command=self._login)
        self.btn_login.grid(row=4, column=0, sticky="ew", padx=24, pady=(6,18))

        self.ent_user.bind("<Return>", lambda e: self._login())
        self.ent_pass.bind("<Return>", lambda e: self._login())
        self.ent_user.bind("<Key>", lambda e: self.lbl_error.configure(text=""))
        self.ent_pass.bind("<Key>", lambda e: self.lbl_error.configure(text=""))

        if self._cfg.get("last_username"):
            self.ent_user.insert(0, self._cfg.get("last_username",""))
            self.ent_pass.focus()
        else:
            self.ent_user.focus()

    def reset(self, keep_username: bool = True, message: str = ""):
        if not keep_username:
            self.ent_user.delete(0, "end")
        self.ent_pass.delete(0, "end")
        self.lbl_error.configure(text=message)
        (self.ent_pass if (self.ent_user.get() or "").strip() else self.ent_user).focus()

    def _load_cfg(self):
        try:
            if os.path.exists(self._cfg_path):
                with open(self._cfg_path,"r",encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_user(self, username):
        try:
            self._cfg["last_username"] = username
            with open(self._cfg_path,"w",encoding="utf-8") as f:
                json.dump(self._cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _login(self):
        if not self.api:
            messagebox.showerror("Lỗi","Không tìm thấy API client"); return
        u = (self.ent_user.get() or "").strip()
        p = (self.ent_pass.get() or "").strip()
        if not u or not p:
            self.lbl_error.configure(text="Cần nhập tài khoản và mật khẩu."); return
        try:
            ok, payload = self.api.login(u,p)
        except Exception as e:
            ok, payload = False, f"Lỗi kết nối: {e}"
        if not ok:
            self.lbl_error.configure(text=str(payload or "Sai thông tin đăng nhập.")); return

        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            self.lbl_error.configure(text="Không nhận được access_token từ server."); return

        if getattr(self.app, "app_state", None) is not None:
            self.app.app_state.token = token
        self._save_user(u)
        if getattr(self.app, "show_view", None):
            self.app.show_view("dashboard")

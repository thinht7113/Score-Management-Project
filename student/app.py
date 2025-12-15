# student/app.py
from __future__ import annotations
import sys, traceback
import customtkinter as ctk
from tkinter import messagebox
from student.theme import apply_theme, set_matplotlib_style, APP_TITLE
from student.views.login import LoginView
from student.views.shell import ShellView
from student.api.client import APIClient
from student.state.store import AppState
from pathlib import Path
from dotenv import load_dotenv
import os
import sys
from tkinter import PhotoImage

load_dotenv(Path(__file__).with_name(".env"))

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:5000")

def rpath(*parts):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base.joinpath(*parts))
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x760"); self.minsize(1024, 640)
        if sys.platform.startswith("win"):
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "vn.vui.studentassistant"
                )
            except Exception:
                pass
        self.app_state = AppState()

        self.api_client = APIClient(
            base_url=API_BASE_URL,
            token_getter=lambda: getattr(self.app_state, "token", "")
        )
        try:
            self.iconbitmap(rpath("theme", "app.ico"))
        except Exception:
            try:
                self.iconphoto(True, PhotoImage(file=rpath("theme", "app_256.png")))
            except Exception:
                pass
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.views = {}; self.current_view = None; self._busy = False

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_view("login")

    def on_close(self):
        try:
            if self.current_view and hasattr(self.current_view, "on_close"):
                self.current_view.on_close()
        finally:
            self.destroy()

    def show_view(self, name: str):
        if self._busy: return
        self._busy = True
        try:
            if self.current_view is not None:
                try: self.current_view.pack_forget()
                except Exception: pass

            if name not in self.views:
                if name == "login":
                    self.views[name] = LoginView(self.container, app=self)
                elif name in ("dashboard","shell"):
                    self.views[name] = ShellView(self.container, app=self)
                else:
                    raise ValueError(f"Unknown view: {name}")

            if name == "login":
                self._apply_login_window_mode()
            else:
                self._apply_shell_window_mode()

            v = self.views[name]; v.pack(fill="both", expand=True); self.current_view = v
            if hasattr(v, "on_show"): self.after_idle(v.on_show)
        finally:
            self.after(120, lambda: setattr(self, "_busy", False))

    def _center(self, w=560, h=420):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = int((sw - w) / 2.7); y = int((sh - h) / 3.2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _apply_login_window_mode(self):
        try: self.state("normal")
        except Exception: pass
        self.resizable(False, False); self._center(560, 420)

    def _apply_shell_window_mode(self):
        self.resizable(True, True); self.minsize(1024, 640)
        try: self.state("zoomed")
        except Exception:
            self.update_idletasks()
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            self.geometry(f"{sw}x{sh}+0+0")

def _run():
    apply_theme(mode="light"); set_matplotlib_style()
    app = App()
    try: app.mainloop()
    except Exception as e:
        traceback.print_exc()
        try: messagebox.showerror("Lỗi ứng dụng", f"{type(e).__name__}: {e}")
        except Exception: pass
        sys.exit(1)

if __name__ == "__main__":
    _run()


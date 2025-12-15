# student/theme/__init__.py
from __future__ import annotations
import customtkinter as ctk
from matplotlib import rcParams
from .tokens import TOKENS

APP_TITLE = "Student Assistant"

def apply_theme(mode: str = "light"):
    try: ctk.set_appearance_mode(mode)
    except Exception: pass

def set_matplotlib_style():
    rcParams.update({
        "axes.facecolor": TOKENS["color"]["surface"],
        "figure.facecolor": TOKENS["color"]["surface"],
        "axes.edgecolor": TOKENS["color"]["border"],
        "grid.color": TOKENS["color"]["grid"],
        "text.color": TOKENS["color"]["text"],
        "axes.labelcolor": TOKENS["color"]["text"],
        "xtick.color": TOKENS["color"]["muted"],
        "ytick.color": TOKENS["color"]["muted"],
        "axes.grid": True,
        "grid.alpha": 0.18,
        "lines.linewidth": 2.0,
    })

class AnimatedGradientBG(ctk.CTkCanvas):
    def __init__(self, master, **kw):
        super().__init__(master, highlightthickness=0, **kw)
        self.running = False; self._h = 0
    def start(self, fps: int = 30):
        self.running = True
        self._tick(max(1, int(1000/fps)))
    def stop(self): self.running = False
    def _tick(self, delay):
        if not self.running or not self.winfo_exists(): return
        self._h = (self._h + 2) % 360
        try: self.configure(bg=self._hsv_to_hex(self._h, 0.22, 1.0))
        except Exception: pass
        self.after(delay, lambda: self._tick(delay))
    @staticmethod
    def _hsv_to_hex(h, s, v):
        import colorsys
        r,g,b = colorsys.hsv_to_rgb(h/360, s, v)
        return "#%02x%02x%02x"%(int(r*255), int(g*255), int(b*255))

# student/widgets/charts.py
from __future__ import annotations
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from student.theme.tokens import TOKENS

class MatplotlibHost(ctk.CTkFrame):
    def __init__(self, master, figsize=(4,2), dpi=100, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.fig = Figure(figsize=figsize, dpi=dpi)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def plot(self, fn):
        self.ax.clear(); fn(self.ax); self.canvas.draw_idle()

def sparkline(parent, values):
    host = MatplotlibHost(parent, figsize=(3.6,1.3))
    def _plot(ax):
        if not values:
            ax.text(0.5,0.5,"No data", ha="center", va="center")
        else:
            x = list(range(len(values)))
            ax.plot(x, values, color=TOKENS["color"]["primary"])
            try:
                ax.fill_between(x, values, [min(values)]*len(values), alpha=0.12,
                                color=TOKENS["color"]["primary"])
            except Exception:
                pass
            ax.set_ylim(0, max(10, max(values)+1))
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(True, alpha=0.18)
    host.plot(_plot); return host

def donut(parent, value, maximum=10.0):
    host = MatplotlibHost(parent, figsize=(2.6,2.6))
    def _plot(ax):
        v = max(0.0, min(float(value), float(maximum)))
        ax.pie([v, max(0.0, maximum-v)], startangle=90,
               colors=[TOKENS["color"]["primary"], TOKENS["color"]["border"]],
               radius=1.0, wedgeprops=dict(width=0.36, edgecolor="white"))
        ax.text(0.5,0.5,f"{v:.2f}", ha="center", va="center",
                fontsize=13, fontweight="bold", color=TOKENS["color"]["text"])
        ax.set_aspect("equal")
    host.plot(_plot); return host

def hbar(parent, labels, values, title=""):
    host = MatplotlibHost(parent, figsize=(4.6,2.4))
    def _plot(ax):
        y = list(range(len(labels)))
        ax.barh(y, values, color=TOKENS["color"]["primary"])
        ax.set_yticks(y); ax.set_yticklabels(labels)
        if title: ax.set_title(title, fontsize=10)
        ax.grid(axis="x", alpha=0.2)
    host.plot(_plot); return host

def line_plot(parent, series_dict: dict[str, list[float]], xlabel="", ylabel=""):
    host = MatplotlibHost(parent, figsize=(5.6,2.2))
    def _plot(ax):
        if not series_dict:
            ax.text(0.5,0.5,"No data", ha="center", va="center"); return
        for label, vals in series_dict.items():
            ax.plot(vals, label=label)
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.legend(loc="best")
    host.plot(_plot); return host

def hist_plot(parent, values, bins=10, title=""):
    host = MatplotlibHost(parent, figsize=(5.6,2.2))
    def _plot(ax):
        if not values: ax.text(0.5,0.5,"No data", ha="center", va="center")
        else: ax.hist(values, bins=bins)
        if title: ax.set_title(title)
    host.plot(_plot); return host

def corr_plot(parent, df_numeric):
    host = MatplotlibHost(parent, figsize=(5.6,2.6))
    def _plot(ax):
        if df_numeric.empty:
            ax.text(0.5,0.5,"No numeric data", ha="center", va="center"); return
        c = df_numeric.corr()
        im = ax.imshow(c, cmap="Blues", vmin=-1, vmax=1)
        ax.set_xticks(range(len(c.columns))); ax.set_xticklabels(c.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(c.columns))); ax.set_yticklabels(c.columns)
        host.fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    host.plot(_plot); return host
def line_semester(parent, labels: list[str], values: list[float], title=""):
    host = MatplotlibHost(parent, figsize=(7.2,2.8))
    def _plot(ax):
        n = len(values)
        if n == 0:
            ax.text(0.5,0.5,"Chưa có dữ liệu", ha="center", va="center"); return
        x = list(range(n))
        ax.plot(x, values, marker="o", linewidth=2, color=TOKENS["color"]["primary"])
        # số trên từng điểm
        for xi, yi in zip(x, values):
            ax.annotate(f"{yi:.2f}", (xi, yi), textcoords="offset points",
                        xytext=(0,8), ha="center", fontsize=9)
        ax.set_ylim(0, 10)
        ax.set_xticks(x); ax.set_xticklabels(labels)
        if title: ax.set_title(title, fontsize=11)
        ax.set_ylabel("GPA (10)")
        ax.grid(True, alpha=0.25)
    host.plot(_plot); return host

def hbar_labeled(parent, labels, values, right_text=None, title=""):
    # auto-height: 0.6 inch cho mỗi mục + nền tối thiểu
    height = max(2.4, 0.6 * max(1, len(labels)) + 1.0)
    host = MatplotlibHost(parent, figsize=(4.8, height))
    host.fig.subplots_adjust(left=0.35, right=0.95, top=0.9, bottom=0.1)
    def _plot(ax):
        m = max([10] + list(values))
        y = list(range(len(labels)))
        ax.barh(y, values, color=TOKENS["color"]["primary"], height=0.55)
        ax.set_yticks(y); ax.set_yticklabels(labels)
        ax.set_xlim(0, m * 1.12)
        for yi, val in enumerate(values):
            # txt = f"{val:.2f}/10"
            # if right_text and yi < len(right_text) and right_text[yi]:
            #     txt = right_text[yi] # Use provided text directly if available, assuming it contains value
            
            # The calling code passes full string in right_text.
            # Overview.py sends: "A . 8.80/10 . 3 TC"
            # We should just print that.
            
            txt = ""
            if right_text and yi < len(right_text):
                 txt = str(right_text[yi])
            else:
                 txt = f"{val:.2f}"

            ax.text(val + (m*0.02), yi, txt, va="center", ha="left", fontsize=9)
        if title: ax.set_title(title, fontsize=11)
        ax.grid(axis="x", alpha=0.2)
    host.plot(_plot); return host

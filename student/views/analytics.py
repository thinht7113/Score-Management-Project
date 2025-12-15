#student/views/analytics.py
# -*- coding: utf-8 -*-


from __future__ import annotations
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import numpy as np
import pandas as pd

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ---------- Helpers ----------

def _fmt(x, nd=2):
    try:
        if x is None or (isinstance(x, float) and np.isnan(x)):
            return "—"
        fmt = f"{{:.{nd}f}}"
        return fmt.format(float(x))
    except Exception:
        return str(x)


def _normalize_grades_df(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa DataFrame: ép kiểu và đảm bảo cột tối thiểu tồn tại."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["HocKy", "DiemHe10", "DiemHe4", "SoTinChi", "MaHP", "TenHP", "TinhTichLuy"])

    cols = {c.lower(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in df.columns:
                return n
            if n.lower() in cols:
                return cols[n.lower()]
        return None

    out = pd.DataFrame()
    out["HocKy"] = pd.to_numeric(df[pick("HocKy", "Hoc_ky", "Semester")] if pick("HocKy","Hoc_ky","Semester") else np.nan, errors="coerce").astype("Int64")

    for c, alt in [("DiemHe10", ("DiemHe10","Diem_10","Diem_He_10","Score10","Diem10")),
                   ("DiemHe4",  ("DiemHe4","Diem_4","Diem_He_4","Score4","Diem4")),
                   ("SoTinChi", ("SoTinChi","TinChi","TC","Credits"))]:
        col = pick(*alt)
        out[c] = pd.to_numeric(df[col], errors="coerce") if col else np.nan

    out["MaHP"]  = df[pick("MaHP","Ma_mon","CourseId")] if pick("MaHP","Ma_mon","CourseId") else ""
    out["TenHP"] = df[pick("TenHP","Ten_mon","CourseName")] if pick("TenHP","Ten_mon","CourseName") else ""

    acc = pick("TinhTichLuy","IsAccumulated","Accumulated","Tinh_tich_luy")
    if acc:
        out["TinhTichLuy"] = df[acc].astype(bool)
    else:
        out["TinhTichLuy"] = True  # mặc định tính tích lũy

    return out


def _weighted_gpa10(df: pd.DataFrame) -> float | None:
    d = df.dropna(subset=["DiemHe10", "SoTinChi"])
    if d.empty: return None
    w = d["SoTinChi"].to_numpy(dtype=float)
    v = d["DiemHe10"].to_numpy(dtype=float)
    if w.sum() == 0: return None
    return float((v * w).sum() / w.sum())


def _weighted_gpa4(df: pd.DataFrame) -> float | None:
    if "DiemHe4" not in df.columns: return None
    d = df.dropna(subset=["DiemHe4", "SoTinChi"])
    if d.empty: return None
    w = d["SoTinChi"].to_numpy(dtype=float)
    v = d["DiemHe4"].to_numpy(dtype=float)
    if w.sum() == 0: return None
    return float((v * w).sum() / w.sum())


def _pass_rate(df: pd.DataFrame) -> float | None:
    d = df.dropna(subset=["DiemHe10"])
    if d.empty: return None
    passed = (d["DiemHe10"] >= 4.0).sum()
    return passed * 100.0 / len(d)


def _gpa_trajectory(df: pd.DataFrame):
    """Trả về (x=list học kỳ), y10=list GPA10 theo kỳ, y4=list GPA4 theo kỳ."""
    if df.empty or "HocKy" not in df.columns:
        return [], [], []
    res_x, res_10, res_4 = [], [], []
    for hk, g in df.groupby("HocKy"):
        if pd.isna(hk):
            continue
        hk = int(hk)
        res_x.append(hk)
        res_10.append(_weighted_gpa10(g))
        res_4.append(_weighted_gpa4(g))
    pairs = sorted(zip(res_x, res_10, res_4), key=lambda t: t[0])
    if not pairs: return [], [], []
    x, y10, y4 = zip(*pairs)
    return list(x), list(y10), list(y4)


# ---------- Small UI widgets ----------

class Section(ctk.CTkFrame):
    """Khung có tiêu đề lớn, dùng grid để bố cục các phần tử con."""
    def __init__(self, master, title: str, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.grid_columnconfigure(0, weight=1)
        lbl = ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=16, weight="bold"))
        lbl.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))


class KPICard(ctk.CTkFrame):
    """Thẻ KPI đơn giản với tiêu đề + số lớn."""
    def __init__(self, master, title: str, value: str = "—", **kw):
        super().__init__(master, **kw)
        self.configure(corner_radius=12, fg_color=("#FFFFFF", "#0f172a"))
        ctk.CTkLabel(self, text=title, text_color=("gray20","gray70")).pack(anchor="w", padx=14, pady=(12, 0))
        self.val = ctk.CTkLabel(self, text=value, font=ctk.CTkFont(size=28, weight="bold"))
        self.val.pack(anchor="w", padx=14, pady=(2, 12))
    def set_value(self, s: str):
        self.val.configure(text=s or "—")


class MatplotlibHost(ctk.CTkFrame):
    """Khung chứa Figure Matplotlib và tiện ích vẽ qua callback."""
    def __init__(self, master, figsize=(8, 2.4), dpi=100, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.fig = Figure(figsize=figsize, dpi=dpi, layout="constrained")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.configure(highlightthickness=0, borderwidth=0)
        self.canvas_widget.pack(fill="both", expand=True)
    def plot(self, fn):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        try:
            fn(ax)
        finally:
            self.canvas.draw_idle()


# ---------- Main View ----------

class View(ctk.CTkFrame):
    def __init__(self, master, grades_df: pd.DataFrame, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.df_all = _normalize_grades_df(grades_df)
        self._build()

    # ===== UI build =====
    def _build(self):
        sc = ctk.CTkScrollableFrame(self, fg_color="transparent")
        sc.pack(fill="both", expand=True, padx=6, pady=(0, 10))

        head = Section(sc, "Phân tích học tập")
        head.pack(fill="x", padx=8, pady=(0, 6))

        # ==== Filter bar: "Kỳ:" sát dropdown ====
        sems = sorted([int(x) for x in self.df_all["HocKy"].dropna().unique().tolist()]) or []
        self.sem_var = tk.StringVar(value="Tất cả")
        self.acc_only = tk.BooleanVar(value=True)

        filter_bar = ctk.CTkFrame(head, fg_color="transparent")
        filter_bar.grid(row=1, column=0, sticky="w", padx=8, pady=(6, 8))

        ctk.CTkLabel(filter_bar, text="Kỳ:").pack(side="left", padx=(0, 6))
        ctk.CTkOptionMenu(
            filter_bar,
            values=["Tất cả"] + [f"Học kỳ {n}" for n in sems],
            variable=self.sem_var, command=lambda _=None: self._rebuild(),
            width=180, height=34
        ).pack(side="left")

        ctk.CTkCheckBox(
            filter_bar, text="Chỉ môn tính tích lũy",
            variable=self.acc_only, command=self._rebuild
        ).pack(side="left", padx=(12, 0))

        kpi = ctk.CTkFrame(sc, fg_color="transparent")
        kpi.pack(fill="x", padx=8, pady=(6, 2))
        kpi.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")

        self.kpi_gpa10 = KPICard(kpi, "CPA (10)", "—"); self.kpi_gpa10.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        self.kpi_gpa4  = KPICard(kpi, "CPA (4)",  "—"); self.kpi_gpa4 .grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        self.kpi_tc    = KPICard(kpi, "Tổng tín chỉ","—"); self.kpi_tc  .grid(row=0, column=2, padx=6, pady=6, sticky="nsew")
        self.kpi_pass  = KPICard(kpi, "Tỷ lệ qua (%)","—"); self.kpi_pass.grid(row=0, column=3, padx=6, pady=6, sticky="nsew")

        # helper: caption dưới chart
        def _note(container, text):
            ctk.CTkLabel(container, text=text, text_color=("#334155","#94a3b8"), wraplength=980, justify="left").grid(
                row=2, column=0, sticky="w", padx=8, pady=(0, 8)
            )

        sec_traj = Section(sc, "Xu hướng CPA"); sec_traj.pack(fill="x", padx=8, pady=(6, 6))
        self.host_traj = MatplotlibHost(sec_traj, figsize=(9.5, 3.2))  # was 2.8
        self.host_traj.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        _note(sec_traj, "Chú thích: Mỗi điểm là CPA có trọng số theo tín chỉ của từng học kỳ; xanh = thang 10, cam = thang 4.")

        sec_hist = Section(sc, "Phân bố điểm hệ 10"); sec_hist.pack(fill="x", padx=8, pady=(0, 6))
        self.host_hist = MatplotlibHost(sec_hist, figsize=(9.5, 2.8))  # was 2.4
        self.host_hist.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        _note(sec_hist, "Chú thích: Cột biểu diễn số lượng môn ở từng mức điểm (X: điểm hệ 10, Y: số môn). Đường đứt = trung bình; đường liền = trung vị.")

        sec_box = Section(sc, "Boxplot điểm"); sec_box.pack(fill="x", padx=8, pady=(0, 6))
        self.host_box = MatplotlibHost(sec_box, figsize=(9.5, 2.0))  # was 1.6
        self.host_box.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        _note(sec_box, "Chú thích: Hộp thể hiện Q1–Q3; vạch dày = trung vị; vạch đứt = trung bình; điểm lẻ là ngoại lệ.")

        sec_sc = Section(sc, "Tín chỉ vs. Điểm"); sec_sc.pack(fill="x", padx=8, pady=(0, 6))
        self.host_scatter = MatplotlibHost(sec_sc, figsize=(9.5, 3.0))  # was 2.6
        self.host_scatter.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        _note(sec_sc, "Chú thích: Mỗi chấm là một môn (X: số tín chỉ, Y: điểm hệ 10). Đường ngang 4.0 là mốc qua môn; chấm đỏ = dưới 4.0.")

        sec_hm = Section(sc, "Tương quan đặc trưng"); sec_hm.pack(fill="x", padx=8, pady=(0, 6))
        self.host_heat = MatplotlibHost(sec_hm, figsize=(5.6, 2.6))  # was 2.2
        self.host_heat.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))
        _note(sec_hm, "Chú thích: Bản đồ nhiệt hệ số tương quan (Pearson) giữa các cột. Dương = cùng chiều, âm = ngược chiều; |giá trị| càng lớn → quan hệ tuyến tính càng mạnh.")

        sec_tbl = Section(sc, "Môn kéo tụt CPA"); sec_tbl.pack(fill="both", padx=8, pady=(0, 8))
        sec_tbl.grid_columnconfigure(0, weight=1); sec_tbl.grid_rowconfigure(1, weight=1)
        self.tbl = ttk.Treeview(sec_tbl, columns=("hp","impact","detail"), show="headings", height=6)
        self.tbl.heading("hp", text="Học phần"); self.tbl.heading("impact", text="Tác động (↓)"); self.tbl.heading("detail", text="Điểm · TC")
        self.tbl.column("hp", width=560, anchor="w"); self.tbl.column("impact", width=120, anchor="e"); self.tbl.column("detail", width=160, anchor="e")
        self.tbl.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        vs = ttk.Scrollbar(sec_tbl, orient="vertical", command=self.tbl.yview)
        self.tbl.configure(yscroll=vs.set); vs.grid(row=1, column=1, sticky="ns", pady=8)
        _note(sec_tbl, "Chú thích: Sắp xếp theo mức làm giảm CPA = (CPA trung bình − điểm môn) × tín chỉ; hiển thị 8 môn có tác động xấu nhất.")

        self._rebuild()

    def _filtered(self) -> pd.DataFrame:
        df = self.df_all.copy()
        sem_txt = self.sem_var.get()
        if sem_txt and sem_txt != "Tất cả":
            try:
                hk = int(sem_txt.split()[-1])
                df = df[df["HocKy"] == hk]
            except Exception:
                pass
        if self.acc_only.get() and "TinhTichLuy" in df.columns:
            df = df[df["TinhTichLuy"] == True]
        return df

    def _rebuild(self):
        df = self._filtered()

        g10 = _weighted_gpa10(df); g4 = _weighted_gpa4(df)
        self.kpi_gpa10.set_value(_fmt(g10, 2)); self.kpi_gpa4.set_value(_fmt(g4, 2))
        self.kpi_tc.set_value(str(int(df["SoTinChi"].sum())) if "SoTinChi" in df.columns else "0")
        self.kpi_pass.set_value(_fmt(_pass_rate(df), 1))

        x, y10, y4 = _gpa_trajectory(df)
        def _plot_traj(ax):
            if not x:
                ax.text(0.5, 0.5, "(Không có dữ liệu kỳ)", ha="center", va="center", transform=ax.transAxes); return
            ax.plot(x, y10, marker="o", linewidth=2, label="CPA(10)")
            if any(v is not None for v in y4): ax.plot(x, y4, marker="o", linewidth=2, label="GPA(4)")
            for xx, yy in zip(x, y10):
                if yy is None: continue
                ax.text(xx, yy + 0.08, _fmt(yy, 2), ha="center", va="bottom", fontsize=9)
            ax.set_xlabel("Học kỳ"); ax.set_ylabel("CPA"); ax.set_xticks(x)
            ax.grid(True, alpha=0.15); ax.legend(loc="lower right")
        self.host_traj.plot(_plot_traj)

        points = df["DiemHe10"].dropna().astype(float).tolist() if "DiemHe10" in df.columns else []

        def _plot_hist(ax):
            if not points:
                ax.text(0.5, 0.5, "(Không có dữ liệu điểm)", ha="center", va="center", transform=ax.transAxes); return
            bins = min(10, max(5, int(len(points) / 2)))
            ax.hist(points, bins=bins, rwidth=0.92)
            mu, med = float(np.mean(points)), float(np.median(points))
            ymax = ax.get_ylim()[1]
            ax.axvline(mu, linestyle="--", linewidth=1)
            ax.axvline(med, linestyle="-", linewidth=1)
            ax.text(mu, ymax * 0.95, f"TB={_fmt(mu,2)}", rotation=90, va="top", ha="right", fontsize=9)
            ax.text(med, ymax * 0.95, f"TrV={_fmt(med,2)}", rotation=90, va="top", ha="left",  fontsize=9)
            ax.set_xlabel("Điểm hệ 10"); ax.set_ylabel("Số môn"); ax.grid(axis="y", alpha=0.15)
        self.host_hist.plot(_plot_hist)

        def _plot_box(ax):
            if not points:
                ax.text(0.5, 0.5, "(Không có dữ liệu điểm)", ha="center", va="center", transform=ax.transAxes); return
            ax.boxplot(points, vert=False, widths=0.6, showmeans=True, meanline=True)
            ax.set_xlabel("Điểm hệ 10"); ax.set_yticks([]); ax.grid(axis="x", alpha=0.15)
        self.host_box.plot(_plot_box)

        sc_df = df[df.get("DiemHe10").notna() & (df.get("SoTinChi", 0) > 0)] if not df.empty and "DiemHe10" in df.columns else pd.DataFrame()
        def _plot_sc(ax):
            if sc_df.empty:
                ax.text(0.5, 0.5, "(Không có dữ liệu)", ha="center", va="center", transform=ax.transAxes); return
            xs = sc_df["SoTinChi"].to_numpy(dtype=float) + (np.random.rand(len(sc_df)) - 0.5) * 0.15
            ys = sc_df["DiemHe10"].to_numpy(dtype=float)
            colors = np.where(ys >= 4.0, "#2563EB", "#EF4444")
            ax.scatter(xs, ys, s=42, alpha=0.85, c=colors, edgecolors="none")
            ax.axhline(4.0, linestyle="--", linewidth=1)  # mốc qua môn
            ax.set_xlabel("Số tín chỉ"); ax.set_ylabel("Điểm hệ 10"); ax.grid(True, alpha=0.15)
        self.host_scatter.plot(_plot_sc)

        def _plot_heat(ax):
            cols = [c for c in ["DiemHe10","DiemHe4","SoTinChi","HocKy"] if c in df.columns]
            if len(cols) < 2:
                ax.text(0.5, 0.5, "(Thiếu cột để tính tương quan)", ha="center", va="center", transform=ax.transAxes); return
            corr = df[cols].dropna().corr()
            im = ax.imshow(corr, vmin=-1, vmax=1)
            ax.set_xticks(range(len(cols))); ax.set_yticks(range(len(cols)))
            ax.set_xticklabels(cols, rotation=30, ha="right"); ax.set_yticklabels(cols)
            # giá trị tại từng ô
            for i in range(corr.shape[0]):
                for j in range(corr.shape[1]):
                    ax.text(j, i, _fmt(corr.values[i, j], 2), ha="center", va="center", fontsize=9)
            cbar = ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label("Hệ số tương quan")
        self.host_heat.plot(_plot_heat)

        for iid in self.tbl.get_children():
            self.tbl.delete(iid)
        if points:
            mu = float(np.mean(points))
            tmp = df[df["DiemHe10"].notna()].copy()
            tmp["impact"] = (mu - tmp["DiemHe10"].astype(float)) * tmp["SoTinChi"].astype(float)
            worst = tmp.sort_values("impact", ascending=False).head(8)
            for _, r in worst.iterrows():
                hp = f"{r.get('MaHP','')} — {r.get('TenHP','')}"
                detail = f"{_fmt(r['DiemHe10'],2)}/10 · {int(r['SoTinChi'])} TC"
                self.tbl.insert("", "end", values=(hp, _fmt(r['impact'],2), detail))


if __name__ == "__main__":

    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.geometry("1100x720")
    root.title("Analytics Demo")
    root.mainloop()

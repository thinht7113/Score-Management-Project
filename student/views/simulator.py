# student/views/simulator.py
from __future__ import annotations
import customtkinter as ctk
import tkinter as tk
import pandas as pd
import numpy as np
from ..widgets.charts import MatplotlibHost
from ..widgets.cards import Section, KPICard

def _to_num(s, d=0.0):
    try: return float(s)
    except Exception: return d

def _fmt(x, n=2):
    try: return f"{float(x):.{n}f}".rstrip("0").rstrip(".")
    except Exception: return str(x)

def _best_grades(grades: pd.DataFrame) -> pd.DataFrame:
    g = grades.copy()
    g["DiemHe10"] = pd.to_numeric(g["DiemHe10"], errors="coerce")
    g["SoTinChi"] = pd.to_numeric(g["SoTinChi"], errors="coerce").fillna(0).astype(int)
    g["HocKy"]    = pd.to_numeric(g["HocKy"], errors="coerce")
    g = g.sort_values(["MaHP","DiemHe10","HocKy"], ascending=[True, False, True])
    return g.groupby("MaHP", as_index=False).first()

def _weighted_gpa10(df: pd.DataFrame) -> float:
    d = df[(pd.notnull(df["DiemHe10"])) & (df["SoTinChi"]>0)]
    if d.empty: return 0.0
    return float((d["DiemHe10"]*d["SoTinChi"]).sum()/d["SoTinChi"].sum())

def _traj_by_semester(df: pd.DataFrame):
    d = df[(pd.notnull(df["DiemHe10"])) & (df["SoTinChi"]>0)].copy()
    if "HocKy" not in d.columns or d["HocKy"].isna().all(): return [], []
    wsum = (d["DiemHe10"]*d["SoTinChi"]).groupby(d["HocKy"]).sum()
    csum = d["SoTinChi"].groupby(d["HocKy"]).sum()
    g = (wsum/csum).astype(float).sort_index()
    labs = [f"HK{int(k)}" for k in g.index.tolist()]
    vals = g.values.tolist()
    return labs, vals

class View(ctk.CTkFrame):

    def __init__(self, master, grades_df: pd.DataFrame,
                 curriculum_df: pd.DataFrame | None = None, plan_df: pd.DataFrame | None = None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self.grades_df = grades_df.copy()
        if curriculum_df is None and plan_df is not None: curriculum_df = plan_df
        self.curriculum_df = curriculum_df.copy() if curriculum_df is not None else None

        for c in ["MaHP","TenHP","SoTinChi","DiemHe10","HocKy","TinhDiemTichLuy"]:
            if c not in self.grades_df.columns: self.grades_df[c] = None
        self.grades_df["SoTinChi"] = pd.to_numeric(self.grades_df["SoTinChi"], errors="coerce").fillna(0).astype(int)
        self.grades_df["HocKy"]    = pd.to_numeric(self.grades_df["HocKy"], errors="coerce")

        self._inputs: dict[str, tk.DoubleVar] = {}
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._base: dict[str, float] = {}

        self.target_var = tk.DoubleVar(value=0.0)
        self.delta_var  = tk.DoubleVar(value=0.0)

        self.filter_var = tk.StringVar(value="Tất cả")
        self.search_var = tk.StringVar(value="")

        self._build()

    def _build(self):
        # --- Header / Tip ---
        tip_frame = ctk.CTkFrame(self, fg_color="#EFF6FF", corner_radius=8)
        tip_frame.pack(fill="x", padx=16, pady=(10, 12))
        
        ctk.CTkLabel(tip_frame, text="💡 HƯỚNG DẪN MÔ PHỎNG", text_color="#1E40AF", 
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=12, pady=(8,2))
        
        tip = (
            "• Bước 1: Nhập điểm giả định cho các môn bên trái (môn chưa học hoặc muốn cải thiện).\n"
            "• Bước 2: Hoặc nhập 'CPA mục tiêu' bên phải để hệ thống tự gợi ý điểm số cần đạt.\n"
            "• Bước 3: Dùng thanh trượt '+Δ' để tăng giảm đồng loạt điểm giả định."
        )
        ctk.CTkLabel(tip_frame, text=tip, text_color="#1E3A8A", justify="left",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=12, pady=(0,8))

        # --- Main Grid ---
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=8, pady=(0,8))
        grid.grid_columnconfigure(0, weight=2, uniform="g") # Left column (Subject list)
        grid.grid_columnconfigure(1, weight=3, uniform="g") # Right column (Controls & Charts)
        grid.grid_rowconfigure(0, weight=1)

        # === LEFT PANEL ===
        self._build_left_panel(grid)

        # === RIGHT PANEL ===
        self._build_right_panel(grid)

        self._build_candidates()
        self._recalc()

    def _build_left_panel(self, parent):
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_rowconfigure(2, weight=1)

        # 1. Filter & Search Bar
        bar = ctk.CTkFrame(left, fg_color="white", corner_radius=8, height=50)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        ctk.CTkLabel(bar, text="Lọc:", text_color="#6B7280", font=ctk.CTkFont(size=12, weight="bold"))\
            .pack(side="left", padx=(12, 4))
        
        ctk.CTkOptionMenu(bar, variable=self.filter_var, values=["Tất cả", "Chưa đạt", "Chưa học"],
                          width=110, fg_color="#F3F4F6", text_color="#111827", button_color="#D1D5DB",
                          command=lambda *_: self._build_candidates()).pack(side="left")

        ctk.CTkLabel(bar, text="Tìm:", text_color="#6B7280", font=ctk.CTkFont(size=12, weight="bold"))\
            .pack(side="left", padx=(16, 4))
        
        srch = ctk.CTkEntry(bar, textvariable=self.search_var, width=180, placeholder_text="Mã hoặc tên môn...")
        srch.pack(side="left", padx=(0, 12), fill="x", expand=True)
        srch.bind("<KeyRelease>", lambda *_: self._build_candidates())

        # 2. List Header
        header = ctk.CTkFrame(left, fg_color="#E5E7EB", corner_radius=6, height=32)
        header.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(header, text="MÔN HỌC", font=ctk.CTkFont(size=11, weight="bold"), text_color="#374151")\
            .pack(side="left", padx=12)
        ctk.CTkLabel(header, text="GIẢ ĐỊNH", font=ctk.CTkFont(size=11, weight="bold"), text_color="#374151")\
            .pack(side="right", padx=12)

        # 3. Scrollable List
        self.list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent", corner_radius=0)
        self.list_frame.grid(row=2, column=0, sticky="nsew")

    def _build_right_panel(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        # 1. KPI Cards
        kpi_box = ctk.CTkFrame(right, fg_color="transparent")
        kpi_box.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        kpi_box.grid_columnconfigure((0, 1, 2), weight=1, uniform="k")

        self.kpi_now = KPICard(kpi_box, "CPA HIỆN TẠI", "—", color="#4B5563")
        self.kpi_now.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.kpi_sim = KPICard(kpi_box, "CPA MÔ PHỎNG", "—", color="#2563EB") # Blue
        self.kpi_sim.grid(row=0, column=1, sticky="ew", padx=6)

        self.kpi_gap = KPICard(kpi_box, "THAY ĐỔI (+/-)", "—", color="#059669") # Green
        self.kpi_gap.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        # 2. Control Panel (Target & Tools)
        ctrl = Section(right, "🎯 Bảng điều khiển")
        ctrl.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        
        # Row 1: Target CPA
        r1 = ctk.CTkFrame(ctrl, fg_color="transparent")
        r1.grid(row=1, column=0, sticky="ew", padx=12, pady=12)
        
        ctk.CTkLabel(r1, text="Mục tiêu CPA:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.target_entry = ctk.CTkEntry(r1, width=70, font=ctk.CTkFont(weight="bold"), justify="center")
        self.target_entry.pack(side="left", padx=8)
        self.target_entry.bind("<KeyRelease>", lambda _: self._suggest_for_target())
        self.target_entry.bind("<FocusOut>", lambda _: self._suggest_for_target())

        ctk.CTkLabel(r1, text="(Nhập để tự động gợi ý)", text_color="#6B7280", font=ctk.CTkFont(size=11, slant="italic"))\
            .pack(side="left")

        # Presets
        ctk.CTkButton(r1, text="8.0 (Giỏi)", width=70, fg_color="#DBEAFE", text_color="#1E40AF", hover_color="#BFDBFE",
                      command=lambda: self._set_target(8.0)).pack(side="right", padx=(4,0))
        ctk.CTkButton(r1, text="7.0 (Khá)", width=70, fg_color="#DBEAFE", text_color="#1E40AF", hover_color="#BFDBFE",
                      command=lambda: self._set_target(7.0)).pack(side="right")

        # Row 2: Batch Increase
        r2 = ctk.CTkFrame(ctrl, fg_color="transparent")
        r2.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        
        ctk.CTkLabel(r2, text="Tăng/Giảm đồng loạt:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.delta_scale = ctk.CTkSlider(r2, from_=-2.0, to=2.0, number_of_steps=40, width=180,
                                         command=lambda v: self._apply_batch_delta(float(v)))
        self.delta_scale.set(0)
        self.delta_scale.pack(side="left", padx=12, fill="x", expand=True)
        
        ctk.CTkButton(r2, text="↺ Đặt lại", width=80, fg_color="#F3F4F6", text_color="#374151", hover_color="#E5E7EB",
                      command=self._reset_suggestion).pack(side="right")

        chart_sec = Section(right, "📈 Xu hướng CPA")
        chart_sec.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        chart_sec.grid_rowconfigure(1, weight=1) 
        right.grid_rowconfigure(2, weight=1)
        
        self.host = MatplotlibHost(chart_sec, figsize=(5, 2.5))
        self.host.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)

    def _set_target(self, val):
        self.target_entry.delete(0, "end")
        self.target_entry.insert(0, str(val))
        self._suggest_for_target()

    def _build_candidates(self):
        for w in self.list_frame.winfo_children(): w.destroy()
        self._inputs.clear()
        self._entries.clear()

        best = _best_grades(self.grades_df)
        passed_codes = set(best.loc[(best["DiemHe10"]>=4.0) & best["DiemHe10"].notna(), "MaHP"].tolist())
        failed = best[(best["DiemHe10"]<4.0) | (best["DiemHe10"].isna())].copy()

        cand = pd.DataFrame(columns=["MaHP","TenHP","SoTinChi","HocKy","DiemHe10","_status"])
        if not failed.empty:
            tmp = failed[["MaHP","TenHP","SoTinChi","HocKy","DiemHe10"]].copy()
            tmp["_status"] = np.where(tmp["DiemHe10"].notna() & (tmp["DiemHe10"]<4.0), "Chưa đạt", "Chưa học")
            cand = pd.concat([cand, tmp], ignore_index=True)

        if self.curriculum_df is not None and not self.curriculum_df.empty:
            cur = self.curriculum_df.copy()
            for c in ["MaHP","TenHP","SoTinChi","HocKy","HKGoiY"]:
                if c not in cur.columns: cur[c] = None
            cur["HocKy"] = pd.to_numeric(cur["HocKy"], errors="coerce")\
                .fillna(pd.to_numeric(cur["HKGoiY"], errors="coerce"))
            cur = cur[~cur["MaHP"].isin(passed_codes)]
            cur = cur[~cur["MaHP"].isin(cand["MaHP"])]
            cur = cur.assign(DiemHe10=np.nan, _status="Chưa học")
            cand = pd.concat([cand, cur[["MaHP","TenHP","SoTinChi","HocKy","DiemHe10","_status"]]], ignore_index=True)

        view = self.filter_var.get()
        key  = self.search_var.get().strip().lower()
        if view in ("Chưa đạt","Chưa học"):
            cand = cand[cand["_status"] == view]
        if key:
            cand = cand[cand.apply(lambda r: key in str(r["MaHP"]).lower() or key in str(r["TenHP"]).lower(), axis=1)]

        if cand.empty:
            ctk.CTkLabel(self.list_frame, text="Không tìm thấy môn học nào.", text_color="#6B7280")\
                .pack(pady=20)
            return

        # Group by Semester for better organization
        cand["HocKy"] = pd.to_numeric(cand["HocKy"], errors="coerce").fillna(999)
        groups = cand.groupby("HocKy")
        
        for hk, group in sorted(groups):
            hk_label = f"Học kỳ {int(hk)}" if hk != 999 else "Môn chưa xếp kỳ"
            ctk.CTkLabel(self.list_frame, text=hk_label, text_color="#374151", 
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=8, pady=(12,4))
            
            for _, r in group.sort_values("TenHP").iterrows():
                self._render_row(r)

    def _render_row(self, r):
        card = ctk.CTkFrame(self.list_frame, fg_color="white", corner_radius=6)
        card.pack(fill="x", padx=4, pady=2)
        
        # Configure grid columns: 0=Strip, 1=Text(Expand), 2=Input
        card.grid_columnconfigure(1, weight=1) 

        # Status indicator strip
        status = r.get('_status')
        strip_color = "#EF4444" if status == "Chưa đạt" else "#9CA3AF" # Red or Gray
        # Fix: Force small height so it doesn't expand row to default 200px
        strip = ctk.CTkFrame(card, width=4, height=20, fg_color=strip_color, corner_radius=0)
        strip.grid(row=0, column=0, rowspan=2, sticky="ns")

        # Title
        title = f"{r['TenHP']}"
        title_lbl = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"), 
                                 text_color="#111827", anchor="w", justify="left")
        title_lbl.grid(row=0, column=1, sticky="ew", padx=(8, 4), pady=(3, 0))

        # Subtitle
        sub = f"{r['MaHP']} • {int(_to_num(r.get('SoTinChi'), 0))} TC"
        sub_lbl = ctk.CTkLabel(card, text=sub, font=ctk.CTkFont(size=10), 
                               text_color="#6B7280", anchor="w")
        sub_lbl.grid(row=1, column=1, sticky="ew", padx=(8, 4), pady=(0, 3))

        # Input
        code = str(r["MaHP"])
        var = tk.DoubleVar(value=8.0)
        
        if code in self._base:
            var.set(self._base[code])
        
        ent = ctk.CTkEntry(card, width=45, height=24, font=ctk.CTkFont(size=12, weight="bold"), justify="center")
        ent.grid(row=0, column=2, rowspan=2, padx=8, sticky="e")
        ent.insert(0, _fmt(var.get()))

        def _bind(_=None, _var=var, _ent=ent, _code=code):
            try:
                val = float(_ent.get())
                val = max(0.0, min(10.0, val))
                _var.set(val)
                self._base[_code] = val 
                
                if self.delta_scale.get() != 0:
                    self.delta_scale.set(0)
            except Exception:
                pass
            self._recalc()

        ent.bind("<KeyRelease>", _bind)
        ent.bind("<FocusOut>", _bind)

        self._inputs[code] = var
        self._entries[code] = ent
        if code not in self._base:
            self._base[code] = var.get()

        # Dynamic wraplength
        def _update_wrap(event):
            # Width of card - strip (4) - entry (45+16) - padding (~20) = ~85
            # Ensure we don't get negative width
            width = max(50, event.width - 90)
            title_lbl.configure(wraplength=width)
        
        card.bind("<Configure>", _update_wrap)

    def _effective_best_with_sim(self) -> pd.DataFrame:
        best = _best_grades(self.grades_df)
        for code, var in self._inputs.items():
            sim = _to_num(var.get(), 0.0)
            sim = 0.0 if sim < 0 else (10.0 if sim > 10 else sim)
            mask = best["MaHP"] == code
            if mask.any():
                old = best.loc[mask, "DiemHe10"].values[0]
                if pd.isna(old) or sim > float(old):
                    best.loc[mask, "DiemHe10"] = sim
            else:
                info = None
                if self.curriculum_df is not None:
                    q = self.curriculum_df[self.curriculum_df["MaHP"] == code]
                    if not q.empty: info = q.iloc[0].to_dict()
                best = pd.concat([best, pd.DataFrame([{
                    "MaHP": code,
                    "TenHP": (info or {}).get("TenHP", code),
                    "SoTinChi": int(_to_num((info or {}).get("SoTinChi"), 0)),
                    "DiemHe10": sim,
                    "HocKy": _to_num((info or {}).get("HocKy"), np.nan)
                }])], ignore_index=True)
        return best

    def _required_avg_for_remaining(self, target: float) -> tuple[float, int]:
        best = _best_grades(self.grades_df)
        best["DiemHe10"] = pd.to_numeric(best["DiemHe10"], errors="coerce")
        best["SoTinChi"] = pd.to_numeric(best["SoTinChi"], errors="coerce").fillna(0).astype(int)

        have = best[best["DiemHe10"].notna()]
        done_w = (have["DiemHe10"]*have["SoTinChi"]).sum()
        done_c = have["SoTinChi"].sum()

        remain_c = 0
        remain_c += best[best["DiemHe10"].isna()]["SoTinChi"].sum()
        if self.curriculum_df is not None and not self.curriculum_df.empty:
            cur = self.curriculum_df.copy()
            for c in ["MaHP","SoTinChi"]:
                if c not in cur.columns: cur[c] = None
            cur["SoTinChi"] = pd.to_numeric(cur["SoTinChi"], errors="coerce").fillna(0).astype(int)
            learned = set(best["MaHP"].tolist())
            remain_c += cur[~cur["MaHP"].isin(learned)]["SoTinChi"].sum()

        total_c = done_c + remain_c
        if total_c <= 0 or remain_c <= 0:
            return (0.0, 0)
        required_sum = target*total_c - done_w
        need_avg = float(required_sum / remain_c)
        return (need_avg, int(remain_c))

    def _apply_batch_delta(self, delta: float):
        # Apply delta relative to the BASE value of each input
        for code, var in self._inputs.items():
            base = self._base.get(code, 8.0)
            v = base + float(delta)
            v = max(0.0, min(10.0, v))
            var.set(v)
            
            # Update entry text visually
            if code in self._entries:
                try:
                    self._entries[code].delete(0, "end")
                    self._entries[code].insert(0, _fmt(v))
                except Exception:
                    pass
        
        self._recalc()

    def _reset_suggestion(self):
        self.delta_scale.set(0.0)
        self.target_entry.delete(0, "end")
        self._base.clear() # Clear base to reset to default 8.0
        self._build_candidates() # Rebuild to reset all to 8.0
        self._recalc()

    def _suggest_for_target(self):
        try:
            val_str = self.target_entry.get()
            if not val_str: return
            target = float(val_str)
        except Exception:
            return
        target = max(0.0, min(10.0, target))

        need_avg, remain_c = self._required_avg_for_remaining(target)
        if remain_c <= 0:
            self._recalc(); return

        suggested_score = min(10.0, max(0.0, need_avg))
        
        # Update all inputs to this suggested score
        for code, var in self._inputs.items():
            var.set(suggested_score)
            self._base[code] = suggested_score # Update base so delta works from here
            
            # Update entry text visually
            if code in self._entries:
                try:
                    self._entries[code].delete(0, "end")
                    self._entries[code].insert(0, _fmt(suggested_score))
                except Exception:
                    pass
            
        self._recalc()

    def _recalc(self):
        base_best = _best_grades(self.grades_df)
        now = _weighted_gpa10(base_best); self.kpi_now.set_value(_fmt(now,2))

        eff = self._effective_best_with_sim()
        sim = _weighted_gpa10(eff); self.kpi_sim.set_value(_fmt(sim,2))
        
        # Update Target Entry to match Sim if not focused (Sync Target with Reality)
        try:
            if self.focus_get() != self.target_entry._entry:
                self.target_entry.delete(0, "end")
                self.target_entry.insert(0, _fmt(sim))
        except Exception:
            pass
        
        gap = sim - now
        gap_str = f"+{_fmt(gap, 2)}" if gap >= 0 else _fmt(gap, 2)
        self.kpi_gap.set_value(gap_str)
        
        # Colorize GAP
        if gap > 0: self.kpi_gap.value_label.configure(text_color="#059669") # Green
        elif gap < 0: self.kpi_gap.value_label.configure(text_color="#DC2626") # Red
        else: self.kpi_gap.value_label.configure(text_color="#6B7280") # Gray

        labs_now, vals_now = _traj_by_semester(base_best)
        labs_sim, vals_sim = _traj_by_semester(eff)
        
        def _plot(ax):
            ax.clear()
            if not vals_now and not vals_sim:
                ax.text(0.5,0.5,"(Chưa có dữ liệu)", ha="center", va="center"); return
                
            all_labs = sorted(set(labs_now) | set(labs_sim), key=lambda s: int(str(s).replace("HK","") or 0))
            def series(labs, vals):
                m = {l:v for l,v in zip(labs, vals)}
                return [m.get(lb, np.nan) for lb in all_labs]
            
            x = range(len(all_labs))
            y_now = series(labs_now, vals_now)
            y_sim = series(labs_sim, vals_sim)

            ax.plot(x, y_now, marker="o", markersize=4, linewidth=2, color="#9CA3AF", label="Hiện tại", linestyle="--")
            ax.plot(x, y_sim, marker="o", markersize=4, linewidth=2, color="#2563EB", label="Mô phỏng")
            
            ax.set_xticks(x)
            ax.set_xticklabels(all_labs, fontsize=8)
            ax.grid(True, linestyle=":", alpha=0.6)
            ax.legend(loc="upper left", fontsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

        self.host.plot(_plot)

        try:
            target = float(self.target_entry.get())
        except Exception:
            target = now
        need_avg, remain_c = self._required_avg_for_remaining(target)
        hint = f"Để đạt CPA { _fmt(target) }: cần TB ≈ { _fmt(max(0, min(10, need_avg)),2) } trên {remain_c} TC còn lại."
        self.kpi_sim.set_tooltip(hint) if hasattr(self.kpi_sim, "set_tooltip") else None

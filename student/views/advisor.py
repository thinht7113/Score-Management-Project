# student/views/advisor.py
from __future__ import annotations
import customtkinter as ctk
import json, threading, traceback

SYSTEM_PROMPT = (
    "Bạn là cố vấn học tập cho sinh viên Việt Nam. "
    "Trả lời ngắn gọn, rõ ràng; dùng gạch đầu dòng khi hợp lý; "
    "tập trung đăng ký học phần, chiến lược học, cải thiện GPA."
)
BUBBLE_GAP = 3
BUBBLE_PADY = 10
BUBBLE_PADX = 12
def _pretty(s: str) -> str:
    return (s or "").replace("**", "").strip()

class View(ctk.CTkFrame):

    def __init__(self, master, grades_df=None, plan_df=None, profile=None, app=None):
        super().__init__(master, fg_color="transparent")
        self.app = app or getattr(master, "app", None) or getattr(getattr(master, "master", None), "app", None)
        if self.app is None or not hasattr(self.app, "app_state"):
            raise RuntimeError("Advisor.View cần gọi: advisor.View(..., app=self.app) từ ShellView")

        self.grades_df = grades_df
        self.plan_df   = plan_df
        self.profile   = profile or {}

        cache = getattr(self.app, "app_state", None)
        if not hasattr(cache, "cache"):
            cache.cache = {}
        self._history = cache.cache.get("advisor_history") or []  # [(role,text)]
        cache.cache["advisor_history"] = self._history

        self._ctx_sent_once = False
        self._build()

    def _ctx_json(self) -> dict:
        data = {}
        try:
            if self.grades_df is not None and not self.grades_df.empty:
                data["grades"] = self.grades_df[["HocKy", "MaHP", "TenHP", "SoTinChi", "DiemHe10", "DiemChu"]] \
                    .astype({"HocKy":"string"}).to_dict(orient="records")
            if self.plan_df is not None and not self.plan_df.empty:
                data["plan"] = self.plan_df[["HocKy", "MaHP", "TenHP", "SoTinChi"]].to_dict(orient="records")
        except Exception:
            pass
        return data

    def _push(self, role: str, text: str):
        self._history.append((role, text))
        self.app.app_state.cache["advisor_history"] = self._history
        self._bubble(text, role)
        self._scroll_end()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10,4))
        ctk.CTkLabel(hdr, text="AI Chat — Cố vấn học tập",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkButton(hdr, text="Cuộc trò chuyện mới", command=self._reset).pack(side="right")

        self._ctx_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self, text="Gửi kèm dữ liệu học tập", variable=self._ctx_var)\
            .grid(row=0, column=0, sticky="w", padx=12, pady=(44,0))

        self._sf = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._sf.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6,8))

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="ew", padx=12, pady=(0,10))
        bottom.grid_columnconfigure(0, weight=1)
        self._entry = ctk.CTkEntry(bottom, placeholder_text="Nhập câu hỏi…", height=44)
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0,8))
        self._entry.bind("<Return>", lambda e: (self._on_send(), "break"))
        ctk.CTkButton(bottom, text="Gửi", height=44, command=self._on_send).grid(row=0, column=1)

        if not self._history:
            self._push("assistant",
                       "Xin chào 👋 Mình là Cố vấn học tập AI. Bạn cần hỗ trợ gì về việc học?")
        else:
            self.after(150, self._load_history)

    def _load_history(self):
        try:
            for r, t in self._history:
                self._bubble(t, r)
            self._scroll_end()
        except Exception:
            pass


    def _bubble(self, text: str, role: str):

        row = ctk.CTkFrame(self._sf, fg_color="transparent")
        row.pack(fill="x", pady=BUBBLE_GAP)  # trước đây: pady=6
        host = ctk.CTkFrame(row, fg_color="transparent")
        host.pack(fill="x")

        is_user = (role == "user")
        lbl = ctk.CTkLabel(
            host, text=_pretty(text), justify="left", anchor="w",
            fg_color=("#E9EEF6" if not is_user else "#2563EB"),
            text_color=("black" if not is_user else "white"),
            corner_radius=14, padx=BUBBLE_PADX, pady=BUBBLE_PADY,
            wraplength=max(360, min(int(self._sf.winfo_width() * 0.68), 820))
        )
        lbl.pack(side=("right" if is_user else "left"), padx=6)

    def _scroll_end(self):
        try:
            canvas = getattr(self._sf, "_parent_canvas", None) or self._sf
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _reset(self):
        self._history.clear()
        self._ctx_sent_once = False
        self.app.app_state.cache["advisor_history"] = self._history
        for w in self._sf.winfo_children(): w.destroy()
        self._push("assistant", "Bắt đầu cuộc trò chuyện mới. Bạn muốn hỏi điều gì?")

    def _on_send(self):
        q = (self._entry.get() or "").strip()
        if not q:
            return
        self._entry.delete(0, "end")
        self._push("user", q)

        row = ctk.CTkFrame(self._sf, fg_color="transparent")
        row.pack(fill="x", pady=BUBBLE_GAP)
        host = ctk.CTkFrame(row, fg_color="transparent")
        host.pack(fill="x")
        pending = ctk.CTkLabel(
            host, text="Đang soạn…", justify="left", anchor="w",
            fg_color="#E9EEF6", text_color="black",
            corner_radius=14, padx=BUBBLE_PADX, pady=BUBBLE_PADY
        )
        pending.pack(side="left", padx=6)
        self._scroll_end()

        def run():
            try:
                payload = {
                    "session_id": getattr(self.app.app_state, "advisor_session_id", "default"),
                    "messages": [{"role": r, "text": t} for (r, t) in self._history],
                    "use_context": bool(self._ctx_var.get() and not self._ctx_sent_once),
                }
                if payload["use_context"]:
                    payload["context"] = self._ctx_json()

                print("[advisor] send payload:", json.dumps(payload, ensure_ascii=False)[:800])
                ok, data = self.app.api_client.advisor_chat(payload)

                if ok:
                    text = _pretty((data or {}).get("text") or "") or "AI không có phản hồi khả dụng."
                    if payload["use_context"]:
                        self._ctx_sent_once = True
                else:
                    print("[advisor] backend error payload:", data)
                    if isinstance(data, dict):
                        if "trace" in data:
                            print("[advisor] server trace:\n", data["trace"])
                        text = data.get("detail") or data.get("text") or "Không rõ lỗi"
                    else:
                        text = "Không rõ lỗi"

                def adopt():
                    pending.configure(text=text)
                    self._history.append(("assistant", text))
                    self.app.app_state.cache["advisor_history"] = self._history
                    self._scroll_end()

                self.after(0, adopt)

            except Exception as ex:
                print("[advisor] client exception:", type(ex).__name__, ex)
                print(traceback.format_exc())
                msg = f"Lỗi hệ thống: {type(ex).__name__}: {ex}"
                self.after(0, lambda: (
                    pending.configure(text=msg),
                    self._history.append(("assistant", msg)),
                    self._scroll_end()
                ))

        threading.Thread(target=run, daemon=True).start()

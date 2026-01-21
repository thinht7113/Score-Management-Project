import os
import json
import traceback
import google.generativeai as genai
from flask import Blueprint, jsonify, request, current_app

bp = Blueprint("advisor", __name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = (
    "Bạn là cố vấn học tập cho sinh viên Việt Nam. "
    "Trả lời ngắn gọn, rõ ràng; dùng gạch đầu dòng; tập trung tư vấn đăng ký học phần và cải thiện GPA."
    "Các nội dung cần biết:CPA(Cumulative Point Average) là điểm trung bình tích lũy của toàn bộ quá trình học tập từ đầu đến thời điểm hiện tại, phản ánh tổng thể năng lực học thuật,GPA (Grade Point Average) là Là điểm trung bình các môn học đạt được trong một khóa học hoặc kỳ học cụ thể. Đây là thước đo kết quả học tập trong một giai đoạn."
)

@bp.post("/api/advisor/gemini")
def advisor_gemini():
    if not GEMINI_API_KEY:
        return jsonify({"detail": "Thiếu GEMINI_API_KEY cấu hình server"}), 500

    try:
        data = request.get_json(force=True) or {}
        history = data.get("messages", [])
        use_ctx = bool(data.get("use_context"))
        ctx = data.get("context") if use_ctx else None

        current_app.logger.info("[advisor] use_ctx=%s, messages=%d", use_ctx, len(history))

        parts = [{"text": SYSTEM_PROMPT}]
        if use_ctx and ctx:
            parts.append({"text": "DỮ LIỆU HỌC TẬP JSON (chỉ dùng lập luận, không lặp lại):"})
            try:
                parts.append({"text": json.dumps(ctx, ensure_ascii=False)[:5000]})
            except Exception:
                pass

        for m in history:
            r = (m.get("role") or "user")
            t = (m.get("text") or "")
            if not t:
                continue
            parts.append({"text": ("USER: " if r == "user" else "AI: ") + t})

        model = genai.GenerativeModel(MODEL_NAME)
        resp = model.generate_content(parts)
        text = (getattr(resp, "text", "") or "").strip() or "Mình chưa nhận được nội dung khả dụng."
        return jsonify({"text": text})

    except Exception as e:
        current_app.logger.exception("[advisor] ERROR: %s", e)
        return jsonify({
            "detail": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc(limit=5),
        }), 500

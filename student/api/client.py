# student/api/client.py
from __future__ import annotations
import  os
import json, requests, traceback
class APIClient:
    def __init__(self, base_url=None, token_getter=None):
        self.base_url = base_url or os.environ.get("API_BASE_URL","http://127.0.0.1:5000")
        self._token_getter = token_getter

    def login(self, username, password):
        url = f"{self.base_url}/api/auth/login"
        try:
            r = requests.post(url, json={"username":username,"password":password}, timeout=10)
            if r.ok: return True, r.json()
            try: return False, r.json().get("message")
            except Exception: return False, r.text
        except Exception as e:
            return False, str(e)

    def fetch_student_data(self, token):
        url = f"{self.base_url}/api/student/data"
        try:
            r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            if r.ok: return True, r.json()
            try: return False, r.json().get("message")
            except Exception: return False, r.text
        except Exception as e:
            return False, str(e)

    def _auth_header(self):
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if callable(self._token_getter):
            tok = self._token_getter()
            if tok:
                h["Authorization"] = "Bearer " + tok
        return h

    def advisor_chat(self, payload: dict):
        url = f"{self.base_url}/api/advisor/gemini"
        try:
            print("[advisor_chat] POST", url)
            print("[advisor_chat] payload:", json.dumps(payload, ensure_ascii=False)[:800])

            r = requests.post(url, headers=self._auth_header(), json=payload, timeout=45)

            if not r.ok:
                print("[advisor_chat] HTTP", r.status_code)
                print("[advisor_chat] TEXT:", r.text)

            is_json = "application/json" in (r.headers.get("content-type") or "")
            data = r.json() if is_json else {"text": r.text}
            return r.ok, data
        except Exception as e:
            print("[advisor_chat] EXCEPTION:", type(e).__name__, e)
            print(traceback.format_exc())
            return False, {"detail": f"{type(e).__name__}: {e}"}

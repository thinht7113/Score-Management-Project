# verify_fix.py
import requests
import json

BASE_URL = "http://127.0.0.1:5000"
S = requests.Session()

def login():
    try:
        r = S.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
        if r.status_code == 200:
            token = r.json().get("access_token")
            S.headers.update({"Authorization": f"Bearer {token}"})
            print("Login success")
            return True
        else:
            print("Login failed:", r.text)
            return False
    except Exception as e:
        print("Login error (is server running?):", e)
        return False

def check_cases():
    try:
        r = S.get(f"{BASE_URL}/api/admin/warning/cases")
        if r.status_code != 200:
            print("Failed to get cases:", r.status_code)
            return
        
        data = r.json()
        items = data.get("items", [])
        print(f"Got {len(items)} cases.")
        if items:
            c = items[0]
            print("Sample case:", json.dumps(c, indent=2))
            # Verify fields
            if "RuleCode" not in c:
                print("ERROR: Missing RuleCode in response")
            else:
                print("OK: RuleCode present")
            
            val = c.get("Value")
            if isinstance(val, float):
                 print(f"OK: Value is float ({val})")
            else:
                 print(f"WARN: Value is {type(val)}")

    except Exception as e:
        print("Check cases error:", e)

if __name__ == "__main__":
    if login():
        check_cases()

# run_backend.py
import os, sys
from pathlib import Path

BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys.executable).parent))
sys.path.insert(0, str(BASE))

from backend.app import create_app
from backend.models import db

app = create_app()
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False, threaded=False)

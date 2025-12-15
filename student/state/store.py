# student/state/store.py
import pandas as pd


class AppState:
    def __init__(self):
        self.token: str | None = None
        self.user: dict | None = None
        self.grades_df: pd.DataFrame | None = None
        self.plan_df: pd.DataFrame | None = None
        self.profile: dict = {}
        from uuid import uuid4

        self.advisor_messages = []
        self.advisor_use_context = True
        self.advisor_session_id = uuid4().hex

    def advisor_reset(self):
        from uuid import uuid4
        self.advisor_messages = []
        self.advisor_session_id = uuid4().hex
# student/services/auth_service.py
class AuthService:
    def __init__(self, api_client):
        self.client = api_client

    def login(self, username, password):
        return self.client.login(username, password)

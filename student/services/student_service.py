# student/services/student_service.py
class StudentService:
    def __init__(self, api_client):
        self.client = api_client

    def get_data(self, token):
        return self.client.fetch_student_data(token)

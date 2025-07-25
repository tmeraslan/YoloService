# tests/utils.py
import base64

def get_auth_headers(username="testuser", password="testpass"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

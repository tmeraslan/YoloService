import pytest

@pytest.fixture(autouse=True)
def mock_verify_user(monkeypatch):
    def fake_verify_user(username: str, password: str):
       
        return username == "testuser" and password == "testpass"

    monkeypatch.setattr("auth_middleware.verify_user", fake_verify_user)


# tests/conftest.py
import os
import sys
import types
import pytest
import numpy as np
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path

# --- Fake ultralytics BEFORE importing the app/controllers ---
@pytest.fixture(scope="session", autouse=True)
def fake_ultralytics_module():
    class _BoxVec:
        def __init__(self, val):
            self._val = val
        def item(self):
            return self._val
    class _XYXY:
        def __init__(self, arr):
            self._arr = arr
        def tolist(self):
            return list(self._arr)

    class FakeBox:
        def __init__(self):
            self.cls = [_BoxVec(0)]
            self.conf = [0.99]
            self.xyxy = [_XYXY([1, 2, 3, 4])]

    class FakeResult:
        def __init__(self):
            self.boxes = [FakeBox()]
        def plot(self):
            # מחזיר "תמונה" פשוטה (10x10) – PIL.fromarray תדע לשמור אותה
            return (np.ones((10, 10, 3), dtype="uint8") * 255)

    class FakeYOLO:
        def __init__(self, *args, **kwargs):
            self.names = {0: "person"}
        def __call__(self, path, device="cpu"):
            return [FakeResult()]

    mod = types.ModuleType("ultralytics")
    mod.YOLO = FakeYOLO
    sys.modules["ultralytics"] = mod
    yield


@pytest.fixture(scope="session")
def app_instance():
    # עכשיו בטוח לייבא את האפליקציה
    import app as app_module
    return app_module.app


@pytest.fixture
def tmp_upload_dirs(monkeypatch, tmp_path):
    # מגדיר תיקיות לוקאליות ל־uploads בסביבת טסט
    orig = tmp_path / "uploads" / "original"
    pred = tmp_path / "uploads" / "predicted"
    orig.mkdir(parents=True, exist_ok=True)
    pred.mkdir(parents=True, exist_ok=True)

    import controllers
    monkeypatch.setattr(controllers, "UPLOAD_DIR", str(orig))
    monkeypatch.setattr(controllers, "PREDICTED_DIR", str(pred))
    return orig, pred


@pytest.fixture(autouse=True)
def stub_queries_writes(monkeypatch):
    # מנטרל פעולות כתיבה ל־DB בזמן טסטים של /predict
    import queries
    monkeypatch.setattr(queries, "query_save_prediction_session", lambda *a, **k: None)
    monkeypatch.setattr(queries, "query_save_detection_object", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def mock_verify_user(monkeypatch):
    # עוקף אימות בסיסי
    def fake_verify_user(username: str, password: str):
        return username == "testuser" and password == "testpass"
    monkeypatch.setattr("auth_middleware.verify_user", fake_verify_user)


@pytest.fixture
def client(app_instance, monkeypatch, tmp_upload_dirs):
    # עוקף get_db
    from db import get_db
    def override_get_db():
        # מחזיר אובייקט דמה במקום Session אמיתי
        db = Mock()
        yield db
    app_instance.dependency_overrides[get_db] = override_get_db

    # מוקים לפונקציות S3 בתוך controllers (כי יובאו ב־from s3_utils import ...)
    import controllers
    created_keys = []

    def fake_download_to_path(key, dest_path):
        # יוצר "קובץ" מקור כדי שהעלאה ל־S3 לא תיכשל על os.path.isfile
        Path(dest_path).write_bytes(b"\xFF\xD8\xFF\xD9")  # חתימה מינימלית של JPEG
        return True

    def fake_upload_file(local_path, key, extra_args=None):
        # סימון שהועלה (אפשר לרשום לרשימה אם תרצה לבדיקות)
        if not Path(local_path).is_file():
            return False
        created_keys.append(key)
        return True

    def fake_delete_object(key):
        created_keys.append(("deleted", key))
        return True

    def fake_download_to_temp(key, suffix=None):
        suffix = suffix or ".jpg"
        from tempfile import mkstemp
        fd, tmp = mkstemp(suffix=suffix)
        os.close(fd)
        Path(tmp).write_bytes(b"\xFF\xD8\xFF\xD9")
        return tmp

    def fake_presign_get_url(key, expires_in=3600):
        return f"https://signed.example/{key}?exp={expires_in}"

    monkeypatch.setattr(controllers, "s3_download_to_path", fake_download_to_path, raising=True)
    monkeypatch.setattr(controllers, "s3_upload_file", fake_upload_file, raising=True)
    monkeypatch.setattr(controllers, "s3_delete_object", fake_delete_object, raising=True)
    monkeypatch.setattr(controllers, "s3_download_to_temp", fake_download_to_temp, raising=True)
    monkeypatch.setattr(controllers, "s3_presign_get_url", fake_presign_get_url, raising=True)

    from fastapi.testclient import TestClient
    return TestClient(app_instance)


@pytest.fixture
def VALID_AUTH_HEADER():
    # "testuser:testpass" בבסיס64
    return {"Authorization": "Basic dGVzdHVzZXI6dGVzdHBhc3M="}


@pytest.fixture
def WRONG_AUTH_HEADER():
    return {"Authorization": "Basic d3Jvbmc6dXNlcg=="}  # "wrong:user"



# import pytest

# @pytest.fixture(autouse=True)
# def mock_verify_user(monkeypatch):
#     def fake_verify_user(username: str, password: str):
       
#         return username == "testuser" and password == "testpass"

#     monkeypatch.setattr("auth_middleware.verify_user", fake_verify_user)

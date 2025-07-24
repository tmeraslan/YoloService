# tests/test_auth.py
import io
import unittest
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
from PIL import Image
from tests.seed_user import seed_test_user

# דואגים שהמשתמש לבדיקה קיים
seed_test_user()

client = TestClient(app)

def create_dummy_image():
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf

class TestAuth(unittest.TestCase):

    def test_health_no_auth(self):
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("status", resp.json())

    def test_predict_no_auth(self):
        img_bytes = create_dummy_image()
        files = {"file": ("dummy.jpg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("prediction_uid", resp.json())

    def test_count_no_auth(self):
        resp = client.get("/predictions/count")
        self.assertEqual(resp.status_code, 401)

    def test_count_with_auth(self):
        headers = get_auth_headers("testuser", "testpass")
        resp = client.get("/predictions/count", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("count", resp.json())

    def test_count_with_wrong_auth(self):
        headers = get_auth_headers("wronguser", "wrongpass")
        resp = client.get("/predictions/count", headers=headers)
        self.assertEqual(resp.status_code, 401)

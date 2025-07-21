import io
import unittest
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
from PIL import Image

client = TestClient(app)

def create_dummy_image():
    # יצירת תמונת JPEG פשוטה בזיכרון
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf

class TestAuth(unittest.TestCase):

    def test_health_no_auth(self):
        # /health פתוח לכולם
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("status", resp.json())

    def test_predict_no_auth(self):
        # יצירת תמונה תקינה
        img_bytes = create_dummy_image()
        files = {"file": ("dummy.jpg", img_bytes, "image/jpeg")}
        # /predict אמור לעבוד גם בלי אימות
        resp = client.post("/predict", files=files)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("prediction_uid", resp.json())

    def test_count_no_auth(self):
        # /predictions/count דורש אימות
        resp = client.get("/predictions/count")
        self.assertEqual(resp.status_code, 401)

    def test_count_with_auth(self):
        # אימות נכון
        headers = get_auth_headers("testuser", "testpass")
        resp = client.get("/predictions/count", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("count", resp.json())

    def test_count_with_wrong_auth(self):
        # אימות שגוי
        headers = get_auth_headers("wronguser", "wrongpass")
        resp = client.get("/predictions/count", headers=headers)
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()

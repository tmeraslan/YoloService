import unittest
import io
import os
from fastapi.testclient import TestClient
from PIL import Image
from app import app

client = TestClient(app)

def create_image_bytes():
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf

class TestPredictEndpoint(unittest.TestCase):
    def test_predict_endpoint(self):
        img_bytes = create_image_bytes()
        files = {"file": ("dummy.jpg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prediction_uid", data)
        self.assertIn("labels", data)
        self.assertIn("detection_count", data)
        # לוודא שנשמר קובץ
        predicted_path = os.path.join("uploads/predicted", f"{data['prediction_uid']}.jpg")
        self.assertTrue(os.path.exists(predicted_path))

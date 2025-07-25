import unittest
import io
import os
import base64
from fastapi.testclient import TestClient
from PIL import Image
from app import app
from db import SessionLocal
from models import PredictionSession

client = TestClient(app)


def get_auth_headers():
    creds = "testuser:testpass"
    encoded = base64.b64encode(creds.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}

def create_image_bytes():
    img = Image.new("RGB", (20, 20), color=(0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


class TestPredictEndpoint(unittest.TestCase):
    def test_predict_endpoint(self):
        img_bytes = create_image_bytes()
        files = {"file": ("dummy.jpg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prediction_uid", data)
        self.assertIn("labels", data)
        self.assertIn("detection_count", data)
        # Make sure the file is saved.
        predicted_path = os.path.join("uploads/predicted", f"{data['prediction_uid']}.jpg")
        self.assertTrue(os.path.exists(predicted_path))

    def test_predict_with_auth_and_verify_db_insert(self):
        img_bytes = create_image_bytes()
        files = {"file": ("dummy2.jpg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prediction_uid", data)

 
        db = SessionLocal()
        try:
            row = db.query(PredictionSession).filter_by(uid=data["prediction_uid"]).first()
            self.assertIsNotNone(row)
        finally:
            db.close()

    def test_predict_runs_yolo_and_saves_image(self):
        img_bytes = create_image_bytes()
        files = {"file": ("cover.jpg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        uid = data["prediction_uid"]
        predicted_path = os.path.join("uploads/predicted", f"{uid}.jpg")
        # Verify that an output image file has been created.
        self.assertTrue(os.path.exists(predicted_path))

    def test_predict_with_detected_object(self):
        # make sure beatles.jpeg exists in your test directory
        with open("beatles.jpeg", "rb") as f:
            files = {"file": ("beatles.jpeg", f, "image/jpeg")}
            resp = client.post("/predict", files=files, headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Verify labels are found
        self.assertGreater(data["detection_count"], 0)
        self.assertTrue(len(data["labels"]) > 0)
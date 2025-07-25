
import unittest
import os
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers

from db import SessionLocal
from models import PredictionSession

client = TestClient(app)

class TestGetPredictionImage(unittest.TestCase):
    def setUp(self):
        self.uid = "test-getimg-uid"
        self.predicted_path = f"uploads/predicted/{self.uid}.jpg"

        self.clean()

        os.makedirs("uploads/predicted", exist_ok=True)
        with open(self.predicted_path, "w") as f:
            f.write("dummy")

        db = SessionLocal()
        try:
            row = PredictionSession(
                uid=self.uid,
                timestamp=datetime.utcnow(),
                original_image="uploads/original/x.jpg",
                predicted_image=self.predicted_path
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.clean()
        if os.path.exists(self.predicted_path):
            os.remove(self.predicted_path)

    def clean(self):
        db = SessionLocal()
        try:
            db.query(PredictionSession).filter(PredictionSession.uid == self.uid).delete()
            db.commit()
        finally:
            db.close()

    # --- Existing tests ---
    def test_get_prediction_image_png(self):
        resp = client.get(
            f"/prediction/{self.uid}/image",
            headers={**get_auth_headers(), "accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_prediction_image_jpeg(self):
        resp = client.get(
            f"/prediction/{self.uid}/image",
            headers={**get_auth_headers(), "accept": "image/jpeg"}
        )
        self.assertEqual(resp.status_code, 200)

    def test_get_prediction_image_not_acceptable(self):
        resp = client.get(
            f"/prediction/{self.uid}/image",
            headers={**get_auth_headers(), "accept": "application/json"}
        )
        self.assertEqual(resp.status_code, 406)

    # --- New tests for edge cases ---
    def test_get_prediction_image_uid_not_found(self):
        resp = client.get(
            "/prediction/nonexistent-uid/image",
            headers={**get_auth_headers(), "accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_prediction_image_file_missing(self):
      
        fake_uid = "fake-uid"

        db = SessionLocal()
        try:
            
            db.query(PredictionSession).filter(PredictionSession.uid == fake_uid).delete()
            db.commit()
          
            row = PredictionSession(
                uid=fake_uid,
                timestamp=datetime.utcnow(),
                original_image="uploads/original/y.jpg",
                predicted_image="uploads/predicted/missing.jpg"
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        resp = client.get(
            f"/prediction/{fake_uid}/image",
            headers={**get_auth_headers(), "accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_prediction_by_uid_not_found(self):
        resp = client.get(
            "/prediction/nonexistent-uid",
            headers=get_auth_headers()
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_predictions_by_label_empty(self):
        resp = client.get(
            "/predictions/label/nonexistent-label",
            headers=get_auth_headers()
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_delete_prediction_not_found(self):
        resp = client.delete(
            "/prediction/nonexistent-uid",
            headers=get_auth_headers()
        )
        self.assertEqual(resp.status_code, 404)
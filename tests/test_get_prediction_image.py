import unittest
import os
import sqlite3
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers

client = TestClient(app)

class TestGetPredictionImage(unittest.TestCase):
    def setUp(self):
        self.uid = "test-getimg-uid"
        self.clean()
        self.predicted_path = f"uploads/predicted/{self.uid}.jpg"
        os.makedirs("uploads/predicted", exist_ok=True)
        with open(self.predicted_path, "w") as f:
            f.write("dummy")
        now = datetime.now().isoformat()
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image)
                VALUES (?, ?, ?, ?)
            """, (self.uid, now, "uploads/original/x.jpg", self.predicted_path))

    def tearDown(self):
        self.clean()
        if os.path.exists(self.predicted_path):
            os.remove(self.predicted_path)

    def clean(self):
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (self.uid,))

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

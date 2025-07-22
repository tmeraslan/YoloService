import unittest
import os
import sqlite3
from datetime import datetime
from fastapi.testclient import TestClient
from app import app, DB_PATH
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
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image)
                VALUES (?, ?, ?, ?)
            """, (self.uid, now, "uploads/original/x.jpg", self.predicted_path))

    def tearDown(self):
        self.clean()
        if os.path.exists(self.predicted_path):
            os.remove(self.predicted_path)

    def clean(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (self.uid,))

    # --- Existing tests---
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

    # --- New tests for edge cases---
    def test_get_prediction_image_uid_not_found(self):
        resp = client.get(
            "/prediction/nonexistent-uid/image",
            headers={**get_auth_headers(), "accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 404)

    def test_get_prediction_image_file_missing(self):
        # Inserting a record with a non-existent file
        fake_uid = "fake-uid"
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (fake_uid,))
            conn.execute(
                "INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image) VALUES (?, ?, ?, ?)",
                (fake_uid, datetime.now().isoformat(), "uploads/original/y.jpg", "uploads/predicted/missing.jpg")
            )

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

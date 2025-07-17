import unittest
from fastapi.testclient import TestClient
from app import app
import sqlite3
from datetime import datetime
from tests.utils import get_auth_headers

class TestLabelsEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.test_uid = "test-label-uid"
        self.clean()

        now = datetime.now().isoformat()
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image)
                VALUES (?, ?, ?, ?)
            """, (self.test_uid, now, "path/to/original.jpg", "path/to/predicted.jpg"))
            conn.execute("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, (self.test_uid, "cat", 0.9, "[0,0,50,50]"))
            conn.execute("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, (self.test_uid, "cat", 0.8, "[0,0,50,50]"))
            conn.execute("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, (self.test_uid, "dog", 0.88, "[10,10,60,60]"))

    def tearDown(self):
        self.clean()

    def clean(self):
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM detection_objects WHERE prediction_uid = ?", (self.test_uid,))
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (self.test_uid,))

    def test_labels_endpoint(self):
        response = self.client.get("/labels", headers=get_auth_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("labels", data)
        self.assertIn("cat", data["labels"])
        self.assertIn("dog", data["labels"])

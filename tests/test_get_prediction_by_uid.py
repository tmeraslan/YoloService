import unittest
import sqlite3
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
client = TestClient(app)

class TestGetPredictionByUID(unittest.TestCase):
    def setUp(self):
        self.uid = "test-uid-get"
        self.clean()
        now = datetime.now().isoformat()
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image)
                VALUES (?, ?, ?, ?)
            """, (self.uid, now, "uploads/original/test.jpg", "uploads/predicted/test.jpg"))
            conn.execute("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, (self.uid, "dog", 0.95, "[0,0,10,10]"))

    def tearDown(self):
        self.clean()

    def clean(self):
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM detection_objects WHERE prediction_uid = ?", (self.uid,))
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (self.uid,))

    def test_get_prediction_by_uid(self):
        resp = client.get(f"/prediction/{self.uid}",headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["uid"], self.uid)
        self.assertIn("detection_objects", data)
        self.assertGreaterEqual(len(data["detection_objects"]), 1)

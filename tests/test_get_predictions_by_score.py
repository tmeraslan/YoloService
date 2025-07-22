import unittest
import sqlite3
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
client = TestClient(app)

class TestGetPredictionsByScore(unittest.TestCase):
    def setUp(self):
        self.uid = "test-score-uid"
        self.clean()
        now = datetime.now().isoformat()
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image)
                VALUES (?, ?, ?, ?)
            """, (self.uid, now, "uploads/original/y.jpg", "uploads/predicted/y.jpg"))
            conn.execute("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, (self.uid, "cat", 0.91, "[0,0,10,10]"))

    def tearDown(self):
        self.clean()

    def clean(self):
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM detection_objects WHERE prediction_uid = ?", (self.uid,))
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (self.uid,))

    def test_get_predictions_by_score(self):
        resp = client.get("/predictions/score/0.5",headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        uids = [row["uid"] for row in data]
        self.assertIn(self.uid, uids)

    def test_get_predictions_by_score_no_results(self):
        # Too high a score that should not return anything
        resp = client.get("/predictions/score/0.99", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

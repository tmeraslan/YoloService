import unittest
from fastapi.testclient import TestClient
from app import app
import sqlite3
from datetime import datetime

class TestStatsEndpoint(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        self.uid = "test-stats-uid"
        now = datetime.now().isoformat()

        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM detection_objects")
            conn.execute("DELETE FROM prediction_sessions")

            conn.execute("""
                INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image)
                VALUES (?, ?, ?, ?)
            """, (self.uid, now, "original.jpg", "predicted.jpg"))

            conn.executemany("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, [
                (self.uid, "cat", 0.9, "[0,0,10,10]"),
                (self.uid, "cat", 0.85, "[0,0,20,20]"),
                (self.uid, "dog", 0.95, "[5,5,15,15]")
            ])

    def tearDown(self):
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM detection_objects WHERE prediction_uid = ?", (self.uid,))
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (self.uid,))

    def test_stats_endpoint(self):
        response = self.client.get("/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("total_predictions", data)
        self.assertIn("average_confidence_score", data)
        self.assertIn("most_common_labels", data)

        self.assertEqual(data["total_predictions"], 1)
        self.assertGreaterEqual(data["average_confidence_score"], 0.0)
        self.assertEqual(data["most_common_labels"].get("cat"), 2)
        self.assertEqual(data["most_common_labels"].get("dog"), 1)

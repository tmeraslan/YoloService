import unittest
from fastapi.testclient import TestClient
from app import app
from datetime import datetime, timedelta
import sqlite3
from tests.utils import get_auth_headers

class TestPredictionCount(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        # הוספת נתוני דמה במסד
        self.cleanup()
        now = datetime.now()
        past = now - timedelta(days=3)
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image)
                VALUES (?, ?, ?, ?)""",
                ("test-uid", past.isoformat(), "uploads/original/test.jpg", "uploads/predicted/test.jpg"))

    def cleanup(self):
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM prediction_sessions WHERE uid = 'test-uid'")

    def tearDown(self):
        self.cleanup()

    def test_prediction_count_endpoint(self):
        response = self.client.get("/predictions/count", headers=get_auth_headers())
        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.json())
        self.assertGreaterEqual(response.json()["count"], 1)

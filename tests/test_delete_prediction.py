import unittest
from fastapi.testclient import TestClient
from app import app
import sqlite3
import os

class TestDeletePrediction(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.uid = "test-delete-uid"
        self.original_image = f"uploads/original/{self.uid}.jpg"
        self.predicted_image = f"uploads/predicted/{self.uid}.jpg"


        # יצירת תמונות דמה
        os.makedirs("uploads/original", exist_ok=True)
        os.makedirs("uploads/predicted", exist_ok=True)
        with open(self.original_image, "w") as f:
            f.write("original")
        with open(self.predicted_image, "w") as f:
            f.write("predicted")

        # הכנסת רשומות למסד
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, original_image, predicted_image)
                VALUES (?, ?, ?)
            """, (self.uid, self.original_image, self.predicted_image))
            conn.execute("""
                INSERT INTO detection_objects (prediction_uid, label, score, box)
                VALUES (?, ?, ?, ?)
            """, (self.uid, "test", 0.9, "[0,0,10,10]"))

    def tearDown(self):
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM detection_objects WHERE prediction_uid = ?", (self.uid,))
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (self.uid,))
        for path in [self.original_image, self.predicted_image]:
            if os.path.exists(path):
                os.remove(path)

    def test_delete_prediction_success(self):
        response = self.client.delete(f"/prediction/{self.uid}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted successfully", response.json()["detail"])

        # בדיקה שהקבצים נמחקו
        self.assertFalse(os.path.exists(self.original_image))
        self.assertFalse(os.path.exists(self.predicted_image))

        # בדיקה שהרשומות נמחקו מהמסד
        with sqlite3.connect("predictions.db") as conn:
            session = conn.execute("SELECT * FROM prediction_sessions WHERE uid = ?", (self.uid,)).fetchone()
            self.assertIsNone(session)

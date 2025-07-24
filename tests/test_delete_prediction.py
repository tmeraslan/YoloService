# tests/test_delete_prediction.py
import unittest
from fastapi.testclient import TestClient
from app import app
import os
from tests.utils import get_auth_headers
from db import SessionLocal
from models import PredictionSession, DetectionObject

class TestDeletePrediction(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.uid = "test-delete-uid"
        self.original_image = f"uploads/original/{self.uid}.jpg"
        self.predicted_image = f"uploads/predicted/{self.uid}.jpg"

        # יצירת קבצי תמונה דמיוניים
        os.makedirs("uploads/original", exist_ok=True)
        os.makedirs("uploads/predicted", exist_ok=True)
        with open(self.original_image, "w") as f:
            f.write("original")
        with open(self.predicted_image, "w") as f:
            f.write("predicted")

        # הכנסת רשומות ל‑DB באמצעות SQLAlchemy
        db = SessionLocal()
        try:
            session = PredictionSession(
                uid=self.uid,
                original_image=self.original_image,
                predicted_image=self.predicted_image
            )
            db.add(session)
            db.commit()

            obj = DetectionObject(
                prediction_uid=self.uid,
                label="test",
                score=0.9,
                box="[0,0,10,10]"
            )
            db.add(obj)
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        # מחיקת הרשומות דרך SQLAlchemy
        db = SessionLocal()
        try:
            db.query(DetectionObject).filter(DetectionObject.prediction_uid == self.uid).delete()
            db.query(PredictionSession).filter(PredictionSession.uid == self.uid).delete()
            db.commit()
        finally:
            db.close()

        # מחיקת הקבצים
        for path in [self.original_image, self.predicted_image]:
            if os.path.exists(path):
                os.remove(path)

    def test_delete_prediction_success(self):
        # קריאת ה‑endpoint עם כותרות אימות
        response = self.client.delete(f"/prediction/{self.uid}", headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted successfully", response.json()["detail"])

        # וידוא שהקבצים נמחקו
        self.assertFalse(os.path.exists(self.original_image))
        self.assertFalse(os.path.exists(self.predicted_image))

        # וידוא שהרשומות נמחקו מה‑DB
        db = SessionLocal()
        try:
            session = db.query(PredictionSession).filter_by(uid=self.uid).first()
            self.assertIsNone(session)
        finally:
            db.close()

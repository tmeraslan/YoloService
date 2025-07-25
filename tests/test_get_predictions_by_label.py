# test_get_predictions_by_label.py
import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
from db import SessionLocal
from models import PredictionSession, DetectionObject

client = TestClient(app)

class TestGetPredictionsByLabel(unittest.TestCase):
    def setUp(self):
        self.uid = "test-label-uid"
        self.clean()
        db = SessionLocal()
        try:
            session_row = PredictionSession(
                uid=self.uid,
                timestamp=datetime.utcnow(),
                original_image="uploads/original/x.jpg",
                predicted_image="uploads/predicted/x.jpg"
            )
            db.add(session_row)
            db.commit()

            detection_row = DetectionObject(
                prediction_uid=self.uid,
                label="car",
                score=0.88,
                box="[1,1,10,10]"
            )
            db.add(detection_row)
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.clean()

    def clean(self):
        db = SessionLocal()
        try:
            db.query(DetectionObject).filter(DetectionObject.prediction_uid == self.uid).delete()
            db.query(PredictionSession).filter(PredictionSession.uid == self.uid).delete()
            db.commit()
        finally:
            db.close()

    def test_get_predictions_by_label(self):
        resp = client.get("/predictions/label/car", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        uids = [row["uid"] for row in data]
        self.assertIn(self.uid, uids)
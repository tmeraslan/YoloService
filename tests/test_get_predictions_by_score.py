import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers

# ✨ ייבוא SQLAlchemy
from db import SessionLocal
from models import PredictionSession, DetectionObject

client = TestClient(app)

class TestGetPredictionsByScore(unittest.TestCase):
    def setUp(self):
        self.uid = "test-score-uid"
        self.clean()

        # הוספת רשומות דרך SQLAlchemy
        db = SessionLocal()
        try:
            session_row = PredictionSession(
                uid=self.uid,
                timestamp=datetime.utcnow(),
                original_image="uploads/original/y.jpg",
                predicted_image="uploads/predicted/y.jpg"
            )
            db.add(session_row)
            db.commit()

            detection_row = DetectionObject(
                prediction_uid=self.uid,
                label="cat",
                score=0.91,
                box="[0,0,10,10]"
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

    def test_get_predictions_by_score(self):
        resp = client.get("/predictions/score/0.5", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        uids = [row["uid"] for row in data]
        self.assertIn(self.uid, uids)

    def test_get_predictions_by_score_no_results(self):
        # ציון גבוה מאוד שלא יחזיר תוצאות
        resp = client.get("/predictions/score/0.99", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

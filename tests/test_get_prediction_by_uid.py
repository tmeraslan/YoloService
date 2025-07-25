# tests/test_get_prediction_by_uid.py
import unittest
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
from db import SessionLocal
from models import PredictionSession, DetectionObject

client = TestClient(app)

class TestGetPredictionByUID(unittest.TestCase):
    def setUp(self):
        self.uid = "test-uid-get"
        self.clean()

        db = SessionLocal()
        try:
            session_row = PredictionSession(
                uid=self.uid,
                timestamp=datetime.utcnow(),
                original_image="uploads/original/test.jpg",
                predicted_image="uploads/predicted/test.jpg"
            )
            db.add(session_row)
            db.commit()

            obj_row = DetectionObject(
                prediction_uid=self.uid,
                label="dog",
                score=0.95,
                box="[0,0,10,10]"
            )
            db.add(obj_row)
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

    def test_get_prediction_by_uid(self):
        resp = client.get(f"/prediction/{self.uid}", headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["uid"], self.uid)
        self.assertIn("detection_objects", data)
        self.assertGreaterEqual(len(data["detection_objects"]), 1)
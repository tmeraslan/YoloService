import unittest
from fastapi.testclient import TestClient
from app import app
from datetime import datetime
from tests.utils import get_auth_headers


from db import SessionLocal
from models import PredictionSession, DetectionObject

class TestLabelsEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.test_uid = "test-label-uid"
        self.clean()

       
        db = SessionLocal()
        try:
            session_row = PredictionSession(
                uid=self.test_uid,
                timestamp=datetime.utcnow(),
                original_image="path/to/original.jpg",
                predicted_image="path/to/predicted.jpg"
            )
            db.add(session_row)
            db.commit()

         
            detections = [
                DetectionObject(prediction_uid=self.test_uid, label="cat", score=0.9, box="[0,0,50,50]"),
                DetectionObject(prediction_uid=self.test_uid, label="cat", score=0.8, box="[0,0,50,50]"),
                DetectionObject(prediction_uid=self.test_uid, label="dog", score=0.88, box="[10,10,60,60]"),
            ]
            db.add_all(detections)
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.clean()

    def clean(self):
        db = SessionLocal()
        try:
            db.query(DetectionObject).filter(DetectionObject.prediction_uid == self.test_uid).delete()
            db.query(PredictionSession).filter(PredictionSession.uid == self.test_uid).delete()
            db.commit()
        finally:
            db.close()

    def test_labels_endpoint(self):
        response = self.client.get("/labels", headers=get_auth_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("labels", data)
        self.assertIn("cat", data["labels"])
        self.assertIn("dog", data["labels"])
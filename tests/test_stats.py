import unittest
from fastapi.testclient import TestClient
from app import app
from datetime import datetime
from tests.utils import get_auth_headers
from db import SessionLocal
from models import PredictionSession, DetectionObject

class TestStatsEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.uid = "test-stats-uid"

        self.cleanup_all()

        # Add dummy data
        db = SessionLocal()
        try:
            session = PredictionSession(
                uid=self.uid,
                timestamp=datetime.now(),
                original_image="original.jpg",
                predicted_image="predicted.jpg"
            )
            db.add(session)
            db.commit()

            detections = [
                DetectionObject(prediction_uid=self.uid, label="cat", score=0.9, box="[0,0,10,10]"),
                DetectionObject(prediction_uid=self.uid, label="cat", score=0.85, box="[0,0,20,20]"),
                DetectionObject(prediction_uid=self.uid, label="dog", score=0.95, box="[5,5,15,15]")
            ]
            db.add_all(detections)
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.cleanup_all()

    def cleanup_all(self):
        db = SessionLocal()
        try:
            db.query(DetectionObject).delete()
            db.query(PredictionSession).delete()
            db.commit()
        finally:
            db.close()

    def test_stats_endpoint(self):
        response = self.client.get("/stats", headers=get_auth_headers())
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("total_predictions", data)
        self.assertIn("average_confidence_score", data)
        self.assertIn("most_common_labels", data)

        self.assertEqual(data["total_predictions"], 1)
        self.assertGreaterEqual(data["average_confidence_score"], 0.0)
        self.assertEqual(data["most_common_labels"].get("cat"), 2)
        self.assertEqual(data["most_common_labels"].get("dog"), 1)
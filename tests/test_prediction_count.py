
import unittest
from fastapi.testclient import TestClient
from app import app
from datetime import datetime, timedelta
from tests.utils import get_auth_headers
from db import SessionLocal
from models import PredictionSession

class TestPredictionCount(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.uid = "test-uid"
        self.cleanup()

        db = SessionLocal()
        try:
            past = datetime.now() - timedelta(days=3)
            row = PredictionSession(
                uid=self.uid,
                timestamp=past,
                original_image="uploads/original/test.jpg",
                predicted_image="uploads/predicted/test.jpg"
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    def cleanup(self):
       
        db = SessionLocal()
        try:
            db.query(PredictionSession).filter_by(uid=self.uid).delete()
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.cleanup()

    def test_prediction_count_endpoint(self):
        response = self.client.get("/predictions/count", headers=get_auth_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("count", data)
        self.assertGreaterEqual(data["count"], 1)
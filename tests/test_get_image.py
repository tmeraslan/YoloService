# tests/test_get_image.py
import unittest
import os
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
import uuid

# ✨ שימוש ב-SQLAlchemy
from db import SessionLocal
from models import PredictionSession

client = TestClient(app)

class TestGetImage(unittest.TestCase):
    def setUp(self):
        self.uid = "test-img-uid"
        self.clean()

        # יצירת קבצי דמה
        self.original_path = f"uploads/original/{self.uid}.jpg"
        self.predicted_path = f"uploads/predicted/{self.uid}.jpg"
        os.makedirs("uploads/original", exist_ok=True)
        os.makedirs("uploads/predicted", exist_ok=True)
        with open(self.original_path, "w") as f:
            f.write("dummy")
        with open(self.predicted_path, "w") as f:
            f.write("dummy")

        # ✨ הכנסת הרשומה ל-DB דרך SQLAlchemy
        db = SessionLocal()
        try:
            row = PredictionSession(
                uid=self.uid,
                timestamp=datetime.utcnow(),
                original_image=self.original_path,
                predicted_image=self.predicted_path
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.clean()
        for path in [self.original_path, self.predicted_path]:
            if os.path.exists(path):
                os.remove(path)

    def clean(self):
        # ✨ מחיקת הרשומה מה-DB דרך SQLAlchemy
        db = SessionLocal()
        try:
            db.query(PredictionSession).filter(PredictionSession.uid == self.uid).delete()
            db.commit()
        finally:
            db.close()

    def test_get_original_image(self):
        filename = os.path.basename(self.original_path)
        resp = client.get(f"/image/original/{filename}", headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(resp.status_code, 200)

    def test_get_predicted_image(self):
        filename = os.path.basename(self.predicted_path)
        resp = client.get(f"/image/predicted/{filename}", headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(resp.status_code, 200)

    def test_get_image_invalid_type(self):
        response = client.get("/image/wrong/fake.jpg", headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(response.status_code, 400)

    def test_get_image_not_found(self):
        response = client.get("/image/original/non_existent.jpg", headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(response.status_code, 404)

    def test_get_prediction_image_not_acceptable(self):
        uid = self.uid
        response = client.get(
            f"/prediction/{uid}/image",
            headers={"accept": "application/json", **get_auth_headers("testuser", "testpass")}
        )
        self.assertEqual(response.status_code, 406)

    def test_get_prediction_image_not_found(self):
        uid = str(uuid.uuid4())
        # ✨ הכנסת רשומה עם predicted_path לא קיים
        db = SessionLocal()
        try:
            row = PredictionSession(
                uid=uid,
                timestamp=datetime.utcnow(),
                original_image="path1",
                predicted_image="uploads/predicted/somefile.jpg"
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        response = client.get(
            f"/prediction/{uid}/image",
            headers={"accept": "image/png", **get_auth_headers("testuser", "testpass")}
        )
        self.assertEqual(response.status_code, 404)

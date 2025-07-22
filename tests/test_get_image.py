import unittest
import os
import sqlite3
from datetime import datetime
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
import  uuid
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
        now = datetime.now().isoformat()
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("""
                INSERT INTO prediction_sessions (uid, timestamp, original_image, predicted_image)
                VALUES (?, ?, ?, ?)
            """, (self.uid, now, self.original_path, self.predicted_path))

    def tearDown(self):
        self.clean()
        for path in [self.original_path, self.predicted_path]:
            if os.path.exists(path):
                os.remove(path)

    def clean(self):
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (self.uid,))

    def test_get_original_image(self):
        filename = os.path.basename(self.original_path)
        resp = client.get(f"/image/original/{filename}", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)

    def test_get_predicted_image(self):
        filename = os.path.basename(self.predicted_path)
        resp = client.get(f"/image/predicted/{filename}",headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)

    def test_get_image_invalid_type(self):
        response = client.get("/image/wrong/fake.jpg", headers=get_auth_headers())
        self.assertEqual(response.status_code, 400)

    def test_get_image_not_found(self):
        response = client.get("/image/original/non_existent.jpg", headers=get_auth_headers())
        self.assertEqual(response.status_code, 404)

    def test_get_prediction_image_not_acceptable(self):
        uid = self.uid  # For example, using the UID defined in setUp
        response = client.get(f"/prediction/{uid}/image", headers={"accept": "application/json", **get_auth_headers()})
        self.assertEqual(response.status_code, 406)

    def test_get_prediction_image_not_found(self):
        uid = str(uuid.uuid4())
        with sqlite3.connect("predictions.db") as conn:
            conn.execute("INSERT INTO prediction_sessions (uid, original_image, predicted_image) VALUES (?, ?, ?)",
                        (uid, "path1", "uploads/predicted/somefile.jpg"))
        response = client.get(f"/prediction/{uid}/image", headers={"accept": "image/png", **get_auth_headers()})
        self.assertEqual(response.status_code, 404)
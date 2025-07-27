import unittest
import os
from datetime import datetime
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
import queries

class TestGetImage(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.uid = "test-img-uid"
        self.original_path = f"uploads/original/{self.uid}.jpg"
        self.predicted_path = f"uploads/predicted/{self.uid}.jpg"

        os.makedirs("uploads/original", exist_ok=True)
        os.makedirs("uploads/predicted", exist_ok=True)

        with open(self.original_path, "w") as f:
            f.write("dummy")
        with open(self.predicted_path, "w") as f:
            f.write("dummy")

    def tearDown(self):
        for path in [self.original_path, self.predicted_path]:
            if os.path.exists(path):
                os.remove(path)

    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_not_acceptable(self, mock_query):
        # Simulate an existing prediction
        mock_query.return_value = type("MockPrediction", (), {
            "original_image": self.original_path,
            "predicted_image": self.predicted_path
        })()

        response = self.client.get(
            f"/prediction/{self.uid}/image",
            headers={"accept": "application/json", **get_auth_headers("testuser", "testpass")}
        )

        self.assertEqual(response.status_code, 406)
        mock_query.assert_called_once()

    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_not_found(self, mock_query):
        # Simulate a prediction with a missing file
        mock_query.return_value = type("MockPrediction", (), {
            "original_image": "uploads/original/nonexistent.jpg",
            "predicted_image": "uploads/predicted/nonexistent.jpg"
        })()

        response = self.client.get(
            f"/prediction/{self.uid}/image",
            headers={"accept": "image/png", **get_auth_headers("testuser", "testpass")}
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Predicted image file not found"})
        mock_query.assert_called_once()

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
from datetime import datetime

client = TestClient(app)

class TestGetPredictionByUID(unittest.TestCase):
    def setUp(self):
        self.uid = "test-uid-get"

    @patch("queries.query_get_prediction_by_uid")
    @patch("queries.query_get_objects_by_uid")
    def test_get_prediction_by_uid_mocked(self, mock_get_objects, mock_get_prediction):
        mock_get_prediction.return_value = type("MockPrediction", (), {
            "uid": self.uid,
            "timestamp": datetime.fromisoformat("2025-07-25T12:00:00"),  # כאן!
            "original_image": "uploads/original/test.jpg",
            "predicted_image": "uploads/predicted/test.jpg"
        })()

        mock_get_objects.return_value = [
            type("MockDetectionObject", (), {
                "label": "dog",
                "score": 0.95,
                "box": "[0,0,10,10]"
            })()
        ]

        headers = get_auth_headers("testuser", "testpass")
        response = client.get(f"/prediction/{self.uid}", headers=headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["uid"], self.uid)
        self.assertIn("detection_objects", data)
        self.assertGreaterEqual(len(data["detection_objects"]), 1)
        self.assertEqual(data["detection_objects"][0]["label"], "dog")

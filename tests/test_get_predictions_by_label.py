import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers

client = TestClient(app)

class TestGetPredictionsByLabel(unittest.TestCase):

    @patch("app.queries.query_get_predictions_by_label")
    def test_get_predictions_by_label(self, mock_query):
        # Defining a simulated result that the function will return
        mock_query.return_value = [
            {"uid": "mock-uid-1", "timestamp": "2025-07-25T12:00:00"},
            {"uid": "mock-uid-2", "timestamp": "2025-07-25T13:00:00"}
        ]

        resp = client.get("/predictions/label/car", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["uid"], "mock-uid-1")
        self.assertEqual(data[1]["uid"], "mock-uid-2")

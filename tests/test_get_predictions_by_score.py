#test_get_predictions_by_score
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
import queries

client = TestClient(app)

class TestGetPredictionsByScore(unittest.TestCase):

    @patch("queries.query_get_predictions_by_score")
    def test_get_predictions_by_score(self, mock_query):
        # Returns a mock result list of UIDs with dates
        mock_query.return_value = [
            {"uid": "test-score-uid", "timestamp": "2025-07-25T12:00:00"},
            {"uid": "another-uid", "timestamp": "2025-07-24T09:30:00"},
        ]

        resp = client.get("/predictions/score/0.5", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertTrue(any(row["uid"] == "test-score-uid" for row in data))

    @patch("queries.query_get_predictions_by_score")
    def test_get_predictions_by_score_no_results(self, mock_query):
        
        mock_query.return_value = []

        resp = client.get("/predictions/score/0.99", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

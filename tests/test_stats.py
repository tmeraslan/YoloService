import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
import queries


class TestStatsEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("queries.query_get_prediction_stats")
    def test_stats_endpoint_mocked(self, mock_query_stats):
        
        mock_query_stats.return_value = {
            "total_predictions": 1,
            "average_confidence_score": 0.9,
            "most_common_labels": {"cat": 2, "dog": 1}
        }

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

        mock_query_stats.assert_called_once()
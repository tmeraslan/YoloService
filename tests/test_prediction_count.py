
#test_prediction
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers
import queries

class TestPredictionCount(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("queries.query_get_prediction_count_last_week")
    def test_prediction_count_endpoint_mocked(self, mock_query_count):
        # We will define that the query call will return a predefined value.
        mock_query_count.return_value = 5

        response = self.client.get("/predictions/count", headers=get_auth_headers())
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("count", data)
        self.assertEqual(data["count"], 5)  #Because mock returned 5

        mock_query_count.assert_called_once()

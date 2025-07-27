import unittest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
import queries   

class TestAuth(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        def override_get_db():
            return Mock()

        app.dependency_overrides[get_db] = override_get_db

    def tearDown(self):
        app.dependency_overrides = {}

    @patch("queries.query_get_prediction_count_last_week")
    def test_count_no_auth(self, mock_count):
        mock_count.return_value = 5
        response = self.client.get("/predictions/count")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Missing credentials"})

    @patch("queries.query_get_prediction_count_last_week")
    def test_count_with_auth(self, mock_count):
        mock_count.return_value = 7
        headers = {
            "Authorization": "Basic dGVzdHVzZXI6dGVzdHBhc3M="
        }
        response = self.client.get("/predictions/count", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 7})

    @patch("queries.query_get_prediction_count_last_week")
    def test_count_with_wrong_auth(self, mock_count):
        mock_count.return_value = 0
        headers = {
            "Authorization": "Basic d3Jvbmc6dXNlcg=="
        }
        response = self.client.get("/predictions/count", headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Invalid credentials"})

# tests/test_auth.py
import unittest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db


class TestAuth(unittest.TestCase):
    """
    Test suite for authentication behavior on /predictions/count.
    The database layer is fully mocked (no real DB is used).
    """

    def setUp(self):
        """
        Set up a test client and override the get_db dependency
        with a mock to avoid touching the real database.
        """
        self.client = TestClient(app)

        def override_get_db():
            return Mock()

        app.dependency_overrides[get_db] = override_get_db

    def tearDown(self):
        """
        Clean up after each test by clearing dependency overrides.
        """
        app.dependency_overrides = {}

    @patch("queries.query_get_prediction_count_last_week")
    def test_count_no_auth(self, mock_count):
        """
        Verify that calling /predictions/count without any Authorization header
        returns a 401 response.
        """
        mock_count.return_value = 5  # Doesn't matter, no auth should block access

        response = self.client.get("/predictions/count")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Missing credentials"})

    @patch("queries.query_get_prediction_count_last_week")
    def test_count_with_auth(self, mock_count):
        """
        Verify that calling /predictions/count with valid credentials
        returns a 200 response and the expected mocked count.
        """
        mock_count.return_value = 7

        # This is base64 for "testuser:testpass"
        headers = {
            "Authorization": "Basic dGVzdHVzZXI6dGVzdHBhc3M="
        }

        response = self.client.get("/predictions/count", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 7})

    @patch("queries.query_get_prediction_count_last_week")
    def test_count_with_wrong_auth(self, mock_count):
        """
        Verify that calling /predictions/count with incorrect credentials
        returns a 401 response.
        """
        mock_count.return_value = 0  # Doesn't matter, wrong auth should fail

        # This is base64 for "wrong:user"
        headers = {
            "Authorization": "Basic d3Jvbmc6dXNlcg=="
        }

        response = self.client.get("/predictions/count", headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Invalid credentials"})

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers

client = TestClient(app)

class TestLabelsEndpoint(unittest.TestCase):

    @patch("app.queries.query_get_labels_from_last_week")
    def test_labels_endpoint(self, mock_query):
        # Define dummy labels
        mock_query.return_value = ["cat", "dog", "bird"]

        response = client.get("/labels", headers=get_auth_headers())
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("labels", data)
        self.assertIn("cat", data["labels"])
        self.assertIn("dog", data["labels"])
        self.assertIn("bird", data["labels"])

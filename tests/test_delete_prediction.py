# tests/test_delete_prediction.py
import unittest
import os
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers
import queries

class TestDeletePrediction(unittest.TestCase):
    """
    Test suite for DELETE /prediction/{uid} endpoint.
    All database operations are mocked. No real database is used.
    """

    def setUp(self):
        """
        Prepare the test environment before each test:
        - Override the get_db dependency with a mock.
        - Create dummy image files to simulate stored prediction images.
        """
        self.client = TestClient(app)

        # Override get_db to avoid real DB usage
        def override_get_db():
            return Mock()
        app.dependency_overrides[get_db] = override_get_db

        self.uid = "test-delete-uid"
        self.original_image = f"uploads/original/{self.uid}.jpg"
        self.predicted_image = f"uploads/predicted/{self.uid}.jpg"

        # Ensure directories exist
        os.makedirs("uploads/original", exist_ok=True)
        os.makedirs("uploads/predicted", exist_ok=True)

        # Create fake files
        with open(self.original_image, "w") as f:
            f.write("original content")
        with open(self.predicted_image, "w") as f:
            f.write("predicted content")

    def tearDown(self):
        """
        Clean up after each test:
        - Remove any remaining image files.
        - Clear dependency overrides.
        """
        for path in [self.original_image, self.predicted_image]:
            if os.path.exists(path):
                os.remove(path)

        # Reset dependency overrides
        app.dependency_overrides = {}

    @patch("queries.query_delete_prediction")
    def test_delete_prediction_success(self, mock_delete):
        """
        Test that deleting an existing prediction works as expected:
        - The mocked DB delete function returns a mock object with file paths.
        - The endpoint should return 200 and remove files from disk.
        """
        # Simulate a prediction object with the same paths
        mock_delete.return_value = type("MockPrediction", (), {
            "original_image": self.original_image,
            "predicted_image": self.predicted_image
        })()

        response = self.client.delete(
            f"/prediction/{self.uid}",
            headers=get_auth_headers("testuser", "testpass")
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted successfully", response.json()["detail"])

        # Files should be removed
        self.assertFalse(os.path.exists(self.original_image))
        self.assertFalse(os.path.exists(self.predicted_image))

        # Verify the mock was called exactly once
        mock_delete.assert_called_once()

    @patch("queries.query_delete_prediction")
    def test_delete_prediction_not_found(self, mock_delete):
        """
        Test that deleting a non-existing prediction returns 404:
        - The mocked DB delete function returns None.
        """
        mock_delete.return_value = None

        response = self.client.delete(
            "/prediction/nonexistent-uid",
            headers=get_auth_headers("testuser", "testpass")
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Prediction not found")
        mock_delete.assert_called_once()

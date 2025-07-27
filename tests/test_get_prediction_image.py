#TEST
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from fastapi.testclient import TestClient
from app import app  
from tests.utils import get_auth_headers
import queries
import controllers
client = TestClient(app)

class TestGetPredictionImage(unittest.TestCase):
    def setUp(self):
        self.uid = "test-getimg-uid"
        self.predicted_path = f"uploads/predicted/{self.uid}.jpg"
    
    @patch("controllers.FileResponse")
    @patch("os.path.exists")
    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_png(self, mock_query, mock_exists, mock_fileresponse_class):
        mock_query.return_value = type("MockPrediction", (), {
            "uid": self.uid,
            "timestamp": datetime.utcnow(),
            "original_image": "uploads/original/mock.png",
            "predicted_image": self.predicted_path
        })()

        mock_exists.return_value = True

        mock_response_instance = MagicMock()
        mock_response_instance.background = None
        mock_fileresponse_class.return_value = mock_response_instance

        resp = client.get(
            f"/prediction/{self.uid}/image",
            headers={**get_auth_headers(), "accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 200)

    @patch("controllers.FileResponse")
    @patch("os.path.exists")
    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_jpeg(self, mock_query, mock_exists, mock_fileresponse_class):
        mock_query.return_value = type("MockPrediction", (), {
            "uid": self.uid,
            "timestamp": datetime.utcnow(),
            "original_image": "uploads/original/mock.jpg",
            "predicted_image": self.predicted_path
        })()

        mock_exists.return_value = True

        mock_response_instance = MagicMock()
        mock_response_instance.background = None
        mock_fileresponse_class.return_value = mock_response_instance

        resp = client.get(
            f"/prediction/{self.uid}/image",
            headers={**get_auth_headers(), "accept": "image/jpeg"}
        )
        self.assertEqual(resp.status_code, 200)

    @patch("os.path.exists")
    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_not_acceptable(self, mock_query, mock_exists):
        mock_query.return_value = type("MockPrediction", (), {
            "uid": "test-getimg-uid",
            "timestamp": datetime.utcnow(),
            "original_image": "uploads/original/mock.png",
            "predicted_image": f"uploads/predicted/test-getimg-uid.png"
        })()
        mock_exists.return_value = True  # חשוב

        resp = client.get(
            f"/prediction/test-getimg-uid/image",
            headers={**get_auth_headers(), "accept": "application/json"}
        )
        self.assertEqual(resp.status_code, 406)



    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_uid_not_found(self, mock_query):
        mock_query.return_value = None

        resp = client.get(
            "/prediction/nonexistent-uid/image",
            headers={**get_auth_headers(), "accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 404)

    @patch("os.path.exists")
    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_file_missing(self, mock_query, mock_exists):
        mock_query.return_value = type("MockPrediction", (), {
            "uid": "fake-uid",
            "timestamp": datetime.utcnow(),
            "original_image": "uploads/original/y.jpg",
            "predicted_image": "uploads/predicted/missing.jpg"
        })()
        mock_exists.return_value = False  # הקובץ חסר

        resp = client.get(
            "/prediction/fake-uid/image",
            headers={**get_auth_headers(), "accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 404)

    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_by_uid_not_found(self, mock_query):
        mock_query.return_value = None

        resp = client.get(
            "/prediction/nonexistent-uid",
            headers=get_auth_headers()
        )
        self.assertEqual(resp.status_code, 404)

    @patch("queries.query_get_predictions_by_label")
    def test_get_predictions_by_label_empty(self, mock_query_label):
        mock_query_label.return_value = []

        resp = client.get(
            "/predictions/label/nonexistent-label",
            headers=get_auth_headers()
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    @patch("queries.query_delete_prediction")
    def test_delete_prediction_not_found(self, mock_delete):
        mock_delete.return_value = None

        resp = client.delete(
            "/prediction/nonexistent-uid",
            headers=get_auth_headers()
        )
        self.assertEqual(resp.status_code, 404)

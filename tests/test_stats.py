
# tests/test_stats_endpoint.py
import unittest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers


class TestStatsEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        # לאמת testuser:testpass
        self.p_auth = patch(
            "auth_middleware.verify_user",
            lambda u, p: (u == "testuser" and p == "testpass"),
        )
        self.p_auth.start()

        # לעקוף get_db כדי לא להשתמש ב-DB אמיתי
        self.db = Mock()
        def override_get_db():
            yield self.db
        app.dependency_overrides[get_db] = override_get_db

    def tearDown(self):
        app.dependency_overrides = {}
        try:
            self.p_auth.stop()
        except Exception:
            pass

    @patch("queries.query_get_prediction_stats")
    def test_stats_endpoint_mocked(self, mock_query_stats):
        mock_query_stats.return_value = {
            "total_predictions": 1,
            "average_confidence_score": 0.9,
            "most_common_labels": {"cat": 2, "dog": 1},
        }

        resp = self.client.get("/stats", headers=get_auth_headers())
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        self.assertIn("total_predictions", data)
        self.assertIn("average_confidence_score", data)
        self.assertIn("most_common_labels", data)

        self.assertEqual(data["total_predictions"], 1)
        self.assertGreaterEqual(data["average_confidence_score"], 0.0)
        self.assertEqual(data["most_common_labels"].get("cat"), 2)
        self.assertEqual(data["most_common_labels"].get("dog"), 1)

        mock_query_stats.assert_called_once()

    @patch("queries.query_get_prediction_stats", return_value={"total_predictions": 0, "average_confidence_score": 0.0, "most_common_labels": {}})
    def test_stats_endpoint_unauthorized_missing(self, _mock_stats):
        # ללא Authorization → 401
        resp = self.client.get("/stats")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json(), {"detail": "Missing credentials"})


# import unittest
# from unittest.mock import patch
# from fastapi.testclient import TestClient
# from app import app
# from tests.utils import get_auth_headers
# import queries


# class TestStatsEndpoint(unittest.TestCase):
#     def setUp(self):
#         self.client = TestClient(app)

#     @patch("queries.query_get_prediction_stats")
#     def test_stats_endpoint_mocked(self, mock_query_stats):
        
#         mock_query_stats.return_value = {
#             "total_predictions": 1,
#             "average_confidence_score": 0.9,
#             "most_common_labels": {"cat": 2, "dog": 1}
#         }

#         response = self.client.get("/stats", headers=get_auth_headers())
#         self.assertEqual(response.status_code, 200)

#         data = response.json()
#         self.assertIn("total_predictions", data)
#         self.assertIn("average_confidence_score", data)
#         self.assertIn("most_common_labels", data)

#         self.assertEqual(data["total_predictions"], 1)
#         self.assertGreaterEqual(data["average_confidence_score"], 0.0)
#         self.assertEqual(data["most_common_labels"].get("cat"), 2)
#         self.assertEqual(data["most_common_labels"].get("dog"), 1)

#         mock_query_stats.assert_called_once()
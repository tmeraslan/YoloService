

# tests/test_get_predictions_by_score.py
import unittest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers


class TestGetPredictionsByScore(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        # אימות בסיסי לטסטים
        self.p_auth = patch("auth_middleware.verify_user",
                            lambda u, p: (u == "testuser" and p == "testpass"))
        self.p_auth.start()

        # לעקוף get_db כדי לא להשתמש ב־DB אמיתי
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

    @patch("queries.query_get_predictions_by_score")
    def test_get_predictions_by_score(self, mock_query):
        # תוצאה מדומה שהפונקציה תחזיר
        mock_query.return_value = [
            {"uid": "test-score-uid", "timestamp": "2025-07-25T12:00:00"},
            {"uid": "another-uid", "timestamp": "2025-07-24T09:30:00"},
        ]

        resp = self.client.get("/predictions/score/0.5",
                               headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # הממשק החדש מחזיר {"items": [...]}
        self.assertIsInstance(data, dict)
        self.assertIn("items", data)
        self.assertIsInstance(data["items"], list)
        self.assertTrue(any(row["uid"] == "test-score-uid" for row in data["items"]))

    @patch("queries.query_get_predictions_by_score", return_value=[])
    def test_get_predictions_by_score_no_results(self, _mock_query):
        resp = self.client.get("/predictions/score/0.99",
                               headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"items": []})



# #test_get_predictions_by_score
# import unittest
# from unittest.mock import patch
# from fastapi.testclient import TestClient
# from app import app
# from tests.utils import get_auth_headers
# import queries

# client = TestClient(app)

# class TestGetPredictionsByScore(unittest.TestCase):

#     @patch("queries.query_get_predictions_by_score")
#     def test_get_predictions_by_score(self, mock_query):
#         # Returns a mock result list of UIDs with dates
#         mock_query.return_value = [
#             {"uid": "test-score-uid", "timestamp": "2025-07-25T12:00:00"},
#             {"uid": "another-uid", "timestamp": "2025-07-24T09:30:00"},
#         ]

#         resp = client.get("/predictions/score/0.5", headers=get_auth_headers())
#         self.assertEqual(resp.status_code, 200)
#         data = resp.json()
#         self.assertIsInstance(data, list)
#         self.assertTrue(any(row["uid"] == "test-score-uid" for row in data))

#     @patch("queries.query_get_predictions_by_score")
#     def test_get_predictions_by_score_no_results(self, mock_query):
        
#         mock_query.return_value = []

#         resp = client.get("/predictions/score/0.99", headers=get_auth_headers())
#         self.assertEqual(resp.status_code, 200)
#         self.assertEqual(resp.json(), [])

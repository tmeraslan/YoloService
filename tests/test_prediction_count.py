

# tests/test_prediction_count.py
import unittest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers


class TestPredictionCount(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        # אימות בסיסי: נאפשר user=testuser / pass=testpass
        self.p_auth = patch(
            "auth_middleware.verify_user",
            lambda u, p: (u == "testuser" and p == "testpass"),
        )
        self.p_auth.start()

        # עקיפת get_db כדי לא להשתמש ב-DB אמיתי
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

    @patch("queries.query_get_prediction_count_last_week", return_value=5)
    def test_prediction_count_endpoint_mocked(self, mock_query_count):
        resp = self.client.get(
            "/predictions/count",
            headers=get_auth_headers("testuser", "testpass"),
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("count", data)
        self.assertEqual(data["count"], 5)  # כי המוק החזיר 5
        mock_query_count.assert_called_once()

    @patch("queries.query_get_prediction_count_last_week", return_value=3)
    def test_prediction_count_unauthorized_missing(self, _mock_query_count):
        # בלי Authorization header → 401
        resp = self.client.get("/predictions/count")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json(), {"detail": "Missing credentials"})

    @patch("queries.query_get_prediction_count_last_week", return_value=0)
    def test_prediction_count_wrong_auth(self, _mock_query_count):
        # Authorization שגוי → 401
        wrong_header = {"Authorization": "Basic d3Jvbmc6dXNlcg=="}  # "wrong:user"
        resp = self.client.get("/predictions/count", headers=wrong_header)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json(), {"detail": "Invalid credentials"})



# #test_prediction
# import unittest
# from unittest.mock import patch
# from fastapi.testclient import TestClient
# from app import app
# from tests.utils import get_auth_headers
# import queries

# class TestPredictionCount(unittest.TestCase):
#     def setUp(self):
#         self.client = TestClient(app)

#     @patch("queries.query_get_prediction_count_last_week")
#     def test_prediction_count_endpoint_mocked(self, mock_query_count):
#         # We will define that the query call will return a predefined value.
#         mock_query_count.return_value = 5

#         response = self.client.get("/predictions/count", headers=get_auth_headers())
#         self.assertEqual(response.status_code, 200)

#         data = response.json()
#         self.assertIn("count", data)
#         self.assertEqual(data["count"], 5)  #Because mock returned 5

#         mock_query_count.assert_called_once()

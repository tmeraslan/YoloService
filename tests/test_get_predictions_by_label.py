
# tests/test_get_predictions_by_label.py
import unittest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers


class TestGetPredictionsByLabel(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        # אימות בסיסי: נאפשר user:testuser / pass:testpass
        self.p_auth = patch("auth_middleware.verify_user",
                            lambda u, p: (u == "testuser" and p == "testpass"))
        self.p_auth.start()

        # override ל־get_db כדי לא להשתמש ב־DB אמיתי
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

    @patch("queries.query_get_predictions_by_label")
    def test_get_predictions_by_label(self, mock_query):
        # תוצאה מדומה שהפונקציה תחזיר
        mock_query.return_value = [
            {"uid": "mock-uid-1", "timestamp": "2025-07-25T12:00:00"},
            {"uid": "mock-uid-2", "timestamp": "2025-07-25T13:00:00"},
        ]

        resp = self.client.get("/predictions/label/car", headers=get_auth_headers("testuser", "testpass"))
        assert resp.status_code == 200
        data = resp.json()

        # מבנה חדש: {"items": [...]}
        assert isinstance(data, dict)
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 2
        assert data["items"][0]["uid"] == "mock-uid-1"
        assert data["items"][1]["uid"] == "mock-uid-2"

    @patch("queries.query_get_predictions_by_label", return_value=[])
    def test_get_predictions_by_label_empty(self, _mock_query):
        resp = self.client.get("/predictions/label/unknown", headers=get_auth_headers("testuser", "testpass"))
        assert resp.status_code == 200
        assert resp.json() == {"items": []}


# import unittest
# from unittest.mock import patch
# from fastapi.testclient import TestClient
# from app import app
# from tests.utils import get_auth_headers
# import queries
# client = TestClient(app)

# class TestGetPredictionsByLabel(unittest.TestCase):

#     @patch("queries.query_get_predictions_by_label")
#     def test_get_predictions_by_label(self, mock_query):
#         # Defining a simulated result that the function will return
#         mock_query.return_value = [
#             {"uid": "mock-uid-1", "timestamp": "2025-07-25T12:00:00"},
#             {"uid": "mock-uid-2", "timestamp": "2025-07-25T13:00:00"}
#         ]

#         resp = client.get("/predictions/label/car", headers=get_auth_headers())
#         self.assertEqual(resp.status_code, 200)
#         data = resp.json()
#         self.assertIsInstance(data, list)
#         self.assertEqual(len(data), 2)
#         self.assertEqual(data[0]["uid"], "mock-uid-1")
#         self.assertEqual(data[1]["uid"], "mock-uid-2")

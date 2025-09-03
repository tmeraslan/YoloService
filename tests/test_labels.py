

# tests/test_labels.py
import unittest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers


class TestLabelsEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        # אימות בסיסי: לאפשר testuser:testpass
        self.p_auth = patch("auth_middleware.verify_user",
                            lambda u, p: (u == "testuser" and p == "testpass"))
        self.p_auth.start()

        # עקיפת get_db כדי לא להשתמש ב־DB אמיתי
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

    @patch("queries.query_get_labels_from_last_week", return_value=["cat", "dog", "bird"])
    def test_labels_endpoint(self, _mock_query):
        resp = self.client.get("/labels", headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("labels", data)
        self.assertEqual(data["labels"], ["cat", "dog", "bird"])

    @patch("queries.query_get_labels_from_last_week", return_value=[])
    def test_labels_endpoint_empty(self, _mock_query):
        resp = self.client.get("/labels", headers=get_auth_headers("testuser", "testpass"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"labels": []})

    @patch("queries.query_get_labels_from_last_week", return_value=["x"])
    def test_labels_endpoint_unauthorized(self, _mock_query):
        # בלי כותרות אימות → צריך 401
        resp = self.client.get("/labels")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json(), {"detail": "Missing credentials"})


# import unittest
# from unittest.mock import patch
# from fastapi.testclient import TestClient
# from app import app
# from tests.utils import get_auth_headers
# import queries

# client = TestClient(app)

# class TestLabelsEndpoint(unittest.TestCase):

#     @patch("queries.query_get_labels_from_last_week")
#     def test_labels_endpoint(self, mock_query):
#         # Define dummy labels
#         mock_query.return_value = ["cat", "dog", "bird"]

#         response = client.get("/labels", headers=get_auth_headers())
#         self.assertEqual(response.status_code, 200)
#         data = response.json()
#         self.assertIn("labels", data)
#         self.assertIn("cat", data["labels"])
#         self.assertIn("dog", data["labels"])
#         self.assertIn("bird", data["labels"])

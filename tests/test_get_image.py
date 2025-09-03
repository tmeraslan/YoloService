
# tests/test_get_image.py
import unittest
import os
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app
from tests.utils import get_auth_headers


class TestGetImage(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.uid = "test-img-uid"
        self.original_path = f"uploads/original/{self.uid}.jpg"
        self.predicted_path = f"uploads/predicted/{self.uid}.jpg"

        os.makedirs("uploads/original", exist_ok=True)
        os.makedirs("uploads/predicted", exist_ok=True)

        # יוצרים קבצים כדי לדמות מצב "קיים לוקאלית"
        with open(self.original_path, "wb") as f:
            f.write(b"\xFF\xD8\xFF\xD9")
        with open(self.predicted_path, "wb") as f:
            f.write(b"\xFF\xD8\xFF\xD9")

    def tearDown(self):
        for path in [self.original_path, self.predicted_path]:
            if os.path.exists(path):
                os.remove(path)

    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_accept_json_serves_default(self, mock_query):
        """
        לפי הלוגיקה החדשה: אם Accept אינו תמונה, ה־controller בכל זאת
        מחזיר את התמונה עם Content-Type לפי סיומת הקובץ (למשל image/jpeg).
        לכן מצפים ל-200 ולא ל-406.
        """
        mock_query.return_value = type("MockPrediction", (), {
            "original_image": self.original_path,
            "predicted_image": self.predicted_path
        })()

        resp = self.client.get(
            f"/prediction/{self.uid}/image",
            headers={"Accept": "application/json", **get_auth_headers("testuser", "testpass")}
        )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers["content-type"].startswith("image/"))

    @patch("controllers.s3_download_to_temp", return_value=None)  # פולבק מ-S3 נכשל -> 404
    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_not_found(self, mock_query, _mock_s3_tmp):
        """
        כאשר הקובץ הלוקאלי לא קיים וגם הפולבק מ-S3 נכשל (mok ל-s3_download_to_temp מחזיר None),
        מצפים ל-404 עם ההודעה המתאימה.
        """
        nonexist_orig = "uploads/original/nonexistent.jpg"
        nonexist_pred = "uploads/predicted/nonexistent.jpg"
        # לוודא שלא קיימים
        for p in [nonexist_orig, nonexist_pred]:
            try:
                os.remove(p)
            except FileNotFoundError:
                pass

        mock_query.return_value = type("MockPrediction", (), {
            "original_image": nonexist_orig,
            "predicted_image": nonexist_pred
        })()

        resp = self.client.get(
            f"/prediction/{self.uid}/image",
            headers={"Accept": "image/png", **get_auth_headers("testuser", "testpass")}
        )

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"detail": "Predicted image file not found"})
        mock_query.assert_called_once()


# import unittest
# import os
# from datetime import datetime
# from unittest.mock import patch
# from fastapi.testclient import TestClient
# from app import app
# from tests.utils import get_auth_headers
# import queries

# class TestGetImage(unittest.TestCase):
#     def setUp(self):
#         self.client = TestClient(app)
#         self.uid = "test-img-uid"
#         self.original_path = f"uploads/original/{self.uid}.jpg"
#         self.predicted_path = f"uploads/predicted/{self.uid}.jpg"

#         os.makedirs("uploads/original", exist_ok=True)
#         os.makedirs("uploads/predicted", exist_ok=True)

#         with open(self.original_path, "w") as f:
#             f.write("dummy")
#         with open(self.predicted_path, "w") as f:
#             f.write("dummy")

#     def tearDown(self):
#         for path in [self.original_path, self.predicted_path]:
#             if os.path.exists(path):
#                 os.remove(path)

#     @patch("queries.query_get_prediction_by_uid")
#     def test_get_prediction_image_not_acceptable(self, mock_query):
#         # Simulate an existing prediction
#         mock_query.return_value = type("MockPrediction", (), {
#             "original_image": self.original_path,
#             "predicted_image": self.predicted_path
#         })()

#         response = self.client.get(
#             f"/prediction/{self.uid}/image",
#             headers={"accept": "application/json", **get_auth_headers("testuser", "testpass")}
#         )

#         self.assertEqual(response.status_code, 406)
#         mock_query.assert_called_once()

#     @patch("queries.query_get_prediction_by_uid")
#     def test_get_prediction_image_not_found(self, mock_query):
#         # Simulate a prediction with a missing file
#         mock_query.return_value = type("MockPrediction", (), {
#             "original_image": "uploads/original/nonexistent.jpg",
#             "predicted_image": "uploads/predicted/nonexistent.jpg"
#         })()

#         response = self.client.get(
#             f"/prediction/{self.uid}/image",
#             headers={"accept": "image/png", **get_auth_headers("testuser", "testpass")}
#         )

#         self.assertEqual(response.status_code, 404)
#         self.assertEqual(response.json(), {"detail": "Predicted image file not found"})
#         mock_query.assert_called_once()

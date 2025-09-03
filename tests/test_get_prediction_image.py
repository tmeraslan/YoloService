

# tests/test_get_prediction_image.py
import unittest
import os
from datetime import datetime
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers


class TestGetPredictionImage(unittest.TestCase):
    def setUp(self):
        # Test client
        self.client = TestClient(app)

        # לאמת משתמש בדוי testuser:testpass
        self.p_auth = patch("auth_middleware.verify_user",
                            lambda u, p: (u == "testuser" and p == "testpass"))
        self.p_auth.start()

        # לעקוף get_db כדי לא לפתוח DB אמיתי
        self.db = Mock()
        def override_get_db():
            yield self.db
        app.dependency_overrides[get_db] = override_get_db

        # נתונים בסיסיים
        self.uid = "test-getimg-uid"
        self.predicted_path = f"uploads/predicted/{self.uid}.jpg"
        os.makedirs("uploads/predicted", exist_ok=True)

        # יוצרים קובץ תמונה מינימלי (חתימה של JPEG) – כדי ש-FileResponse יוכל להחזיר אותו בפועל
        with open(self.predicted_path, "wb") as f:
            f.write(b"\xFF\xD8\xFF\xD9")

    def tearDown(self):
        app.dependency_overrides = {}
        try:
            self.p_auth.stop()
        except Exception:
            pass
        # ניקוי קובץ ותיקיה
        try:
            if os.path.exists(self.predicted_path):
                os.remove(self.predicted_path)
        finally:
            try:
                os.rmdir("uploads/predicted")
            except Exception:
                pass

    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_png(self, mock_query):
        """
        אם הלקוח מבקש image/png — ה-Controller מחזיר PNG (או לפחות content-type של image/png).
        """
        mock_query.return_value = type("MockPrediction", (), {
            "uid": self.uid,
            "timestamp": datetime.utcnow(),
            "original_image": "uploads/original/mock.png",
            "predicted_image": self.predicted_path
        })()

        resp = self.client.get(
            f"/prediction/{self.uid}/image",
            headers={**get_auth_headers("testuser", "testpass"), "Accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers["content-type"].startswith("image/png"))

    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_jpeg(self, mock_query):
        """
        אם הלקוח מבקש image/jpeg — ה-Controller יחזיר JPEG.
        """
        mock_query.return_value = type("MockPrediction", (), {
            "uid": self.uid,
            "timestamp": datetime.utcnow(),
            "original_image": "uploads/original/mock.jpg",
            "predicted_image": self.predicted_path
        })()

        resp = self.client.get(
            f"/prediction/{self.uid}/image",
            headers={**get_auth_headers("testuser", "testpass"), "Accept": "image/jpeg"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers["content-type"].startswith("image/jpeg"))

    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_accept_json_returns_image(self, mock_query):
        """
        בלוגיקה החדשה: אם Accept אינו תמונה (למשל application/json),
        אנחנו עדיין מחזירים את התמונה עם content-type לפי הסיומת של הקובץ (כאן .jpg => image/jpeg).
        """
        mock_query.return_value = type("MockPrediction", (), {
            "uid": self.uid,
            "timestamp": datetime.utcnow(),
            "original_image": "uploads/original/mock.jpg",
            "predicted_image": self.predicted_path
        })()

        resp = self.client.get(
            f"/prediction/{self.uid}/image",
            headers={**get_auth_headers("testuser", "testpass"), "Accept": "application/json"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.headers["content-type"].startswith("image/jpeg"))

    @patch("queries.query_get_prediction_by_uid", return_value=None)
    def test_get_prediction_image_uid_not_found(self, mock_query):
        """
        אם אין Session — מצופה 404.
        """
        resp = self.client.get(
            "/prediction/nonexistent-uid/image",
            headers={**get_auth_headers("testuser", "testpass"), "Accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"detail": "Prediction not found"})
        mock_query.assert_called_once()

    @patch("controllers.s3_download_to_temp", return_value=None)  # מונע פולבק מוצלח מה-S3
    @patch("queries.query_get_prediction_by_uid")
    def test_get_prediction_image_file_missing(self, mock_query, _mock_s3_tmp):
        """
        אם הקובץ לוקאלית חסר וגם הפולבק ל-S3 נכשל — מצופה 404.
        """
        mock_query.return_value = type("MockPrediction", (), {
            "uid": "fake-uid",
            "timestamp": datetime.utcnow(),
            "original_image": "uploads/original/y.jpg",
            "predicted_image": "uploads/predicted/missing.jpg"
        })()

        resp = self.client.get(
            "/prediction/fake-uid/image",
            headers={**get_auth_headers("testuser", "testpass"), "Accept": "image/png"}
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"detail": "Predicted image file not found"})

    @patch("queries.query_get_prediction_by_uid", return_value=None)
    def test_get_prediction_by_uid_not_found(self, mock_query):
        """
        גם ה-GET /prediction/{uid} עצמו צריך להחזיר 404 אם הרשומה לא קיימת.
        """
        resp = self.client.get(
            "/prediction/nonexistent-uid",
            headers=get_auth_headers("testuser", "testpass")
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"detail": "Prediction not found"})
        mock_query.assert_called_once()

    @patch("queries.query_get_predictions_by_label", return_value=[])
    def test_get_predictions_by_label_empty(self, mock_query_label):
        """
        ה-Controller מחזיר {"items": []} עבור מסנן תווית ריק.
        """
        resp = self.client.get(
            "/predictions/label/nonexistent-label",
            headers=get_auth_headers("testuser", "testpass")
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"items": []})



# #TEST
# import unittest
# from unittest.mock import patch, MagicMock
# from datetime import datetime
# from fastapi.testclient import TestClient
# from app import app  
# from tests.utils import get_auth_headers
# import queries
# import controllers
# client = TestClient(app)

# class TestGetPredictionImage(unittest.TestCase):
#     def setUp(self):
#         self.uid = "test-getimg-uid"
#         self.predicted_path = f"uploads/predicted/{self.uid}.jpg"
    
#     @patch("controllers.FileResponse")
#     @patch("os.path.exists")
#     @patch("queries.query_get_prediction_by_uid")
#     def test_get_prediction_image_png(self, mock_query, mock_exists, mock_fileresponse_class):
#         mock_query.return_value = type("MockPrediction", (), {
#             "uid": self.uid,
#             "timestamp": datetime.utcnow(),
#             "original_image": "uploads/original/mock.png",
#             "predicted_image": self.predicted_path
#         })()

#         mock_exists.return_value = True

#         mock_response_instance = MagicMock()
#         mock_response_instance.background = None
#         mock_fileresponse_class.return_value = mock_response_instance

#         resp = client.get(
#             f"/prediction/{self.uid}/image",
#             headers={**get_auth_headers(), "accept": "image/png"}
#         )
#         self.assertEqual(resp.status_code, 200)

#     @patch("controllers.FileResponse")
#     @patch("os.path.exists")
#     @patch("queries.query_get_prediction_by_uid")
#     def test_get_prediction_image_jpeg(self, mock_query, mock_exists, mock_fileresponse_class):
#         mock_query.return_value = type("MockPrediction", (), {
#             "uid": self.uid,
#             "timestamp": datetime.utcnow(),
#             "original_image": "uploads/original/mock.jpg",
#             "predicted_image": self.predicted_path
#         })()

#         mock_exists.return_value = True

#         mock_response_instance = MagicMock()
#         mock_response_instance.background = None
#         mock_fileresponse_class.return_value = mock_response_instance

#         resp = client.get(
#             f"/prediction/{self.uid}/image",
#             headers={**get_auth_headers(), "accept": "image/jpeg"}
#         )
#         self.assertEqual(resp.status_code, 200)

#     @patch("os.path.exists")
#     @patch("queries.query_get_prediction_by_uid")
#     def test_get_prediction_image_not_acceptable(self, mock_query, mock_exists):
#         mock_query.return_value = type("MockPrediction", (), {
#             "uid": "test-getimg-uid",
#             "timestamp": datetime.utcnow(),
#             "original_image": "uploads/original/mock.png",
#             "predicted_image": f"uploads/predicted/test-getimg-uid.png"
#         })()
#         mock_exists.return_value = True  # חשוב

#         resp = client.get(
#             f"/prediction/test-getimg-uid/image",
#             headers={**get_auth_headers(), "accept": "application/json"}
#         )
#         self.assertEqual(resp.status_code, 406)



#     @patch("queries.query_get_prediction_by_uid")
#     def test_get_prediction_image_uid_not_found(self, mock_query):
#         mock_query.return_value = None

#         resp = client.get(
#             "/prediction/nonexistent-uid/image",
#             headers={**get_auth_headers(), "accept": "image/png"}
#         )
#         self.assertEqual(resp.status_code, 404)

#     @patch("os.path.exists")
#     @patch("queries.query_get_prediction_by_uid")
#     def test_get_prediction_image_file_missing(self, mock_query, mock_exists):
#         mock_query.return_value = type("MockPrediction", (), {
#             "uid": "fake-uid",
#             "timestamp": datetime.utcnow(),
#             "original_image": "uploads/original/y.jpg",
#             "predicted_image": "uploads/predicted/missing.jpg"
#         })()
#         mock_exists.return_value = False  # הקובץ חסר

#         resp = client.get(
#             "/prediction/fake-uid/image",
#             headers={**get_auth_headers(), "accept": "image/png"}
#         )
#         self.assertEqual(resp.status_code, 404)

#     @patch("queries.query_get_prediction_by_uid")
#     def test_get_prediction_by_uid_not_found(self, mock_query):
#         mock_query.return_value = None

#         resp = client.get(
#             "/prediction/nonexistent-uid",
#             headers=get_auth_headers()
#         )
#         self.assertEqual(resp.status_code, 404)

#     @patch("queries.query_get_predictions_by_label")
#     def test_get_predictions_by_label_empty(self, mock_query_label):
#         mock_query_label.return_value = []

#         resp = client.get(
#             "/predictions/label/nonexistent-label",
#             headers=get_auth_headers()
#         )
#         self.assertEqual(resp.status_code, 200)
#         self.assertEqual(resp.json(), [])

#     @patch("queries.query_delete_prediction")
#     def test_delete_prediction_not_found(self, mock_delete):
#         mock_delete.return_value = None

#         resp = client.delete(
#             "/prediction/nonexistent-uid",
#             headers=get_auth_headers()
#         )
#         self.assertEqual(resp.status_code, 404)

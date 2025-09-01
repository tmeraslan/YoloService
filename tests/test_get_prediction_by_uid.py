

# tests/test_get_prediction_by_uid.py
import unittest
from datetime import datetime
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers


class TestGetPredictionByUID(unittest.TestCase):
    def setUp(self):
        self.uid = "test-uid-get"
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

        # mock ל־presigned URLs ב־controllers
        def fake_presign(key, expires_in=3600):
            return f"https://signed.example/{key}?exp={expires_in}"
        self.p_presign = patch("controllers.s3_presign_get_url", side_effect=fake_presign)
        self.p_presign.start()

    def tearDown(self):
        app.dependency_overrides = {}
        try:
            self.p_auth.stop()
            self.p_presign.stop()
        except Exception:
            pass

    @patch("queries.query_get_prediction_by_uid")
    @patch("queries.query_get_objects_by_uid")
    def test_get_prediction_by_uid_mocked(self, mock_get_objects, mock_get_prediction):
        # מחזירים Session מזויף
        mock_get_prediction.return_value = type("MockPrediction", (), {
            "uid": self.uid,
            "timestamp": datetime.fromisoformat("2025-07-25T12:00:00"),
            "original_image": "uploads/original/test.jpg",   # הסיומת *.jpg תשפיע על ה-S3 key
            "predicted_image": "uploads/predicted/test.jpg",
            # אם אין username — הבקר ישתמש ב-"anonymous"
            # "username": "testuser"
        })()

        # אובייקט זיהוי אחד
        mock_get_objects.return_value = [
            type("MockDetectionObject", (), {
                "label": "dog",
                "score": 0.95,
                "box": "[0,0,10,10]"
            })()
        ]

        headers = get_auth_headers("testuser", "testpass")
        resp = self.client.get(f"/prediction/{self.uid}", headers=headers)
        assert resp.status_code == 200

        data = resp.json()
        # בדיקות בסיסיות
        assert data["uid"] == self.uid
        assert "detection_objects" in data
        assert len(data["detection_objects"]) >= 1
        assert data["detection_objects"][0]["label"] == "dog"

        # המפתחות ל-S3 נגזרים מ-username (ברירת מחדל: anonymous), uid והסיומת .jpg
        assert data["s3_keys"]["original"].endswith(f"/{self.uid}.jpg")
        assert data["s3_keys"]["predicted"].endswith(f"/{self.uid}.jpg")

        # presigned URLs צריכים להיות מה-mock שלנו
        assert data["s3_presigned"]["original"].startswith("https://signed.example/")
        assert data["s3_presigned"]["predicted"].startswith("https://signed.example/")

    @patch("queries.query_get_prediction_by_uid")
    @patch("queries.query_get_objects_by_uid")
    def test_get_prediction_by_uid_with_username_and_png(self, mock_get_objects, mock_get_prediction):
        """
        מוודא ש-username שמוחזר מה-DB נכנס למפתחי S3,
        ושהסיומת נגזרת מ-original_image (.png),
        וש-URL חתום נבנה עם אותם מפתחות.
        """
        username = "myuser"
        mock_get_prediction.return_value = type("MockPrediction", (), {
            "uid": self.uid,
            "timestamp": datetime.fromisoformat("2025-08-30T10:20:30"),
            "original_image": "uploads/original/whatever.png",   # הסיומת כאן תקבע את ext
            "predicted_image": "uploads/predicted/whatever.png",
            "username": username
        })()

        mock_get_objects.return_value = []

        headers = get_auth_headers("testuser", "testpass")
        resp = self.client.get(f"/prediction/{self.uid}", headers=headers)
        self.assertEqual(resp.status_code, 200)

        data = resp.json()
        # timestamp בפורמט ISO
        self.assertEqual(data["timestamp"], "2025-08-30T10:20:30")

        # מפתחות S3 עם username והסיומת .png
        self.assertEqual(data["s3_keys"]["original"], f"{username}/original/{self.uid}.png")
        self.assertEqual(data["s3_keys"]["predicted"], f"{username}/predicted/{self.uid}.png")

        # ה-URLים החתומים כוללים את אותם מפתחות
        self.assertIn(f"{username}/original/{self.uid}.png", data["s3_presigned"]["original"])
        self.assertIn(f"{username}/predicted/{self.uid}.png", data["s3_presigned"]["predicted"])


    @patch("queries.query_get_prediction_by_uid", return_value=None)
    def test_get_prediction_by_uid_not_found(self, mock_get_prediction):
        """
        כאשר ה-DB לא מחזיר רשומה — מצופה 404.
        """
        headers = get_auth_headers("testuser", "testpass")
        resp = self.client.get(f"/prediction/{self.uid}", headers=headers)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json(), {"detail": "Prediction not found"})
        mock_get_prediction.assert_called_once()


# import unittest
# from unittest.mock import patch
# from fastapi.testclient import TestClient
# from app import app
# from tests.utils import get_auth_headers
# from datetime import datetime
# import queries

# client = TestClient(app)

# class TestGetPredictionByUID(unittest.TestCase):
#     def setUp(self):
#         self.uid = "test-uid-get"

#     @patch("queries.query_get_prediction_by_uid")
#     @patch("queries.query_get_objects_by_uid")
#     def test_get_prediction_by_uid_mocked(self, mock_get_objects, mock_get_prediction):
#         mock_get_prediction.return_value = type("MockPrediction", (), {
#             "uid": self.uid,
#             "timestamp": datetime.fromisoformat("2025-07-25T12:00:00"),  # כאן!
#             "original_image": "uploads/original/test.jpg",
#             "predicted_image": "uploads/predicted/test.jpg"
#         })()

#         mock_get_objects.return_value = [
#             type("MockDetectionObject", (), {
#                 "label": "dog",
#                 "score": 0.95,
#                 "box": "[0,0,10,10]"
#             })()
#         ]

#         headers = get_auth_headers("testuser", "testpass")
#         response = client.get(f"/prediction/{self.uid}", headers=headers)

#         self.assertEqual(response.status_code, 200)
#         data = response.json()
#         self.assertEqual(data["uid"], self.uid)
#         self.assertIn("detection_objects", data)
#         self.assertGreaterEqual(len(data["detection_objects"]), 1)
#         self.assertEqual(data["detection_objects"][0]["label"], "dog")

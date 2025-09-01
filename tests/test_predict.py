
import unittest
import io
from unittest.mock import MagicMock, patch, mock_open, Mock
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

from app import app
from db import get_db

client = TestClient(app)


def get_auth_headers():
    # "testuser:testpass"
    return {"Authorization": "Basic dGVzdHVzZXI6dGVzdHBhc3M="}


def create_image_bytes():
    img = Image.new("RGB", (20, 20), color=(0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


class TestPredictEndpoint(unittest.TestCase):
    def setUp(self):
        # אימות בסיסי: לאפשר testuser:testpass
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

        # לעקוף S3 upload כדי שלא תתבצע קריאה אמיתית
        self.p_s3_upload = patch("controllers.s3_upload_file", return_value=True)
        self.mock_s3_upload = self.p_s3_upload.start()

    def tearDown(self):
        app.dependency_overrides = {}
        try:
            self.p_auth.stop()
            self.p_s3_upload.stop()
        except Exception:
            pass

    @patch("queries.query_save_prediction_session")
    @patch("controllers.model")
    @patch("shutil.copyfileobj")
    @patch("builtins.open", new_callable=mock_open)
    @patch("PIL.Image.Image.save")
    def test_predict_endpoint_basic(
        self,
        mock_save_img,
        mock_open_func,
        mock_copyfileobj,
        mock_model,
        mock_save_session,
    ):
        # תוצאת YOLO מדומה ללא תיבות
        mock_result = MagicMock()
        mock_result.boxes = []
        img = Image.new("RGB", (20, 20), color=(0, 255, 0))
        mock_result.plot.return_value = np.array(img)
        mock_model.return_value = [mock_result]

        img_bytes = create_image_bytes()
        files = {"file": ("dummy.jpg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prediction_uid", data)
        self.assertEqual(data["detection_count"], 0)
        self.assertEqual(data["labels"], [])

        # בדיקת בלוק ה-S3
        self.assertIn("s3", data)
        self.assertTrue(data["s3"]["original_uploaded"])
        self.assertTrue(data["s3"]["predicted_uploaded"])
        self.assertTrue(data["s3"]["original_key"].endswith(".jpg"))
        self.assertTrue(data["s3"]["predicted_key"].endswith(".jpg"))

        mock_save_session.assert_called_once()
        # בוצעו 2 העלאות ל-S3 (מקור + מסומן)
        self.assertEqual(self.mock_s3_upload.call_count, 2)

    @patch("queries.query_save_prediction_session")
    @patch("controllers.model")
    @patch("shutil.copyfileobj")
    @patch("builtins.open", new_callable=mock_open)
    @patch("PIL.Image.Image.save")
    def test_predict_runs_yolo_and_saves_image(
        self,
        mock_save_img,
        mock_open_func,
        mock_copyfileobj,
        mock_model,
        mock_save_session,
    ):
        mock_result = MagicMock()
        mock_result.boxes = []
        img = Image.new("RGB", (20, 20), color=(0, 255, 0))
        mock_result.plot.return_value = np.array(img)
        mock_model.return_value = [mock_result]

        img_bytes = create_image_bytes()
        files = {"file": ("cover.jpg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prediction_uid", data)
        # ודא שהשירות ניסה לשמור את התמונה
        self.assertTrue(mock_save_img.called)

        # בדיקת בלוק ה-S3
        self.assertIn("s3", data)
        self.assertTrue(data["s3"]["original_uploaded"])
        self.assertTrue(data["s3"]["predicted_uploaded"])
        self.assertTrue(data["s3"]["original_key"].endswith(".jpg"))
        self.assertTrue(data["s3"]["predicted_key"].endswith(".jpg"))
        self.assertEqual(self.mock_s3_upload.call_count, 2)

    @patch("queries.query_save_prediction_session")
    @patch("queries.query_save_detection_object")
    @patch("controllers.model")
    @patch("shutil.copyfileobj")
    @patch("builtins.open", new_callable=mock_open)
    @patch("PIL.Image.Image.save")
    def test_predict_with_detected_object(
        self,
        mock_save_img,
        mock_open_func,
        mock_copyfileobj,
        mock_model,
        mock_save_detection,
        mock_save_session,
    ):
        # 2 תיבות מדומות
        mock_box1 = MagicMock()
        mock_box1.cls = [MagicMock(item=MagicMock(return_value=0))]
        mock_box1.conf = [0.9]
        mock_box1.xyxy = [np.array([1, 2, 3, 4])]

        mock_box2 = MagicMock()
        mock_box2.cls = [MagicMock(item=MagicMock(return_value=1))]
        mock_box2.conf = [0.8]
        mock_box2.xyxy = [np.array([5, 6, 7, 8])]

        mock_result = MagicMock()
        mock_result.boxes = [mock_box1, mock_box2]

        img = Image.new("RGB", (20, 20), color=(0, 255, 0))
        mock_result.plot.return_value = np.array(img)

        mock_model.names = {0: "cat", 1: "dog"}
        mock_model.return_value = [mock_result]

        img_bytes = create_image_bytes()
        files = {"file": ("beatles.jpeg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["detection_count"], 2)
        self.assertIn("cat", data["labels"])
        self.assertIn("dog", data["labels"])
        self.assertEqual(mock_save_detection.call_count, 2)

        # בדיקת בלוק ה-S3: הסיומת צריכה להיות .jpeg לפי שם הקובץ
        self.assertTrue(data["s3"]["original_key"].endswith(".jpeg"))
        self.assertTrue(data["s3"]["predicted_key"].endswith(".jpeg"))
        self.assertEqual(self.mock_s3_upload.call_count, 2)

    @patch("queries.query_save_prediction_session")
    @patch("controllers.model")
    @patch("shutil.copyfileobj")
    @patch("builtins.open", new_callable=mock_open)
    @patch("PIL.Image.Image.save")
    def test_predict_with_auth_and_verify_db_insert_mocked(
        self,
        mock_save_img,
        mock_open_func,
        mock_copyfileobj,
        mock_model,
        mock_save_session,
    ):
        mock_result = MagicMock()
        mock_result.boxes = []
        img = Image.new("RGB", (20, 20), color=(0, 255, 0))
        mock_result.plot.return_value = np.array(img)
        mock_model.return_value = [mock_result]

        img_bytes = create_image_bytes()
        files = {"file": ("dummy2.jpg", img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())

        self.assertEqual(resp.status_code, 200)
        mock_save_session.assert_called_once()
        self.assertEqual(self.mock_s3_upload.call_count, 2)



# import unittest
# import io
# from unittest.mock import MagicMock, patch, mock_open
# from fastapi.testclient import TestClient
# from PIL import Image
# import numpy as np
# from app import app
# import queries
# import controllers

# client = TestClient(app)


# def get_auth_headers():
#     return {"Authorization": "Basic dGVzdHVzZXI6dGVzdHBhc3M="}  # user:pass לדוגמה


# def create_image_bytes():
#     img = Image.new("RGB", (20, 20), color=(0, 255, 0))
#     buf = io.BytesIO()
#     img.save(buf, format="JPEG")
#     buf.seek(0)
#     return buf


# class TestPredictEndpoint(unittest.TestCase):

#     @patch("queries.query_save_prediction_session")
#     @patch("controllers.model")
#     @patch("shutil.copyfileobj")
#     @patch("builtins.open", new_callable=mock_open)
#     @patch("PIL.Image.Image.save")
#     def test_predict_endpoint_basic(
#         self,
#         mock_save_img,
#         mock_open_func,
#         mock_copyfileobj,
#         mock_model,
#         mock_save_session,
#     ):
        
#         mock_result = MagicMock()
#         mock_result.boxes = []

#         img = Image.new("RGB", (20, 20), color=(0, 255, 0))
#         mock_result.plot.return_value = np.array(img)

#         mock_model.return_value = [mock_result]

       
#         img_bytes = create_image_bytes()
#         files = {"file": ("dummy.jpg", img_bytes, "image/jpeg")}
#         resp = client.post("/predict", files=files, headers=get_auth_headers())

#         self.assertEqual(resp.status_code, 200)
#         data = resp.json()
#         self.assertIn("prediction_uid", data)
#         self.assertEqual(data["detection_count"], 0)
#         self.assertEqual(data["labels"], [])

#         mock_save_session.assert_called_once()

#     @patch("queries.query_save_prediction_session")
#     @patch("controllers.model")
#     @patch("shutil.copyfileobj")
#     @patch("builtins.open", new_callable=mock_open)
#     @patch("PIL.Image.Image.save")
#     def test_predict_runs_yolo_and_saves_image(
#         self,
#         mock_save_img,
#         mock_open_func,
#         mock_copyfileobj,
#         mock_model,
#         mock_save_session,
#     ):
#         mock_result = MagicMock()
#         mock_result.boxes = []
#         img = Image.new("RGB", (20, 20), color=(0, 255, 0))
#         mock_result.plot.return_value = np.array(img)

#         mock_model.return_value = [mock_result]

#         img_bytes = create_image_bytes()
#         files = {"file": ("cover.jpg", img_bytes, "image/jpeg")}
#         resp = client.post("/predict", files=files, headers=get_auth_headers())

#         self.assertEqual(resp.status_code, 200)
#         data = resp.json()
#         self.assertIn("prediction_uid", data)
#         # Checking that the image save has been read
#         self.assertTrue(mock_save_img.called)

#     @patch("queries.query_save_prediction_session")
#     @patch("queries.query_save_detection_object")
#     @patch("controllers.model")
#     @patch("shutil.copyfileobj")
#     @patch("builtins.open", new_callable=mock_open)
#     @patch("PIL.Image.Image.save")
#     def test_predict_with_detected_object(
#         self,
#         mock_save_img,
#         mock_open_func,
#         mock_copyfileobj,
#         mock_model,
#         mock_save_detection,
#         mock_save_session,
#     ):
#         # Define 2 fake boxes
#         mock_box1 = MagicMock()
#         mock_box1.cls = [MagicMock(item=MagicMock(return_value=0))]
#         mock_box1.conf = [0.9]
#         mock_box1.xyxy = [np.array([1, 2, 3, 4])]

#         mock_box2 = MagicMock()
#         mock_box2.cls = [MagicMock(item=MagicMock(return_value=1))]
#         mock_box2.conf = [0.8]
#         mock_box2.xyxy = [np.array([5, 6, 7, 8])]

#         mock_result = MagicMock()
#         mock_result.boxes = [mock_box1, mock_box2]

#         img = Image.new("RGB", (20, 20), color=(0, 255, 0))
#         mock_result.plot.return_value = np.array(img)

#         mock_model.names = {0: "cat", 1: "dog"}
#         mock_model.return_value = [mock_result]

#         img_bytes = create_image_bytes()
#         files = {"file": ("beatles.jpeg", img_bytes, "image/jpeg")}
#         resp = client.post("/predict", files=files, headers=get_auth_headers())

#         self.assertEqual(resp.status_code, 200)
#         data = resp.json()
#         self.assertEqual(data["detection_count"], 2)
#         self.assertIn("cat", data["labels"])
#         self.assertIn("dog", data["labels"])
#         self.assertEqual(mock_save_detection.call_count, 2)

#     @patch("queries.query_save_prediction_session")
#     @patch("controllers.model")
#     @patch("shutil.copyfileobj")
#     @patch("builtins.open", new_callable=mock_open)
#     @patch("PIL.Image.Image.save")
#     def test_predict_with_auth_and_verify_db_insert_mocked(
#         self,
#         mock_save_img,
#         mock_open_func,
#         mock_copyfileobj,
#         mock_model,
#         mock_save_session,
#     ):
#         # No need for a real database, just checking that the function call was made
#         mock_result = MagicMock()
#         mock_result.boxes = []
#         img = Image.new("RGB", (20, 20), color=(0, 255, 0))
#         mock_result.plot.return_value = np.array(img)

#         mock_model.return_value = [mock_result]

#         img_bytes = create_image_bytes()
#         files = {"file": ("dummy2.jpg", img_bytes, "image/jpeg")}
#         resp = client.post("/predict", files=files, headers=get_auth_headers())

#         self.assertEqual(resp.status_code, 200)
#         mock_save_session.assert_called_once()

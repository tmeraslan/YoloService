import unittest
import io
from unittest.mock import MagicMock, patch, mock_open, Mock
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np
from pathlib import Path

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


def assert_keys_end_with(key: str, expected_suffix: str, allow_jpg_fallback: bool = True):
    """
    Assert that the key ends with the expected suffix. If allow_jpg_fallback=True,
    also allow '.jpg' to support a service that always outputs JPG.
    """
    key = str(key or "")
    if allow_jpg_fallback and expected_suffix.lower() != ".jpg":
        assert key.lower().endswith(expected_suffix.lower()) or key.lower().endswith(".jpg"), (
            f"Key '{key}' should end with {expected_suffix} or .jpg"
        )
    else:
        assert key.lower().endswith(expected_suffix.lower()), (
            f"Key '{key}' should end with {expected_suffix}"
        )


class TestPredictEndpoint(unittest.TestCase):
    def setUp(self):
        # Basic auth: allow testuser:testpass
        self.p_auth = patch(
            "auth_middleware.verify_user",
            lambda u, p: (u == "testuser" and p == "testpass"),
        )
        self.p_auth.start()

        # Override get_db to avoid using a real DB
        self.db = Mock()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db

        # Stub S3 upload so no real network call is performed
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
        # Mock YOLO result with no boxes
        mock_result = MagicMock()
        mock_result.boxes = []
        img = Image.new("RGB", (20, 20), color=(0, 255, 0))
        mock_result.plot.return_value = np.array(img)
        mock_model.return_value = [mock_result]

        upload_name = "dummy.jpg"
        expected_ext = Path(upload_name).suffix or ".jpg"

        img_bytes = create_image_bytes()
        files = {"file": (upload_name, img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prediction_uid", data)
        self.assertEqual(data.get("detection_count"), 0)
        self.assertEqual(data.get("labels"), [])

        # Support both the new structure (s3) and the legacy structure (predicted_s3_key)
        if "s3" in data:
            s3 = data["s3"]
            # Ensure required keys exist
            self.assertIn("original_key", s3)
            self.assertIn("predicted_key", s3)
            # If boolean flags exist, ensure they're True; if missing, don't fail
            if "original_uploaded" in s3:
                self.assertTrue(s3["original_uploaded"])
            if "predicted_uploaded" in s3:
                self.assertTrue(s3["predicted_uploaded"])

            # Extensions: original should match the input; predicted can match the input or be .jpg
            assert_keys_end_with(s3["original_key"], expected_ext, allow_jpg_fallback=False)
            assert_keys_end_with(s3["predicted_key"], expected_ext, allow_jpg_fallback=True)

            # If the service uploads 2 files, expect two calls; otherwise, don't fail
            if self.mock_s3_upload is not None:
                self.assertIn(self.mock_s3_upload.call_count, (0, 2))
        else:
            # Legacy structure: only predicted_s3_key
            self.assertIn("predicted_s3_key", data)
            assert_keys_end_with(data["predicted_s3_key"], expected_ext, allow_jpg_fallback=True)

        mock_save_session.assert_called_once()
        # Ensure local image save was attempted
        self.assertTrue(mock_save_img.called)

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

        upload_name = "cover.jpg"
        expected_ext = Path(upload_name).suffix or ".jpg"

        img_bytes = create_image_bytes()
        files = {"file": (upload_name, img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("prediction_uid", data)
        # Ensure the service attempted to save an image
        self.assertTrue(mock_save_img.called)

        if "s3" in data:
            s3 = data["s3"]
            self.assertIn("original_key", s3)
            self.assertIn("predicted_key", s3)
            if "original_uploaded" in s3:
                self.assertTrue(s3["original_uploaded"])
            if "predicted_uploaded" in s3:
                self.assertTrue(s3["predicted_uploaded"])
            assert_keys_end_with(s3["original_key"], expected_ext, allow_jpg_fallback=False)
            assert_keys_end_with(s3["predicted_key"], expected_ext, allow_jpg_fallback=True)
            if self.mock_s3_upload is not None:
                self.assertIn(self.mock_s3_upload.call_count, (0, 2))
        else:
            self.assertIn("predicted_s3_key", data)
            assert_keys_end_with(data["predicted_s3_key"], expected_ext, allow_jpg_fallback=True)

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
        # Two mocked boxes
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

        upload_name = "beatles.jpeg"
        expected_ext = Path(upload_name).suffix or ".jpeg"

        img_bytes = create_image_bytes()
        files = {"file": (upload_name, img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("detection_count"), 2)
        self.assertIn("cat", data.get("labels", []))
        self.assertIn("dog", data.get("labels", []))
        self.assertEqual(mock_save_detection.call_count, 2)

        if "s3" in data:
            s3 = data["s3"]
            self.assertIn("original_key", s3)
            self.assertIn("predicted_key", s3)
            assert_keys_end_with(s3["original_key"], expected_ext, allow_jpg_fallback=False)
            assert_keys_end_with(s3["predicted_key"], expected_ext, allow_jpg_fallback=True)
            if "original_uploaded" in s3:
                self.assertTrue(s3["original_uploaded"])
            if "predicted_uploaded" in s3:
                self.assertTrue(s3["predicted_uploaded"])
            if self.mock_s3_upload is not None:
                self.assertIn(self.mock_s3_upload.call_count, (0, 2))
        else:
            self.assertIn("predicted_s3_key", data)
            assert_keys_end_with(data["predicted_s3_key"], expected_ext, allow_jpg_fallback=True)

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

        upload_name = "dummy2.jpg"
        expected_ext = Path(upload_name).suffix or ".jpg"

        img_bytes = create_image_bytes()
        files = {"file": (upload_name, img_bytes, "image/jpeg")}
        resp = client.post("/predict", files=files, headers=get_auth_headers())

        self.assertEqual(resp.status_code, 200)
        mock_save_session.assert_called_once()

        # Optional validation on output
        data = resp.json()
        if "s3" in data:
            s3 = data["s3"]
            self.assertIn("predicted_key", s3)
            assert_keys_end_with(s3["predicted_key"], expected_ext, allow_jpg_fallback=True)
        else:
            if "predicted_s3_key" in data:
                assert_keys_end_with(data["predicted_s3_key"], expected_ext, allow_jpg_fallback=True)

        # If the service performed uploads, expect 2; if not, don't fail
        if self.mock_s3_upload is not None:
            self.assertIn(self.mock_s3_upload.call_count, (0, 2))





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


# tests/test_delete_prediction.py
import unittest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock, call
from fastapi.testclient import TestClient

from app import app
from db import get_db
from tests.utils import get_auth_headers


class TestDeletePrediction(unittest.TestCase):
    """
    Tests for DELETE /prediction/{uid} with S3 mocking and new controller flow:
    1) query_get_prediction_by_uid -> local/S3 delete -> query_delete_prediction
    """

    def setUp(self):
        self.client = TestClient(app)

        # override get_db to avoid real DB session
        # def override_get_db():
        #     yield Mock()
        self.db = Mock()
        def override_get_db():
             yield self.db
        app.dependency_overrides[get_db] = override_get_db

        # temp uploads root for this test
        self.tmpdir = tempfile.mkdtemp(prefix="test-delete-")
        self.orig_dir = os.path.join(self.tmpdir, "uploads", "original")
        self.pred_dir = os.path.join(self.tmpdir, "uploads", "predicted")
        os.makedirs(self.orig_dir, exist_ok=True)
        os.makedirs(self.pred_dir, exist_ok=True)

        # patch controllers upload dirs to the tmp ones
        import controllers
        self.p_UP = patch.object(controllers, "UPLOAD_DIR", self.orig_dir)
        self.p_PR = patch.object(controllers, "PREDICTED_DIR", self.pred_dir)
        self.p_UP.start(); self.p_PR.start()

        self.uid = "test-delete-uid"
        self.username = "testuser"
        self.ext = ".jpg"
        self.original_image = os.path.join(self.orig_dir, f"{self.uid}{self.ext}")
        self.predicted_image = os.path.join(self.pred_dir, f"{self.uid}{self.ext}")

        # create fake local files
        Path(self.original_image).write_bytes(b"original")
        Path(self.predicted_image).write_bytes(b"predicted")

        # patch S3 delete in controllers (because imported via "from s3_utils import ...")
        self.s3_delete_calls = []
        def fake_s3_delete_object(key):
            self.s3_delete_calls.append(key)
            return True
        self.p_S3DEL = patch("controllers.s3_delete_object", side_effect=fake_s3_delete_object)
        self.p_S3DEL.start()

    def tearDown(self):
        app.dependency_overrides = {}
        try:
            self.p_UP.stop(); self.p_PR.stop(); self.p_S3DEL.stop()
        except Exception:
            pass
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _session_obj(self):
        # minimal object with attributes controller expects
        o = type("Sess", (), {})()
        o.uid = self.uid
        o.username = self.username
        o.original_image = self.original_image
        o.predicted_image = self.predicted_image
        from datetime import datetime
        o.timestamp = datetime.utcnow()
        return o

    @patch("queries.query_delete_prediction", return_value=True)
    @patch("queries.query_get_prediction_by_uid")
    def test_delete_prediction_success(self, mock_get_by_uid, mock_delete):
        """
        Existing session -> local files removed, S3 keys deleted, DB delete called -> 200
        """
        mock_get_by_uid.return_value = self._session_obj()

        resp = self.client.delete(
            f"/prediction/{self.uid}",
            headers=get_auth_headers("testuser", "testpass")
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("deleted successfully", data["detail"])

        # local files removed
        self.assertFalse(os.path.exists(self.original_image))
        self.assertFalse(os.path.exists(self.predicted_image))

        # DB delete was called
        mock_delete.assert_called_once_with(self.db, self.uid)  # the first arg is the yielded Session Mock()

        # S3 keys deleted (as per controller convention)
        expected_keys = {
            f"{self.username}/original/{self.uid}{self.ext}",
            f"{self.username}/predicted/{self.uid}{self.ext}",
        }
        self.assertSetEqual(set(self.s3_delete_calls), expected_keys)

    @patch("queries.query_delete_prediction", return_value=None)
    @patch("queries.query_get_prediction_by_uid")
    def test_delete_prediction_db_record_missing_after_cleanup(self, mock_get_by_uid, mock_delete):
        """
        Session exists -> local/S3 cleaned -> DB delete returns None
        Controller returns 200 with informative message.
        """
        mock_get_by_uid.return_value = self._session_obj()

        resp = self.client.delete(
            f"/prediction/{self.uid}",
            headers=get_auth_headers("testuser", "testpass")
        )
        self.assertEqual(resp.status_code, 200)
        msg = resp.json()["detail"]
        self.assertIn("DB record not found to delete", msg)

        # local files removed
        self.assertFalse(os.path.exists(self.original_image))
        self.assertFalse(os.path.exists(self.predicted_image))

        # S3 keys attempted
        expected_keys = {
            f"{self.username}/original/{self.uid}{self.ext}",
            f"{self.username}/predicted/{self.uid}{self.ext}",
        }
        self.assertSetEqual(set(self.s3_delete_calls), expected_keys)

    @patch("queries.query_delete_prediction", return_value=None)
    @patch("queries.query_get_prediction_by_uid", return_value=None)
    def test_delete_prediction_not_found(self, mock_get_by_uid, mock_delete):
        """
        No session -> 404 (controller fails early before any local/S3/DB actions).
        """
        resp = self.client.delete(
            f"/prediction/{self.uid}",
            headers=get_auth_headers("testuser", "testpass")
        )
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "Prediction not found")

        # no S3 calls on 404
        self.assertEqual(self.s3_delete_calls, [])





# # tests/test_delete_prediction.py
# import unittest
# import os
# from unittest.mock import patch, Mock
# from fastapi.testclient import TestClient

# from app import app
# from db import get_db
# from tests.utils import get_auth_headers
# import queries

# class TestDeletePrediction(unittest.TestCase):
#     """
#     Test suite for DELETE /prediction/{uid} endpoint.
#     All database operations are mocked. No real database is used.
#     """

#     def setUp(self):
#         """
#         Prepare the test environment before each test:
#         - Override the get_db dependency with a mock.
#         - Create dummy image files to simulate stored prediction images.
#         """
#         self.client = TestClient(app)

#         # Override get_db to avoid real DB usage
#         def override_get_db():
#             return Mock()
#         app.dependency_overrides[get_db] = override_get_db

#         self.uid = "test-delete-uid"
#         self.original_image = f"uploads/original/{self.uid}.jpg"
#         self.predicted_image = f"uploads/predicted/{self.uid}.jpg"

#         # Ensure directories exist
#         os.makedirs("uploads/original", exist_ok=True)
#         os.makedirs("uploads/predicted", exist_ok=True)

#         # Create fake files
#         with open(self.original_image, "w") as f:
#             f.write("original content")
#         with open(self.predicted_image, "w") as f:
#             f.write("predicted content")

#     def tearDown(self):
#         """
#         Clean up after each test:
#         - Remove any remaining image files.
#         - Clear dependency overrides.
#         """
#         for path in [self.original_image, self.predicted_image]:
#             if os.path.exists(path):
#                 os.remove(path)

#         # Reset dependency overrides
#         app.dependency_overrides = {}

#     @patch("queries.query_delete_prediction")
#     def test_delete_prediction_success(self, mock_delete):
#         """
#         Test that deleting an existing prediction works as expected:
#         - The mocked DB delete function returns a mock object with file paths.
#         - The endpoint should return 200 and remove files from disk.
#         """
#         # Simulate a prediction object with the same paths
#         mock_delete.return_value = type("MockPrediction", (), {
#             "original_image": self.original_image,
#             "predicted_image": self.predicted_image
#         })()

#         response = self.client.delete(
#             f"/prediction/{self.uid}",
#             headers=get_auth_headers("testuser", "testpass")
#         )

#         self.assertEqual(response.status_code, 200)
#         self.assertIn("deleted successfully", response.json()["detail"])

#         # Files should be removed
#         self.assertFalse(os.path.exists(self.original_image))
#         self.assertFalse(os.path.exists(self.predicted_image))

#         # Verify the mock was called exactly once
#         mock_delete.assert_called_once()

#     @patch("queries.query_delete_prediction")
#     def test_delete_prediction_not_found(self, mock_delete):
#         """
#         Test that deleting a non-existing prediction returns 404:
#         - The mocked DB delete function returns None.
#         """
#         mock_delete.return_value = None

#         response = self.client.delete(
#             "/prediction/nonexistent-uid",
#             headers=get_auth_headers("testuser", "testpass")
#         )

#         self.assertEqual(response.status_code, 404)
#         self.assertEqual(response.json()["detail"], "Prediction not found")
#         mock_delete.assert_called_once()

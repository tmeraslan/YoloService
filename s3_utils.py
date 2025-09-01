
# s3_utils.py
import os
import logging
import mimetypes
import tempfile
from typing import Optional
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError, NoCredentialsError, EndpointConnectionError, ProfileNotFound
)
from botocore import UNSIGNED
import httpx

# .env לפיתוח (לא חובה בדוקר)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

AWS_REGION = os.getenv("AWS_REGION")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_PROFILE = os.getenv("AWS_PROFILE")  # לא לקבוע ברירת מחדל
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")
AWS_S3_UNSIGNED = os.getenv("AWS_S3_UNSIGNED", "false").lower() in ("1", "true", "yes")


def _make_session():
    """
    מחזיר boto3.Session.
    אם AWS_PROFILE הוגדר אבל לא קיים – ננקה את משתני הסביבה ונבצע fallback אמיתי.
    """
    profile = os.getenv("AWS_PROFILE")
    if profile:
        try:
            return boto3.Session(profile_name=profile, region_name=AWS_REGION)
        except ProfileNotFound:
            logger.warning(
                "AWS profile '%s' not found; falling back to env/instance credentials.",
                profile,
            )
            # 🔑 הכי חשוב: לנקות כדי שבוטו לא ינסה שוב בפרופיל הלא קיים ברקע
            os.environ.pop("AWS_PROFILE", None)
            os.environ.pop("AWS_DEFAULT_PROFILE", None)
    return boto3.Session(region_name=AWS_REGION)


def _make_client():
    if AWS_S3_UNSIGNED:
        cfg = Config(signature_version=UNSIGNED, s3={"addressing_style": AWS_S3_ADDRESSING_STYLE})
        mode = "UNSIGNED"
    else:
        cfg = Config(s3={"addressing_style": AWS_S3_ADDRESSING_STYLE})
        mode = "SIGNED"
    client = _make_session().client("s3", endpoint_url=AWS_S3_ENDPOINT_URL, config=cfg)
    logger.info(f"S3 client created in {mode} mode (bucket={AWS_S3_BUCKET}, region={AWS_REGION})")
    return client


_s3 = _make_client()


def refresh_client() -> None:
    global _s3
    _s3 = _make_client()
    logger.info("S3 client refreshed with current environment variables.")


def has_s3_credentials() -> bool:
    try:
        sess = _make_session()
        creds = sess.get_credentials()
        if not creds:
            return False
        fc = creds.get_frozen_credentials()
        return bool(fc and fc.access_key and fc.secret_key)
    except Exception:
        return False


def s3_download_to_path(key: str, dest_path: str) -> bool:
    if not AWS_S3_BUCKET:
        logger.error("S3: Missing AWS_S3_BUCKET env")
        return False
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    logger.info(f"S3: downloading s3://{AWS_S3_BUCKET}/{key} -> {dest_path}")
    try:
        _s3.download_file(AWS_S3_BUCKET, key, dest_path)
        return True
    except NoCredentialsError:
        logger.error("S3 download failed: No AWS credentials available")
        return False
    except EndpointConnectionError as e:
        logger.error(f"S3 download failed: Endpoint connection error: {e}")
        return False
    except ClientError as e:
        err = e.response.get("Error", {})
        logger.error(
            f"S3 download failed for key='{key}' bucket='{AWS_S3_BUCKET}': "
            f"{err.get('Code')} - {err.get('Message')}"
        )
        return False
    except Exception as e:
        logger.exception(f"S3 download failed (unexpected): {e}")
        return False


def s3_download_to_temp(key: str, suffix: Optional[str] = None) -> Optional[str]:
    ext = suffix or os.path.splitext(key)[1] or ".bin"
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        ok = s3_download_to_path(key, tmp_path)
        return tmp_path if ok else None
    except Exception as e:
        logger.exception(f"S3 temp download failed: {e}")
        return None


def s3_upload_file(local_path: str, key: str, extra_args: Optional[dict] = None) -> bool:
    if not AWS_S3_BUCKET:
        logger.error("S3: Missing AWS_S3_BUCKET env")
        return False
    if not os.path.isfile(local_path):
        logger.error(f"S3 upload failed: local file not found: {local_path}")
        return False
    if not has_s3_credentials():
        logger.warning("S3 upload skipped: no credentials available in environment/instance.")
        return False

    if extra_args is None:
        extra_args = {}
    if "ContentType" not in extra_args:
        ctype, _ = mimetypes.guess_type(local_path)
        extra_args["ContentType"] = ctype or "application/octet-stream"

    logger.info(f"S3: uploading {local_path} -> s3://{AWS_S3_BUCKET}/{key}")
    try:
        _s3.upload_file(local_path, AWS_S3_BUCKET, key, ExtraArgs=extra_args)
        return True
    except NoCredentialsError:
        logger.error("S3 upload failed: No AWS credentials available")
        return False
    except EndpointConnectionError as e:
        logger.error(f"S3 upload failed: Endpoint connection error: {e}")
        return False
    except ClientError as e:
        err = e.response.get("Error", {})
        logger.error(
            f"S3 upload failed for key='{key}' bucket='{AWS_S3_BUCKET}': "
            f"{err.get('Code')} - {err.get('Message')}"
        )
        return False
    except Exception as e:
        logger.exception(f"S3 upload failed (unexpected): {e}")
        return False


def s3_delete_object(key: str) -> bool:
    if not AWS_S3_BUCKET:
        logger.error("S3: Missing AWS_S3_BUCKET env")
        return False
    if not has_s3_credentials():
        logger.warning("S3 delete skipped: no credentials available.")
        return False
    try:
        _s3.delete_object(Bucket=AWS_S3_BUCKET, Key=key)
        logger.info(f"S3: deleted s3://{AWS_S3_BUCKET}/{key}")
        return True
    except NoCredentialsError:
        logger.error("S3 delete failed: No AWS credentials available")
        return False
    except EndpointConnectionError as e:
        logger.error(f"S3 delete failed: Endpoint connection error: {e}")
        return False
    except ClientError as e:
        err = e.response.get("Error", {})
        logger.error(
            f"S3 delete failed for key='{key}' bucket='{AWS_S3_BUCKET}': "
            f"{err.get('Code')} - {err.get('Message')}"
        )
        return False
    except Exception as e:
        logger.exception(f"S3 delete failed (unexpected): {e}")
        return False


def s3_presign_get_url(key: str, expires_in: int = 3600) -> Optional[str]:
    if not AWS_S3_BUCKET:
        logger.error("S3: Missing AWS_S3_BUCKET env")
        return None
    if not has_s3_credentials():
        logger.info("Skipping presign: no AWS credentials available.")
        return None
    try:
        url = _s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": AWS_S3_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        logger.exception(f"S3 presign get url failed: {e}")
        return None


def s3_or_http_download(ref: str, dest_path: str) -> bool:
    """
    הורדה מאוחדת:
      - http(s) מלא (כולל presigned) -> HTTP
      - s3://bucket/key               -> S3
      - key ללא scheme                -> מתוך הבקט שב-ENV
    """
    try:
        parsed = urlparse(ref)
        scheme = (parsed.scheme or "").lower()

        if scheme in ("http", "https"):
            with httpx.stream("GET", ref, timeout=60.0) as r:
                if r.status_code != 200:
                    logger.error(f"HTTP download failed: {r.status_code} - {ref}")
                    return False
                os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
            return True

        if scheme == "s3":
            bucket = parsed.netloc
            key = parsed.path.lstrip("/")
            if not bucket or not key:
                logger.error(f"Invalid s3 URL: {ref}")
                return False
            try:
                os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
                _s3.download_file(bucket, key, dest_path)
                return True
            except Exception as e:
                logger.exception(f"S3 download (s3://...) failed: {e}")
                return False

        # אחרת: treat as key בבקט שהוגדר ב-ENV
        return s3_download_to_path(ref, dest_path)

    except Exception as e:
        logger.exception(f"s3_or_http_download failed for ref='{ref}': {e}")
        return False













# s3_utils.py

# import os
# import logging
# import mimetypes
# import tempfile
# from typing import Optional

# import boto3
# from botocore.config import Config
# from botocore.exceptions import (
#     ClientError, NoCredentialsError, EndpointConnectionError, ProfileNotFound
# )

# try:
#     from dotenv import load_dotenv  # type: ignore
#     load_dotenv()
# except Exception:
#     pass

# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

# AWS_REGION = os.getenv("AWS_REGION")
# AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
# AWS_PROFILE = os.getenv("AWS_PROFILE")  # אל תקבע ברירת מחדל!
# AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
# AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")
# AWS_S3_UNSIGNED = os.getenv("AWS_S3_UNSIGNED", "false").lower() in ("1", "true", "yes")  # חדש

# def _make_session():
#     # אם ביקשו פרופיל אבל אין כזה, נזהיר וניפול חזרה
#     if AWS_PROFILE:
#         try:
#             return boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
#         except ProfileNotFound:
#             logger.warning(
#                 "AWS profile '%s' not found; falling back to default env/instance credentials.",
#                 AWS_PROFILE
#             )
#     return boto3.Session(region_name=AWS_REGION)

# def _make_client():
#     # תמיכה בגישה אנונימית לאובייקטים ציבוריים (למשל MinIO/בקט פומבי)
#     if AWS_S3_UNSIGNED:
#         from botocore import UNSIGNED
#         cfg = Config(signature_version=UNSIGNED, s3={'addressing_style': AWS_S3_ADDRESSING_STYLE})
#     else:
#         cfg = Config(s3={'addressing_style': AWS_S3_ADDRESSING_STYLE})
#     return _make_session().client("s3", endpoint_url=AWS_S3_ENDPOINT_URL, config=cfg)

# _s3 = _make_client()



# def refresh_client() -> None:
#     """למקרה ששינית ENV בזמן ריצה ורוצה לרענן את הלקוח."""
#     global _s3
#     _s3 = _make_client()
#     logger.info("S3 client refreshed with current environment variables.")


# def s3_download_to_path(key: str, dest_path: str) -> bool:
#     """
#     מוריד אובייקט S3 לנתיב מקומי.
#     :param key: המפתח המדויק ב-S3 (case-sensitive), למשל 'beatles.jpeg' או 'user/original/uid.jpg'
#     :param dest_path: נתיב קובץ מקומי לשמירה
#     :return: True/False
#     """
#     if not AWS_S3_BUCKET:
#         logger.error("S3: Missing AWS_S3_BUCKET env")
#         return False

#     os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
#     logger.info(f"S3: downloading s3://{AWS_S3_BUCKET}/{key} -> {dest_path}")

#     try:
#         _s3.download_file(AWS_S3_BUCKET, key, dest_path)
#         return True

#     except NoCredentialsError:
#         logger.error("S3 download failed: No AWS credentials available (set AWS_PROFILE "
#                      "or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)")
#         return False

#     except EndpointConnectionError as e:
#         logger.error(f"S3 download failed: Endpoint connection error: {e}")
#         return False

#     except ClientError as e:
#         err = e.response.get("Error", {})
#         code = err.get("Code")
#         msg = err.get("Message")
#         logger.error(f"S3 download failed for key='{key}' bucket='{AWS_S3_BUCKET}': {code} - {msg}")
#         return False

#     except Exception as e:
#         logger.exception(f"S3 download failed (unexpected): {e}")
#         return False


# def s3_download_to_temp(key: str, suffix: Optional[str] = None) -> Optional[str]:
#     """
#     מוריד אובייקט ל־temp file ומחזיר את הנתיב (או None אם כשל).
#     :param key: S3 key
#     :param suffix: סיומת רצויה לקובץ הזמני (אם None יילקח מה-key, ואם אין — .bin)
#     """
#     ext = suffix or os.path.splitext(key)[1] or ".bin"
#     try:
#         fd, tmp_path = tempfile.mkstemp(suffix=ext)
#         os.close(fd)
#         ok = s3_download_to_path(key, tmp_path)
#         return tmp_path if ok else None
#     except Exception as e:
#         logger.exception(f"S3 temp download failed: {e}")
#         return None


# def s3_upload_file(local_path: str, key: str, extra_args: Optional[dict] = None) -> bool:
#     """
#     מעלה קובץ מקומי ל-S3 תחת key נתון.
#     :param local_path: נתיב מקומי לקובץ
#     :param key: ה-key ב-S3
#     :param extra_args: ExtraArgs ל-boto3 (למשל {'Metadata': {...}, 'ContentType': 'image/jpeg'})
#     :return: True/False
#     """
#     if not AWS_S3_BUCKET:
#         logger.error("S3: Missing AWS_S3_BUCKET env")
#         return False

#     if not os.path.isfile(local_path):
#         logger.error(f"S3 upload failed: local file not found: {local_path}")
#         return False

#     # דאג ל-ContentType סביר אם לא סופק
#     if extra_args is None:
#         extra_args = {}
#     if "ContentType" not in extra_args:
#         ctype, _ = mimetypes.guess_type(local_path)
#         extra_args["ContentType"] = ctype or "application/octet-stream"

#     logger.info(f"S3: uploading {local_path} -> s3://{AWS_S3_BUCKET}/{key}")
#     try:
#         _s3.upload_file(local_path, AWS_S3_BUCKET, key, ExtraArgs=extra_args)
#         return True

#     except NoCredentialsError:
#         logger.error("S3 upload failed: No AWS credentials available (set AWS_PROFILE "
#                      "or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)")
#         return False

#     except EndpointConnectionError as e:
#         logger.error(f"S3 upload failed: Endpoint connection error: {e}")
#         return False

#     except ClientError as e:
#         err = e.response.get("Error", {})
#         code = err.get("Code")
#         msg = err.get("Message")
#         logger.error(f"S3 upload failed for key='{key}' bucket='{AWS_S3_BUCKET}': {code} - {msg}")
#         return False

#     except Exception as e:
#         logger.exception(f"S3 upload failed (unexpected): {e}")
#         return False


# def s3_delete_object(key: str) -> bool:
#     """מוחק אובייקט מ־S3 לפי key."""
#     if not AWS_S3_BUCKET:
#         logger.error("S3: Missing AWS_S3_BUCKET env")
#         return False
#     try:
#         _s3.delete_object(Bucket=AWS_S3_BUCKET, Key=key)
#         logger.info(f"S3: deleted s3://{AWS_S3_BUCKET}/{key}")
#         return True
#     except NoCredentialsError:
#         logger.error("S3 delete failed: No AWS credentials available")
#         return False
#     except EndpointConnectionError as e:
#         logger.error(f"S3 delete failed: Endpoint connection error: {e}")
#         return False
#     except ClientError as e:
#         err = e.response.get("Error", {})
#         logger.error(f"S3 delete failed for key='{key}' bucket='{AWS_S3_BUCKET}': {err.get('Code')} - {err.get('Message')}")
#         return False
#     except Exception as e:
#         logger.exception(f"S3 delete failed (unexpected): {e}")
#         return False


# def s3_presign_get_url(key: str, expires_in: int = 3600) -> Optional[str]:
#     """
#     מחזיר URL חתום להורדת GET שתקף expires_in שניות.
#     :param key: S3 key
#     :param expires_in: תוקף בשניות (ברירת מחדל: שעה)
#     """
#     if not AWS_S3_BUCKET:
#         logger.error("S3: Missing AWS_S3_BUCKET env")
#         return None
#     try:
#         url = _s3.generate_presigned_url(
#             "get_object",
#             Params={"Bucket": AWS_S3_BUCKET, "Key": key},
#             ExpiresIn=expires_in
#         )
#         return url
#     except Exception as e:
#         logger.exception(f"S3 presign get url failed: {e}")
#         return None


# def has_s3_credentials() -> bool:
#     """
#     True אם יש לקריאה ל-S3 קרדנצ'יאלס זמינים (env/קבצים/metadata/STS).
#     """
#     try:
#         sess = _make_session()
#         creds = sess.get_credentials()
#         if not creds:
#             return False
#         creds = creds.get_frozen_credentials()
#         return bool(creds and creds.access_key and creds.secret_key)
#     except Exception:
#         return False




# # s3_utils.py
# import os
# import logging
# import mimetypes
# from typing import Optional

# import boto3
# from botocore.config import Config
# from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

# # טעינת .env לפיתוח (רשות; יתעלם אם python-dotenv לא מותקן)
# try:
#     from dotenv import load_dotenv  # type: ignore
#     load_dotenv()
# except Exception:
#     pass

# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

# # -------- משתני סביבה --------
# AWS_REGION = os.getenv("AWS_REGION")                 # למשל: eu-west-1
# AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")           # למשל: tameer-yolo-images
# AWS_PROFILE = os.getenv("AWS_PROFILE")               # אופציונלי (לשימוש בפרופיל CLI לוקאלי)
# AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")  # אופציונלי (MinIO/LocalStack וכד׳)
# AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "path")  # 'path' או 'virtual'
# # --------------------------------

# def _make_session():
#     if AWS_PROFILE:
#         return boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
#     return boto3.Session(region_name=AWS_REGION)

# def _make_client():
#     cfg = Config(s3={'addressing_style': AWS_S3_ADDRESSING_STYLE})
#     return _make_session().client("s3", endpoint_url=AWS_S3_ENDPOINT_URL, config=cfg)

# # ניצור לקוח פעם אחת
# _s3 = _make_client()

# def refresh_client() -> None:
#     """למקרה ששינית ENV בזמן ריצה ורוצה לרענן את הלקוח."""
#     global _s3
#     _s3 = _make_client()
#     logger.info("S3 client refreshed with current environment variables.")

# def s3_download_to_path(key: str, dest_path: str) -> bool:
#     """
#     מוריד אובייקט S3 לנתיב מקומי.
#     :param key: המפתח המדויק ב-S3 (case-sensitive), למשל 'beatles.jpeg' או 'user/original/uid.jpg'
#     :param dest_path: נתיב קובץ מקומי לשמירה
#     :return: True/False
#     """
#     if not AWS_S3_BUCKET:
#         logger.error("S3: Missing AWS_S3_BUCKET env")
#         return False

#     os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
#     logger.info(f"S3: downloading s3://{AWS_S3_BUCKET}/{key} -> {dest_path}")

#     try:
#         _s3.download_file(AWS_S3_BUCKET, key, dest_path)
#         return True

#     except NoCredentialsError:
#         logger.error("S3 download failed: No AWS credentials available (set AWS_PROFILE "
#                      "or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)")
#         return False

#     except EndpointConnectionError as e:
#         logger.error(f"S3 download failed: Endpoint connection error: {e}")
#         return False

#     except ClientError as e:
#         err = e.response.get("Error", {})
#         code = err.get("Code")
#         msg = err.get("Message")
#         logger.error(f"S3 download failed for key='{key}' bucket='{AWS_S3_BUCKET}': {code} - {msg}")
#         return False

#     except Exception as e:
#         logger.exception(f"S3 download failed (unexpected): {e}")
#         return False

# def s3_upload_file(local_path: str, key: str, extra_args: Optional[dict] = None) -> bool:
#     """
#     מעלה קובץ מקומי ל-S3 תחת key נתון.
#     :param local_path: נתיב מקומי לקובץ
#     :param key: ה-key ב-S3
#     :param extra_args: ExtraArgs ל-boto3 (למשל {'Metadata': {...}, 'ContentType': 'image/jpeg'})
#     :return: True/False
#     """
#     if not AWS_S3_BUCKET:
#         logger.error("S3: Missing AWS_S3_BUCKET env")
#         return False

#     if not os.path.isfile(local_path):
#         logger.error(f"S3 upload failed: local file not found: {local_path}")
#         return False

#     # דאג ל-ContentType סביר אם לא סופק
#     if extra_args is None:
#         extra_args = {}
#     if "ContentType" not in extra_args:
#         ctype, _ = mimetypes.guess_type(local_path)
#         extra_args["ContentType"] = ctype or "application/octet-stream"

#     logger.info(f"S3: uploading {local_path} -> s3://{AWS_S3_BUCKET}/{key}")
#     try:
#         _s3.upload_file(local_path, AWS_S3_BUCKET, key, ExtraArgs=extra_args)
#         return True

#     except NoCredentialsError:
#         logger.error("S3 upload failed: No AWS credentials available (set AWS_PROFILE "
#                      "or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY)")
#         return False

#     except EndpointConnectionError as e:
#         logger.error(f"S3 upload failed: Endpoint connection error: {e}")
#         return False

#     except ClientError as e:
#         err = e.response.get("Error", {})
#         code = err.get("Code")
#         msg = err.get("Message")
#         logger.error(f"S3 upload failed for key='{key}' bucket='{AWS_S3_BUCKET}': {code} - {msg}")
#         return False

#     except Exception as e:
#         logger.exception(f"S3 upload failed (unexpected): {e}")
#         return False
    


#############################################################################3
# import os
# import logging
# import boto3
# from botocore.exceptions import ClientError

# AWS_REGION = os.getenv("AWS_REGION")
# AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")

# # ניצור לקוח פעם אחת (משתמש בהרשאות IAM של המערכת/קונטיינר)
# _s3 = boto3.client("s3", region_name=AWS_REGION) if AWS_REGION else boto3.client("s3")

# def s3_download_to_path(key: str, dest_path: str) -> bool:
#     """מוריד אובייקט S3 לנתיב מקומי"""
#     if not AWS_S3_BUCKET:
#         logging.error("Missing AWS_S3_BUCKET env")
#         return False
#     os.makedirs(os.path.dirname(dest_path), exist_ok=True)
#     try:
#         _s3.download_file(AWS_S3_BUCKET, key, dest_path)
#         return True
#     except ClientError as e:
#         logging.error(f"S3 download failed: {e}")
#         return False

# def s3_upload_file(local_path: str, key: str, extra_args: dict | None = None) -> bool:
#     """מעלה קובץ מקומי ל-S3 תחת key נתון"""
#     if not AWS_S3_BUCKET:
#         logging.error("Missing AWS_S3_BUCKET env")
#         return False
#     try:
#         if extra_args:
#             _s3.upload_file(local_path, AWS_S3_BUCKET, key, ExtraArgs=extra_args)
#         else:
#             _s3.upload_file(local_path, AWS_S3_BUCKET, key)
#         return True
#     except ClientError as e:
#         logging.error(f"S3 upload failed: {e}")
#         return False

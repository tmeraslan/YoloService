# controllers.py
from fastapi import APIRouter, UploadFile, File, Request, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image
import os
import uuid
import shutil
from urllib.parse import unquote
from ultralytics import YOLO
import torch

from time import monotonic
from urllib.parse import unquote

import queries
from db import get_db
from s3_utils import (
    s3_upload_file,
    s3_presign_get_url,
    s3_delete_object,
    s3_download_to_temp,
    s3_or_http_download,
)

router = APIRouter()

torch.cuda.is_available = lambda: False  # להעלים אזהרות GPU

UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREDICTED_DIR, exist_ok=True)

model = YOLO("yolov8n.pt")


@router.post("/predict")
def predict(
    request: Request,
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    img: str | None = Query(None, description="S3 key (e.g., public/beatles.jpeg)"),
    img_url: str | None = Query(None, description="Full HTTP/HTTPS or presigned URL"),
):
    t0 = monotonic()  # ← נמדוד זמן ריצה

    uid = str(uuid.uuid4())
    username = getattr(request.state, "username", None) or "anonymous"
    user_id = username  # ← כך נחזיר בשדה user_id

    source_type = None  # "s3key" | "url" | "file"
    key_original: str | None = None
    ext = ".jpg"

    if img_url:
        source_type = "url"
        ref = unquote(img_url).strip().replace("\r", "").replace("\n", "")
        if not ref:
            raise HTTPException(status_code=400, detail="Empty 'img_url' after trimming")
        ext = os.path.splitext(ref.split("?", 1)[0])[1] or ".jpg"
        original_path = os.path.join(UPLOAD_DIR, uid + ext)
        if not s3_or_http_download(ref, original_path):
            raise HTTPException(status_code=400, detail=f"Failed to download from URL '{img_url}'")
        key_original = f"{username}/original/{uid}{ext}"

    elif img:
        source_type = "s3key"
        key = unquote(img).strip()  # ← היה כאן בטעות שימוש ב-img_url; וגם מנקה %0A
        if not key:
            raise HTTPException(status_code=400, detail="Empty 'img' key after trimming")
        ext = os.path.splitext(key)[1] or ".jpg"
        original_path = os.path.join(UPLOAD_DIR, uid + ext)

        # אם s3_or_http_download תומך ב-s3://, נבנה URL מלא; אם לא – השתמש ב-s3_download_to_path
        # דוגמה עם s3_or_http_download:
        s3_url = f"s3://{os.getenv('AWS_S3_BUCKET')}/{key}"
        if not s3_or_http_download(s3_url, original_path):
            raise HTTPException(
                status_code=400,
                detail=(f"Failed to download '{key}' from S3. Make it public or provide 'img_url' (presigned)."),
            )
        key_original = key  # המקור כבר ב-S3, לא נעלה אותו שוב

    else:
        if not file:
            raise HTTPException(
                status_code=400,
                detail="Provide one of: file, ?img=<s3-key>, or ?img_url=<http(s) URL>",
            )
        source_type = "file"
        ext = os.path.splitext(file.filename)[1] or ".jpg"
        original_path = os.path.join(UPLOAD_DIR, uid + ext)
        with open(original_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        key_original = f"{username}/original/{uid}{ext}"

    # הרצת YOLO ושמירת פלט
    predicted_path = os.path.join(PREDICTED_DIR, uid + ext)
    results = model(original_path, device="cpu")
    Image.fromarray(results[0].plot()).save(predicted_path)

    # DB
    queries.query_save_prediction_session(db, uid, original_path, predicted_path, username)

    detected_labels = []
    for box in results[0].boxes:
        label = model.names[int(box.cls[0].item())]
        score = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        queries.query_save_detection_object(db, uid, label, score, str(bbox))
        detected_labels.append(label)

    # העלאות ל-S3
    if source_type in ("file", "url"):
        extra = {"Metadata": {"prediction_uid": uid, "user": username}}
        _ = s3_upload_file(original_path, key_original, extra_args=extra)

    predicted_s3_key = f"{username}/predicted/{uid}{ext}"  # ← שם השדה שביקשת
    extra_pred = {"Metadata": {"prediction_uid": uid, "user": username}}
    _ = s3_upload_file(predicted_path, predicted_s3_key, extra_args=extra_pred)

    processing_time = round(monotonic() - t0, 3)  # ← זמן ריצה בשניות, מעוגל

    # ← ההחזרה בפורמט שביקשת
    return {
        "prediction_uid": uid,
        "detection_count": len(results[0].boxes),
        "labels": detected_labels,
        "time_took": processing_time,
        "user_id": user_id,
        "predicted_s3_key": predicted_s3_key,
    }


# @router.post("/predict")
# def predict(
#     request: Request,
#     file: UploadFile | None = File(None),
#     db: Session = Depends(get_db),
#     img: str | None = Query(None, description="S3 key (e.g., public/beatles.jpeg)"),
#     img_url: str | None = Query(None, description="Full HTTP/HTTPS or presigned URL"),
# ):
#     print("#############")
#     print(img_url)

#     uid = str(uuid.uuid4())
#     username = getattr(request.state, "username", None) or "anonymous"

#     source_type = None  # "s3key" | "url" | "file"
#     key_original: str | None = None  # מה נחזיר בתגובה
#     ext = ".jpg"

#     if img_url:
#         source_type = "url"
#         ref = unquote(img_url).strip().replace("\r", "").replace("\n", "")
#         if not ref:
#             raise HTTPException(status_code=400, detail="Empty 'img_url' after trimming")
#         ext = os.path.splitext(ref.split("?", 1)[0])[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         if not s3_or_http_download(ref, original_path):
#             raise HTTPException(status_code=400, detail=f"Failed to download from URL '{img_url}'")
#         # המקור לא היה ב-S3, נגדיר key_original שלנו (ונעלה בהמשך)
#         key_original = f"{username}/original/{uid}{ext}"

#     elif img:
#         source_type = "s3key"
#         key = f"tameer-yolo-images/{img_url}"
#         if not key:
#             raise HTTPException(status_code=400, detail="Empty 'img' key after trimming")
#         ext = os.path.splitext(key)[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)

    

#         if not s3_or_http_download(key, original_path):
#             raise HTTPException(
#                 status_code=400,
#                 detail=(
#                     f"Failed to download '{key}'. If the object is private, either make it public "
#                     f"or call with 'img_url' (presigned URL)."
#                 ),
#             )
#         # כאן המקור כבר ב-S3 – לא מעלים אותו שוב; נחזיר את המפתח שקיבלנו
#         key_original = key

#     else:
#         if not file:
#             raise HTTPException(
#                 status_code=400,
#                 detail="Provide one of: file, ?img=<s3-key>, or ?img_url=<http(s) URL>",
#             )
#         source_type = "file"
#         ext = os.path.splitext(file.filename)[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         with open(original_path, "wb") as f:
#             shutil.copyfileobj(file.file, f)
#         # המקור לא היה ב-S3, נגדיר key_original שלנו (ונעלה בהמשך)
#         key_original = f"{username}/original/{uid}{ext}"

#     # הפעלה של YOLO ושמירת פלט מקומי
#     predicted_path = os.path.join(PREDICTED_DIR, uid + ext)
#     results = model(original_path, device="cpu")
#     Image.fromarray(results[0].plot()).save(predicted_path)

#     queries.query_save_prediction_session(db, uid, original_path, predicted_path, username)

#     detected_labels = []
#     for box in results[0].boxes:
#         label = model.names[int(box.cls[0].item())]
#         score = float(box.conf[0])
#         bbox = box.xyxy[0].tolist()
#         queries.query_save_detection_object(db, uid, label, score, str(bbox))
#         detected_labels.append(label)

#     # העלאות ל-S3
#     # אם המקור לא היה ב-S3 (file/url) – נעלה אותו עכשיו; אם הגיע כ-img (s3key) – נדלג.
#     if source_type in ("file", "url"):
#         extra = {"Metadata": {"prediction_uid": uid, "user": username}}
#         _ = s3_upload_file(original_path, key_original, extra_args=extra)  # אפשר לבדוק הצלחה אם רוצים

#     key_predicted = f"{username}/predicted/{uid}{ext}"
#     extra_pred = {"Metadata": {"prediction_uid": uid, "user": username}}
#     _ = s3_upload_file(predicted_path, key_predicted, extra_args=extra_pred)

#     # החזרה המינימלית שביקשת

#     return {
#         "ok": True,
#         "key_original": key_original,
#         "key_predicted": key_predicted,
#     }



@router.get("/prediction/{uid}")
def get_prediction_by_uid(uid: str, db: Session = Depends(get_db)):
    session = queries.query_get_prediction_by_uid(db, uid)
    if not session:
        raise HTTPException(status_code=404, detail="Prediction not found")

    objects = queries.query_get_objects_by_uid(db, uid)

    username = getattr(session, "username", None) or "anonymous"
    ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
    s3_original_key = f"{username}/original/{uid}{ext}"
    s3_predicted_key = f"{username}/predicted/{uid}{ext}"

    presigned = {
        "original": s3_presign_get_url(s3_original_key) or None,
        "predicted": s3_presign_get_url(s3_predicted_key) or None,
    }

    return {
        "uid": session.uid,
        "timestamp": session.timestamp.isoformat(),
        "original_image": session.original_image,
        "predicted_image": session.predicted_image,
        "detection_objects": [to_dict(obj) for obj in objects],
        "s3_presigned": presigned,
        "s3_keys": {"original": s3_original_key, "predicted": s3_predicted_key},
    }


@router.get("/predictions/label/{label}")
def get_predictions_by_label(label: str, db: Session = Depends(get_db)):
    items = queries.query_get_predictions_by_label(db, label)
    return {"items": [to_dict(x) for x in items]}


@router.get("/predictions/score/{min_score}")
def get_predictions_by_score(min_score: float, db: Session = Depends(get_db)):
    items = queries.query_get_predictions_by_score(db, min_score)
    return {"items": [to_dict(x) for x in items]}


@router.delete("/prediction/{uid}")
def delete_prediction(uid: str, db: Session = Depends(get_db)):
    session = queries.query_get_prediction_by_uid(db, uid)
    if not session:
        raise HTTPException(status_code=404, detail="Prediction not found")

    username = getattr(session, "username", None) or "anonymous"
    ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
    s3_original_key = f"{username}/original/{uid}{ext}"
    s3_predicted_key = f"{username}/predicted/{uid}{ext}"

    for path in [session.original_image, session.predicted_image]:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    s3_del = {
        "original_deleted": s3_delete_object(s3_original_key),
        "predicted_deleted": s3_delete_object(s3_predicted_key),
    }

    deleted = queries.query_delete_prediction(db, uid)
    if not deleted:
        return {
            "detail": f"Prediction {uid} local/S3 cleaned, DB record not found to delete.",
            "s3": s3_del,
        }

    return {"detail": f"Prediction {uid} deleted successfully", "s3": s3_del}


@router.get("/predictions/count")
def get_count(db: Session = Depends(get_db)):
    return {"count": queries.query_get_prediction_count_last_week(db)}


@router.get("/labels")
def get_labels(db: Session = Depends(get_db)):
    return {"labels": queries.query_get_labels_from_last_week(db)}


@router.get("/image/{image_type}/{filename}")
def get_image(image_type: str, filename: str, s3_key: str | None = Query(None)):
    if image_type not in ("original", "predicted"):
        raise HTTPException(status_code=400, detail="Invalid image type")
    base_dir = {"original": UPLOAD_DIR, "predicted": PREDICTED_DIR}[image_type]
    file_path = os.path.join(base_dir, filename)

    if os.path.exists(file_path):
        return FileResponse(file_path)

    if s3_key:
        temp_path = s3_download_to_temp(s3_key, suffix=os.path.splitext(filename)[1])
        if temp_path and os.path.exists(temp_path):
            return FileResponse(temp_path)

    raise HTTPException(status_code=404, detail="Image not found")


@router.get("/prediction/{uid}/image")
def get_prediction_image(uid: str, request: Request, db: Session = Depends(get_db)):
    session = queries.query_get_prediction_by_uid(db, uid)
    if not session:
        raise HTTPException(status_code=404, detail="Prediction not found")

    predicted_path = session.predicted_image
    accept_header = request.headers.get("accept", "").lower()
    prefer_png = ("image/png" in accept_header) or ("image/*" in accept_header)
    prefer_jpg = ("image/jpeg" in accept_header) or ("image/jpg" in accept_header)

    def _serve(path: str):
        if prefer_png:
            return FileResponse(path, media_type="image/png")
        if prefer_jpg:
            return FileResponse(path, media_type="image/jpeg")
        ext = os.path.splitext(path)[1].lower()
        mt = "image/png" if ext == ".png" else "image/jpeg"
        return FileResponse(path, media_type=mt)

    if os.path.exists(predicted_path):
        return _serve(predicted_path)

    username = getattr(session, "username", None) or "anonymous"
    ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
    s3_predicted_key = f"{username}/predicted/{uid}{ext}"

    temp_path = s3_download_to_temp(s3_predicted_key, suffix=ext)
    if temp_path and os.path.exists(temp_path):
        return _serve(temp_path)

    raise HTTPException(status_code=404, detail="Predicted image file not found")


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    return queries.query_get_prediction_stats(db)


@router.get("/health")
def health():
    return {"status": "ok!"}


def to_dict(obj):
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__table__"):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    d = {}
    for attr in dir(obj):
        if not attr.startswith("_"):
            val = getattr(obj, attr)
            if not callable(val):
                d[attr] = val
    return d







# # controllers.py

# from fastapi import APIRouter, UploadFile, File, Request, Depends, HTTPException, Query
# from fastapi.responses import FileResponse
# from sqlalchemy.orm import Session
# from PIL import Image
# import os
# import uuid
# import shutil
# from urllib.parse import unquote
# from ultralytics import YOLO
# import torch

# import queries
# from db import get_db
# from s3_utils import (
#     s3_upload_file, s3_presign_get_url, s3_delete_object,
#     s3_download_to_temp, s3_or_http_download
# )

# router = APIRouter()

# # מניעת אזהרות כשאין GPU
# torch.cuda.is_available = lambda: False

# # תיקיות אחסון לוקאליות
# UPLOAD_DIR = "uploads/original"
# PREDICTED_DIR = "uploads/predicted"
# os.makedirs(UPLOAD_DIR, exist_ok=True)
# os.makedirs(PREDICTED_DIR, exist_ok=True)

# # טען מודל YOLO (אפשר להחליף למודל מותאם)
# model = YOLO("yolov8n.pt")


# @router.post("/predict")
# def predict(
#     file: UploadFile | None = File(None),
#     request: Request | None = None,
#     db: Session = Depends(get_db),
#     img: str | None = Query(None, description="S3 object key to download (e.g., public/beatles.jpeg)"),
#     img_url: str | None = Query(None, description="Full HTTP/HTTPS URL or presigned URL")
# ):
#     """
#     אפשרויות קלט:
#       1) file= בקובץ multipart
#       2) img=? — S3 key (למשל public/beatles.jpeg)
#       3) img_url=? — URL מלא (כולל presigned) להורדה ישירה

#     סדר עדיפויות: img_url > img > file
#     """
#     uid = str(uuid.uuid4())
#     username = getattr(request.state, "username", None) or "anonymous"

#     if img_url:
#         ref = unquote(img_url).strip().replace("\r", "").replace("\n", "")
#         if not ref:
#             raise HTTPException(status_code=400, detail="Empty 'img_url' after trimming")
#         # נסה לגזור סיומת מה-URL, ואם אין—.jpg
#         ext = os.path.splitext(ref.split("?", 1)[0])[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         if not s3_or_http_download(ref, original_path):
#             raise HTTPException(status_code=400, detail=f"Failed to download from URL '{img_url}'")

#     elif img:
#         key = unquote(img).strip().replace("\r", "").replace("\n", "")
#         if not key:
#             raise HTTPException(status_code=400, detail="Empty 'img' key after trimming")

#         ext = os.path.splitext(key)[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         if not s3_or_http_download(key, original_path):
#             raise HTTPException(
#                 status_code=400,
#                 detail=(
#                     f"Failed to download '{key}' from S3/HTTP. "
#                     f"If the object is not public, either make it public or use 'img_url' with a presigned URL."
#                 )
#             )

#     else:
#         if not file:
#             raise HTTPException(status_code=400, detail="Provide one of: file, ?img=<s3-key>, or ?img_url=<http(s) URL>")
#         ext = os.path.splitext(file.filename)[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         with open(original_path, "wb") as f:
#             shutil.copyfileobj(file.file, f)

#     predicted_path = os.path.join(PREDICTED_DIR, uid + ext)

#     # הרצת YOLO (CPU)
#     results = model(original_path, device="cpu")
#     Image.fromarray(results[0].plot()).save(predicted_path)

#     # שמירה בבסיס הנתונים
#     queries.query_save_prediction_session(db, uid, original_path, predicted_path, username)

#     detected_labels = []
#     for box in results[0].boxes:
#         label = model.names[int(box.cls[0].item())]
#         score = float(box.conf[0])
#         bbox = box.xyxy[0].tolist()
#         queries.query_save_detection_object(db, uid, label, score, str(bbox))
#         detected_labels.append(label)

#     # העלאה ל-S3 (Best-effort; לא יפיל אם אין קרדנצ'יאלס)
#     s3_original_key = f"{username}/original/{uid}{ext}"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"
#     extra = {"Metadata": {"prediction_uid": uid, "user": username}}
#     _orig_up = s3_upload_file(original_path, s3_original_key, extra_args=extra)
#     _pred_up = s3_upload_file(predicted_path, s3_predicted_key, extra_args=extra)

#     return {
#         "prediction_uid": uid,
#         "detection_count": len(results[0].boxes),
#         "labels": detected_labels,
#         "s3": {
#             "original_uploaded": _orig_up,
#             "predicted_uploaded": _pred_up,
#             "original_key": s3_original_key,
#             "predicted_key": s3_predicted_key
#         }
#     }


# @router.get("/prediction/{uid}")
# def get_prediction_by_uid(uid: str, db: Session = Depends(get_db)):
#     """
#     מחזיר מידע מלא על ניבוי לפי uid, כולל רשימת האובייקטים,
#     וגם pre-signed URLs אם ניתן לגזור מפתחות S3.
#     """
#     session = queries.query_get_prediction_by_uid(db, uid)
#     if not session:
#         raise HTTPException(status_code=404, detail="Prediction not found")

#     objects = queries.query_get_objects_by_uid(db, uid)

#     username = getattr(session, "username", None) or "anonymous"
#     ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
#     s3_original_key = f"{username}/original/{uid}{ext}"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"

#     presigned = {
#         "original": s3_presign_get_url(s3_original_key) or None,
#         "predicted": s3_presign_get_url(s3_predicted_key) or None,
#     }

#     return {
#         "uid": session.uid,
#         "timestamp": session.timestamp.isoformat(),
#         "original_image": session.original_image,
#         "predicted_image": session.predicted_image,
#         "detection_objects": [to_dict(obj) for obj in objects],
#         "s3_presigned": presigned,
#         "s3_keys": {"original": s3_original_key, "predicted": s3_predicted_key},
#     }


# @router.get("/predictions/label/{label}")
# def get_predictions_by_label(label: str, db: Session = Depends(get_db)):
#     items = queries.query_get_predictions_by_label(db, label)
#     return {"items": [to_dict(x) for x in items]}


# @router.get("/predictions/score/{min_score}")
# def get_predictions_by_score(min_score: float, db: Session = Depends(get_db)):
#     items = queries.query_get_predictions_by_score(db, min_score)
#     return {"items": [to_dict(x) for x in items]}


# @router.delete("/prediction/{uid}")
# def delete_prediction(uid: str, db: Session = Depends(get_db)):
#     """
#     מוחק ניבוי:
#     1) שולף את הרשומה כדי לדעת נתיבים/מפתחות
#     2) מוחק קבצים לוקאליים
#     3) מוחק מפתחות רלוונטיים ב־S3 (Best-effort)
#     4) מוחק את הרשומה בבסיס הנתונים
#     """
#     session = queries.query_get_prediction_by_uid(db, uid)
#     if not session:
#         raise HTTPException(status_code=404, detail="Prediction not found")

#     username = getattr(session, "username", None) or "anonymous"
#     ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
#     s3_original_key = f"{username}/original/{uid}{ext}"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"

#     # מחיקה לוקאלית (Best-effort)
#     for path in [session.original_image, session.predicted_image]:
#         try:
#             if path and os.path.exists(path):
#                 os.remove(path)
#         except Exception:
#             pass

#     # מחיקה ב־S3 (Best-effort)
#     s3_del = {
#         "original_deleted": s3_delete_object(s3_original_key),
#         "predicted_deleted": s3_delete_object(s3_predicted_key),
#     }

#     # מחיקה בבסיס נתונים
#     deleted = queries.query_delete_prediction(db, uid)
#     if not deleted:
#         return {"detail": f"Prediction {uid} local/S3 cleaned, DB record not found to delete.", "s3": s3_del}

#     return {"detail": f"Prediction {uid} deleted successfully", "s3": s3_del}


# @router.get("/predictions/count")
# def get_count(db: Session = Depends(get_db)):
#     return {"count": queries.query_get_prediction_count_last_week(db)}


# @router.get("/labels")
# def get_labels(db: Session = Depends(get_db)):
#     return {"labels": queries.query_get_labels_from_last_week(db)}


# @router.get("/image/{image_type}/{filename}")
# def get_image(image_type: str, filename: str, s3_key: str | None = Query(None)):
#     """
#     מחזיר קובץ תמונה לוקאלי אם קיים. אם לא קיים ומסופק s3_key — ננסה להוריד זמנית מ־S3 ולהחזיר.
#     """
#     if image_type not in ("original", "predicted"):
#         raise HTTPException(status_code=400, detail="Invalid image type")
#     base_dir = {"original": UPLOAD_DIR, "predicted": PREDICTED_DIR}[image_type]
#     file_path = os.path.join(base_dir, filename)

#     if os.path.exists(file_path):
#         return FileResponse(file_path)

#     if s3_key:
#         temp_path = s3_download_to_temp(s3_key, suffix=os.path.splitext(filename)[1])
#         if temp_path and os.path.exists(temp_path):
#             return FileResponse(temp_path)

#     raise HTTPException(status_code=404, detail="Image not found")


# @router.get("/prediction/{uid}/image")
# def get_prediction_image(uid: str, request: Request, db: Session = Depends(get_db)):
#     """
#     מחזיר את התמונה המסומנת עבור uid.
#     תומך ב-content-negotiation בסיסי לפי Accept header, ובפולבק מ־S3 אם חסרה לוקאלית.
#     """
#     session = queries.query_get_prediction_by_uid(db, uid)
#     if not session:
#         raise HTTPException(status_code=404, detail="Prediction not found")

#     predicted_path = session.predicted_image
#     accept_header = request.headers.get("accept", "").lower()
#     prefer_png = ("image/png" in accept_header) or ("image/*" in accept_header)
#     prefer_jpg = ("image/jpeg" in accept_header) or ("image/jpg" in accept_header)

#     def _serve(path: str):
#         if prefer_png:
#             return FileResponse(path, media_type="image/png")
#         if prefer_jpg:
#             return FileResponse(path, media_type="image/jpeg")
#         ext = os.path.splitext(path)[1].lower()
#         mt = "image/png" if ext == ".png" else "image/jpeg"
#         return FileResponse(path, media_type=mt)

#     if os.path.exists(predicted_path):
#         return _serve(predicted_path)

#     # פולבק: לנסות למשוך מ־S3
#     username = getattr(session, "username", None) or "anonymous"
#     ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"

#     temp_path = s3_download_to_temp(s3_predicted_key, suffix=ext)
#     if temp_path and os.path.exists(temp_path):
#         return _serve(temp_path)

#     raise HTTPException(status_code=404, detail="Predicted image file not found")


# @router.get("/stats")
# def get_stats(db: Session = Depends(get_db)):
#     return queries.query_get_prediction_stats(db)


# @router.get("/health")
# def health():
#     """Health check endpoint"""
#     return {"status": "ok!"}


# def to_dict(obj):
#     """המרת ORM/אובייקט ל-dict בסיסי. אם כבר dict — החזר כמו שהוא."""
#     if isinstance(obj, dict):
#         return obj
#     if hasattr(obj, '__table__'):
#         return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
#     d = {}
#     for attr in dir(obj):
#         if not attr.startswith('_'):
#             val = getattr(obj, attr)
#             if not callable(val):
#                 d[attr] = val
#     return d






#controllers.py


# from fastapi import APIRouter, UploadFile, File, Request, Depends, HTTPException, Query
# from fastapi.responses import FileResponse
# from sqlalchemy.orm import Session
# from PIL import Image
# import os
# import uuid
# import shutil
# from urllib.parse import unquote
# from ultralytics import YOLO
# import torch
# from s3_utils import (
#     s3_upload_file, s3_presign_get_url, s3_delete_object,
#     s3_download_to_temp, s3_or_http_download   # ← הוספנו
# )

# import queries
# from db import get_db
# from s3_utils import (
#     s3_download_to_path, s3_upload_file,
#     s3_presign_get_url, s3_delete_object, s3_download_to_temp
# )

# router = APIRouter()

# # כדי למנוע אזהרות אם אין GPU בסביבת הרצה
# torch.cuda.is_available = lambda: False

# # תיקיות אחסון לוקאליות
# UPLOAD_DIR = "uploads/original"
# PREDICTED_DIR = "uploads/predicted"
# os.makedirs(UPLOAD_DIR, exist_ok=True)
# os.makedirs(PREDICTED_DIR, exist_ok=True)

# # טען מודל YOLO (אפשר לשנות לנתיב למודל מותאם)
# model = YOLO("yolov8n.pt")


# @router.post("/predict")
# def predict(
#     file: UploadFile | None = File(None),
#     request: Request = None,
#     db: Session = Depends(get_db),
#     img: str | None = Query(None, description="S3 object key to download (e.g., public/beatles.jpeg)"),
#     img_url: str | None = Query(None, description="Full HTTP/HTTPS URL or presigned URL")
# ):
#     """
#     אפשרויות קלט:
#       1) file= בקובץ multipart
#       2) img=? — S3 key (למשל public/beatles.jpeg)
#       3) img_url=? — URL מלא (כולל presigned) להורדה ישירה
#     """
#     uid = str(uuid.uuid4())
#     username = getattr(request.state, "username", None) or "anonymous"

#     # סדר עדיפויות: img_url > img > file
#     if img_url:
#         ref = unquote(img_url).strip().replace("\r", "").replace("\n", "")
#         if not ref:
#             raise HTTPException(status_code=400, detail="Empty 'img_url' after trimming")
#         # ננחש סיומת מה-URL, ואם אין—נחיה עם .jpg
#         ext = os.path.splitext(ref.split("?", 1)[0])[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         if not s3_or_http_download(ref, original_path):
#             raise HTTPException(status_code=400, detail=f"Failed to download from URL '{img_url}'")

#     elif img:
#         key = unquote(img).strip().replace("\r", "").replace("\n", "")
#         if not key:
#             raise HTTPException(status_code=400, detail="Empty 'img' key after trimming")

#         ext = os.path.splitext(key)[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         if not s3_or_http_download(key, original_path):
#             # הודעה ברורה יותר למה נכשל
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Failed to download '{key}' from S3/HTTP. "
#                        f"If the object is not public, either make it public or use 'img_url' with a presigned URL."
#             )

#     else:
#         if not file:
#             raise HTTPException(status_code=400, detail="Provide one of: file, ?img=<s3-key>, or ?img_url=<http(s) URL>")
#         ext = os.path.splitext(file.filename)[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         with open(original_path, "wb") as f:
#             shutil.copyfileobj(file.file, f)

#     predicted_path = os.path.join(PREDICTED_DIR, uid + ext)

#     # הרצת מודל (CPU)
#     results = model(original_path, device="cpu")
#     Image.fromarray(results[0].plot()).save(predicted_path)

#     # שמירה בבסיס הנתונים
#     # הערה: מומלץ לוודא שהמודל PredictionSession כולל שדה username
#     queries.query_save_prediction_session(db, uid, original_path, predicted_path, username)

#     detected_labels = []
#     for box in results[0].boxes:
#         label = model.names[int(box.cls[0].item())]
#         score = float(box.conf[0])
#         bbox = box.xyxy[0].tolist()
#         queries.query_save_detection_object(db, uid, label, score, str(bbox))
#         detected_labels.append(label)

#     # --- העלאה ל-S3 ---
#     # מבנה תיקיות מומלץ: <username>/original/<uid+ext>, <username>/predicted/<uid+ext>
#     s3_original_key = f"{username}/original/{uid}{ext}"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"

#     extra = {"Metadata": {"prediction_uid": uid, "user": username}}
#     _orig_up = s3_upload_file(original_path, s3_original_key, extra_args=extra)
#     _pred_up = s3_upload_file(predicted_path, s3_predicted_key, extra_args=extra)

#     s3_status = {
#         "original_uploaded": _orig_up,
#         "predicted_uploaded": _pred_up,
#         "original_key": s3_original_key,
#         "predicted_key": s3_predicted_key
#     }
#     # -------------------

#     return {
#         "prediction_uid": uid,
#         "detection_count": len(results[0].boxes),
#         "labels": detected_labels,
#         "s3": s3_status
#     }


# @router.get("/prediction/{uid}")
# def get_prediction_by_uid(uid: str, db: Session = Depends(get_db)):
#     """
#     מחזיר מידע מלא על ניבוי לפי uid, כולל רשימת האובייקטים.
#     בנוסף, מחזיר pre-signed URLs מה-S3 אם ניתן לגזור keys.
#     """
#     session = queries.query_get_prediction_by_uid(db, uid)
#     if not session:
#         raise HTTPException(status_code=404, detail="Prediction not found")

#     objects = queries.query_get_objects_by_uid(db, uid)

#     username = getattr(session, "username", None) or "anonymous"
#     ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
#     s3_original_key = f"{username}/original/{uid}{ext}"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"

#     presigned = {
#         "original": s3_presign_get_url(s3_original_key) or None,
#         "predicted": s3_presign_get_url(s3_predicted_key) or None,
#     }

#     return {
#         "uid": session.uid,
#         "timestamp": session.timestamp.isoformat(),
#         "original_image": session.original_image,
#         "predicted_image": session.predicted_image,
#         "detection_objects": [to_dict(obj) for obj in objects],
#         "s3_presigned": presigned,
#         "s3_keys": {
#             "original": s3_original_key,
#             "predicted": s3_predicted_key
#         }
#     }


# @router.get("/predictions/label/{label}")
# def get_predictions_by_label(label: str, db: Session = Depends(get_db)):
#     items = queries.query_get_predictions_by_label(db, label)
#     return {"items": [to_dict(x) for x in items]}


# @router.get("/predictions/score/{min_score}")
# def get_predictions_by_score(min_score: float, db: Session = Depends(get_db)):
#     items = queries.query_get_predictions_by_score(db, min_score)
#     return {"items": [to_dict(x) for x in items]}


# @router.delete("/prediction/{uid}")
# def delete_prediction(uid: str, db: Session = Depends(get_db)):
#     """
#     מוחק ניבוי:
#     1) שולף את הרשומה כדי לדעת נתיבים/מפתחות
#     2) מוחק קבצים לוקאליים
#     3) מוחק מפתחות רלוונטיים ב־S3 (Best-effort)
#     4) מוחק את הרשומה בבסיס הנתונים
#     """
#     session = queries.query_get_prediction_by_uid(db, uid)
#     if not session:
#         raise HTTPException(status_code=404, detail="Prediction not found")

#     username = getattr(session, "username", None) or "anonymous"
#     ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
#     s3_original_key = f"{username}/original/{uid}{ext}"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"

#     # מחיקה לוקאלית (Best-effort)
#     for path in [session.original_image, session.predicted_image]:
#         try:
#             if path and os.path.exists(path):
#                 os.remove(path)
#         except Exception:
#             pass

#     # מחיקה ב־S3 (Best-effort)
#     s3_del = {
#         "original_deleted": s3_delete_object(s3_original_key),
#         "predicted_deleted": s3_delete_object(s3_predicted_key),
#     }

#     # מחיקה בבסיס נתונים
#     deleted = queries.query_delete_prediction(db, uid)
#     if not deleted:
#         return {"detail": f"Prediction {uid} local/S3 cleaned, DB record not found to delete.", "s3": s3_del}

#     return {"detail": f"Prediction {uid} deleted successfully", "s3": s3_del}


# @router.get("/predictions/count")
# def get_count(db: Session = Depends(get_db)):
#     return {"count": queries.query_get_prediction_count_last_week(db)}


# @router.get("/labels")
# def get_labels(db: Session = Depends(get_db)):
#     return {"labels": queries.query_get_labels_from_last_week(db)}


# @router.get("/image/{image_type}/{filename}")
# def get_image(image_type: str, filename: str, s3_key: str | None = Query(None)):
#     """
#     מחזיר קובץ תמונה לוקאלי אם קיים. אם לא קיים ומסופק s3_key — ננסה להוריד זמנית מ־S3 ולהחזיר.
#     """
#     if image_type not in ("original", "predicted"):
#         raise HTTPException(status_code=400, detail="Invalid image type")
#     base_dir = {"original": UPLOAD_DIR, "predicted": PREDICTED_DIR}[image_type]
#     file_path = os.path.join(base_dir, filename)

#     if os.path.exists(file_path):
#         return FileResponse(file_path)

#     if s3_key:
#         temp_path = s3_download_to_temp(s3_key, suffix=os.path.splitext(filename)[1])
#         if temp_path and os.path.exists(temp_path):
#             return FileResponse(temp_path)

#     raise HTTPException(status_code=404, detail="Image not found")


# @router.get("/prediction/{uid}/image")
# def get_prediction_image(uid: str, request: Request, db: Session = Depends(get_db)):
#     """
#     מחזיר את התמונה המסומנת עבור uid.
#     תומך ב-content-negotiation בסיסי לפי Accept header, ובפולבק מ־S3 אם חסרה לוקאלית.
#     """
#     session = queries.query_get_prediction_by_uid(db, uid)
#     if not session:
#         raise HTTPException(status_code=404, detail="Prediction not found")

#     predicted_path = session.predicted_image
#     accept_header = request.headers.get("accept", "").lower()
#     prefer_png = ("image/png" in accept_header) or ("image/*" in accept_header)
#     prefer_jpg = ("image/jpeg" in accept_header) or ("image/jpg" in accept_header)

#     def _serve(path: str):
#         if prefer_png:
#             return FileResponse(path, media_type="image/png")
#         if prefer_jpg:
#             return FileResponse(path, media_type="image/jpeg")
#         # אם לא ביקשו ספציפי – נקבע לפי הסיומת
#         ext = os.path.splitext(path)[1].lower()
#         mt = "image/png" if ext == ".png" else "image/jpeg"
#         return FileResponse(path, media_type=mt)

#     if os.path.exists(predicted_path):
#         return _serve(predicted_path)

#     # פולבק: לנסות למשוך מ־S3
#     username = getattr(session, "username", None) or "anonymous"
#     ext = os.path.splitext(session.original_image or "")[1] or ".jpg"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"

#     temp_path = s3_download_to_temp(s3_predicted_key, suffix=ext)
#     if temp_path and os.path.exists(temp_path):
#         return _serve(temp_path)

#     raise HTTPException(status_code=404, detail="Predicted image file not found")


# @router.get("/stats")
# def get_stats(db: Session = Depends(get_db)):
#     return queries.query_get_prediction_stats(db)


# @router.get("/health")
# def health():
#     """Health check endpoint"""
#     return {"status": "ok!"}


# def to_dict(obj):
#     """המרת ORM לאובייקט dict בסיסי (לדיוג/מענה JSON)."""
#     if hasattr(obj, '__table__'):
#         return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
#     d = {}
#     for attr in dir(obj):
#         if not attr.startswith('_'):
#             val = getattr(obj, attr)
#             if not callable(val):
#                 d[attr] = val
#     return d


# def to_dict(obj):
#     """המרת ORM/אובייקט ל-dict בסיסי. אם כבר dict — החזר כמו שהוא."""
#     # ✅ אם כבר dict – החזר כמו שהוא (נדרש כדי לתמוך בפונקציות queries שמחזירות רשימות dict)
#     if isinstance(obj, dict):
#         return obj

#     if hasattr(obj, '__table__'):
#         return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
#     d = {}
#     for attr in dir(obj):
#         if not attr.startswith('_'):
#             val = getattr(obj, attr)
#             if not callable(val):
#                 d[attr] = val
#     return d










# # controllers.py
# from fastapi import APIRouter, UploadFile, File, Request, Depends, HTTPException, Query
# from fastapi.responses import FileResponse
# from sqlalchemy.orm import Session
# from PIL import Image
# import os, uuid, shutil, tempfile
# from ultralytics import YOLO
# import torch
# import queries
# from db import get_db
# from s3_utils import s3_download_to_path, s3_upload_file  # NEW
# # ...
# from urllib.parse import unquote

# router = APIRouter()
# torch.cuda.is_available = lambda: False  # בכדי למנוע אזהרות אם אין GPU
# UPLOAD_DIR = "uploads/original"
# PREDICTED_DIR = "uploads/predicted"
# os.makedirs(UPLOAD_DIR, exist_ok=True)

# model = YOLO("yolov8n.pt")  # או נתיב למודל מותאם אישית

# @router.post("/predict")
# def predict(
#     file: UploadFile | None = File(None),
#     request: Request = None,
#     db: Session = Depends(get_db),
#     img: str | None = Query(None, description="S3 object key to download (e.g., beatles.jpeg)")
# ):
#     uid = str(uuid.uuid4())
#     username = getattr(request.state, "username", None) or "anonymous"

#     # ✅ נקה key שמגיע בשאילתה
#     if img:
#         # הסר קידוד URL (כדי להפוך %0A ל-'\n'), ואז הסר רווחים/שורות
#         img = unquote(img).strip().replace("\r", "").replace("\n", "")
#         if not img:
#             raise HTTPException(status_code=400, detail="Empty 'img' key after trimming")

#         ext = os.path.splitext(img)[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         ok = s3_download_to_path(img, original_path)
#         if not ok:
#             raise HTTPException(status_code=400, detail=f"Failed to download '{img}' from S3")
    
#     else:
#         # העלאת קובץ רגילה
#         if not file:
#             raise HTTPException(status_code=400, detail="Provide either a file or ?img=<s3-key>")
#         ext = os.path.splitext(file.filename)[1] or ".jpg"
#         original_path = os.path.join(UPLOAD_DIR, uid + ext)
#         with open(original_path, "wb") as f:
#             shutil.copyfileobj(file.file, f)

#     predicted_path = os.path.join(PREDICTED_DIR, uid + ext)

#     # הרצת מודל
#     results = model(original_path, device="cpu")
#     Image.fromarray(results[0].plot()).save(predicted_path)

#     # שמירה בבסיס הנתונים (כפי שהיה)
#     queries.query_save_prediction_session(db, uid, original_path, predicted_path, username)

#     detected_labels = []
#     for box in results[0].boxes:
#         label = model.names[int(box.cls[0].item())]
#         score = float(box.conf[0])
#         bbox = box.xyxy[0].tolist()
#         queries.query_save_detection_object(db, uid, label, score, str(bbox))
#         detected_labels.append(label)

#     # --- העלאה ל-S3 (חדש) ---
#     # מבנה תיקיות מומלץ: <username>/original/<uid+ext>, <username>/predicted/<uid+ext>
#     s3_original_key = f"{username}/original/{uid}{ext}"
#     s3_predicted_key = f"{username}/predicted/{uid}{ext}"

#     # ExtraArgs אופציונלי: דוגמת מטא-דאטה
#     extra = {"Metadata": {"prediction_uid": uid, "user": username}}
#     _orig_up = s3_upload_file(original_path, s3_original_key, extra_args=extra)
#     _pred_up = s3_upload_file(predicted_path, s3_predicted_key, extra_args=extra)
#     # אם חשוב לך לטפל כשלים—אפשר להחזיר אזהרה בתגובה:
#     s3_status = {
#         "original_uploaded": _orig_up,
#         "predicted_uploaded": _pred_up,
#         "original_key": s3_original_key,
#         "predicted_key": s3_predicted_key
#     }
#     # ---------------------------

#     return {
#         "prediction_uid": uid,
#         "detection_count": len(results[0].boxes),
#         "labels": detected_labels,
#         "s3": s3_status
#     }

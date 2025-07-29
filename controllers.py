#controllers.py
from fastapi import APIRouter, UploadFile, File, Request, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image
import os, uuid, shutil
from ultralytics import YOLO
import torch
import queries
from db import get_db

router = APIRouter()

torch.cuda.is_available = lambda: False

UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREDICTED_DIR, exist_ok=True)

model = YOLO("yolov8n.pt")


@router.post("/predict")
def predict(file: UploadFile = File(...), request: Request = None, db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1]
    uid = str(uuid.uuid4())
    original_path = os.path.join(UPLOAD_DIR, uid + ext)
    predicted_path = os.path.join(PREDICTED_DIR, uid + ext)

    with open(original_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    results = model(original_path, device="cpu")
    Image.fromarray(results[0].plot()).save(predicted_path)

    username = getattr(request.state, "username", None)
    queries.query_save_prediction_session(db, uid, original_path, predicted_path, username)

    detected_labels = []
    for box in results[0].boxes:
        label = model.names[int(box.cls[0].item())]
        score = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        queries.query_save_detection_object(db, uid, label, score, str(bbox))
        detected_labels.append(label)

    return {
        "prediction_uid": uid,
        "detection_count": len(results[0].boxes),
        "labels": detected_labels
    }


@router.get("/prediction/{uid}")
def get_prediction_by_uid(uid: str, db: Session = Depends(get_db)):
    session = queries.query_get_prediction_by_uid(db, uid)
    if not session:
        raise HTTPException(status_code=404, detail="Prediction not found")
    objects = queries.query_get_objects_by_uid(db, uid)
    return {
        "uid": session.uid,
        "timestamp": session.timestamp.isoformat(),
        "original_image": session.original_image,
        "predicted_image": session.predicted_image,
        "detection_objects": [to_dict(obj) for obj in objects],
    }


@router.get("/predictions/label/{label}")
def get_predictions_by_label(label: str, db: Session = Depends(get_db)):
    return queries.query_get_predictions_by_label(db, label)


@router.get("/predictions/score/{min_score}")
def get_predictions_by_score(min_score: float, db: Session = Depends(get_db)):
    return queries.query_get_predictions_by_score(db, min_score)


@router.delete("/prediction/{uid}")
def delete_prediction(uid: str, db: Session = Depends(get_db)):
    prediction = queries.query_delete_prediction(db, uid)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    for path in [prediction.original_image, prediction.predicted_image]:
        if path and os.path.exists(path):
            os.remove(path)
    return {"detail": f"Prediction {uid} deleted successfully"}


@router.get("/predictions/count")
def get_count(db: Session = Depends(get_db)):
    return {"count": queries.query_get_prediction_count_last_week(db)}


@router.get("/labels")
def get_labels(db: Session = Depends(get_db)):
    return {"labels": queries.query_get_labels_from_last_week(db)}


@router.get("/image/{image_type}/{filename}")
def get_image(image_type: str, filename: str):
    if image_type not in ("original", "predicted"):
        raise HTTPException(status_code=400, detail="Invalid image type")
    base_dir = {"original": UPLOAD_DIR, "predicted": PREDICTED_DIR}[image_type]
    file_path = os.path.join(base_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)


@router.get("/prediction/{uid}/image")
def get_prediction_image(uid: str, request: Request, db: Session = Depends(get_db)):
    session = queries.query_get_prediction_by_uid(db, uid)
    if not session:
        raise HTTPException(status_code=404, detail="Prediction not found")

    predicted_path = session.predicted_image
    if not os.path.exists(predicted_path):
        raise HTTPException(status_code=404, detail="Predicted image file not found")

    accept_header = request.headers.get("accept", "").lower()
    if "image/png" in accept_header or "image/*" in accept_header:
        return FileResponse(predicted_path, media_type="image/png")
    if "image/jpeg" in accept_header or "image/jpg" in accept_header:
        return FileResponse(predicted_path, media_type="image/jpeg")
    raise HTTPException(status_code=406, detail="Not Acceptable")

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    stats = queries.query_get_prediction_stats(db)
    return stats

@router.get("/health")
def health():
    """
    Health check endpoint
    """
    return {"status": "ok!"}

def to_dict(obj):
    if hasattr(obj, '__table__'):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    d = {}
    for attr in dir(obj):
        if not attr.startswith('_'):
            val = getattr(obj, attr)
            if not callable(val):
                d[attr] = val
    return d

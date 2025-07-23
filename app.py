from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from ultralytics import YOLO
from PIL import Image
import os
import uuid
import shutil
from datetime import datetime, timedelta
import torch
from sqlalchemy.orm import Session

from db import get_db, Base, engine
from queries import (
    save_prediction_session,
    save_detection_object,
    get_prediction_by_uid,
    delete_prediction_by_uid,
    create_user_if_not_exists
)
from auth_middleware import basic_auth_middleware

# Disable GPU
torch.cuda.is_available = lambda: False

app = FastAPI()

app.middleware("http")(basic_auth_middleware)

UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
DB_PATH = "predictions.db"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREDICTED_DIR, exist_ok=True)

# Create tables in DB
Base.metadata.create_all(bind=engine)

model = YOLO("yolov8n.pt")

@app.post("/predict")
async def predict(file: UploadFile = File(...), request: Request = None, db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1]
    uid = str(uuid.uuid4())
    original_path = os.path.join(UPLOAD_DIR, uid + ext)
    predicted_path = os.path.join(PREDICTED_DIR, uid + ext)

    with open(original_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    results = model(original_path, device="cpu")

    annotated_frame = results[0].plot()
    annotated_image = Image.fromarray(annotated_frame)
    annotated_image.save(predicted_path)

    username = getattr(request.state, "username", None)
    # Create test user if needed (for demo purposes)
    if username:
        create_user_if_not_exists(db, username, "testpass")

    save_prediction_session(db, uid, original_path, predicted_path, username)

    detected_labels = []
    for box in results[0].boxes:
        label_idx = int(box.cls[0].item())
        label = model.names[label_idx]
        score = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        save_detection_object(db, uid, label, score, str(bbox))
        detected_labels.append(label)

    return {
        "prediction_uid": uid,
        "detection_count": len(results[0].boxes),
        "labels": detected_labels
    }

@app.get("/prediction/{uid}")
def get_prediction(uid: str, db: Session = Depends(get_db)):
    prediction = get_prediction_by_uid(db, uid)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    return {
        "uid": prediction.uid,
        "timestamp": prediction.timestamp,
        "original_image": prediction.original_image,
        "predicted_image": prediction.predicted_image,
        "username": prediction.username
    }

@app.delete("/prediction/{uid}")
def delete_prediction(uid: str, db: Session = Depends(get_db)):
    success = delete_prediction_by_uid(db, uid)
    if not success:
        raise HTTPException(status_code=404, detail="Prediction not found")

    # Also delete files (you may want to do it in queries.py as well)
    # Example code:
    # os.remove(prediction.original_image), etc.

    return {"detail": f"Prediction {uid} deleted successfully"}

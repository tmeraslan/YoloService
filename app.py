# app.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from ultralytics import YOLO
from PIL import Image
import os, uuid, shutil
from datetime import datetime, timedelta
from auth_middleware import basic_auth_middleware
from sqlalchemy.orm import Session
import queries
from db import get_db
import torch
from fastapi.responses import FileResponse
from fastapi import HTTPException
from db import get_db, engine, Base



DB_PATH = "predictions.db"

# Create the tables if they do not exist.
Base.metadata.create_all(bind=engine)
# get_db()

# Disable GPU
torch.cuda.is_available = lambda: False

app = FastAPI()
app.middleware("http")(basic_auth_middleware())

UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
model = YOLO("yolov8n.pt")


@app.post("/predict")
def predict(
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db)
):
    ext = os.path.splitext(file.filename)[1]
    uid = str(uuid.uuid4())
    original_path = os.path.join(UPLOAD_DIR, uid + ext)
    predicted_path = os.path.join(PREDICTED_DIR, uid + ext)

    with open(original_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    results = model(original_path, device="cpu")
    annotated_frame = results[0].plot()
    Image.fromarray(annotated_frame).save(predicted_path)

    username = getattr(request.state, "username", None)
    queries.query_save_prediction_session(db, uid, original_path, predicted_path, username)

    detected_labels = []
    for box in results[0].boxes:
        label = model.names[int(box.cls[0].item())]
        score = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        queries.query_save_detection_object(db, uid, label, score, str(bbox))
        detected_labels.append(label)

    return {"prediction_uid": uid, "detection_count": len(results[0].boxes), "labels": detected_labels}


@app.get("/prediction/{uid}")
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



@app.get("/predictions/label/{label}")
def get_predictions_by_label(label: str, db: Session = Depends(get_db)):
    return queries.query_get_predictions_by_label(db, label)


@app.get("/predictions/score/{min_score}")
def get_predictions_by_score(min_score: float, db: Session = Depends(get_db)):
    return queries.query_get_predictions_by_score(db, min_score)


@app.delete("/prediction/{uid}")
def delete_prediction(uid: str, db: Session = Depends(get_db)):
    prediction = queries.query_delete_prediction(db, uid)
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    files = [prediction.original_image, prediction.predicted_image]
    for path in files:
        if path and os.path.exists(path):
            os.remove(path)
    return {"detail": f"Prediction {uid} deleted successfully"}


@app.get("/predictions/count")
def get_count(db: Session = Depends(get_db)):
    count = queries.query_get_prediction_count_last_week(db)
    return {"count": count}


@app.get("/labels")
def get_labels(db: Session = Depends(get_db)):
    labels = queries.query_get_labels_from_last_week(db)
    return {"labels": labels}


@app.get("/health")
def health():
    return {"status": "ok!"}



@app.get("/image/{image_type}/{filename}")
def get_image(image_type: str, filename: str):
    if image_type not in ("original", "predicted"):
        raise HTTPException(status_code=400, detail="Invalid image type")

    base_dir = {
        "original": UPLOAD_DIR,
        "predicted": PREDICTED_DIR,
    }[image_type]

    file_path = os.path.join(base_dir, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(file_path)

from fastapi import Request

@app.get("/prediction/{uid}/image")
def get_prediction_image(uid: str, request: Request, db: Session = Depends(get_db)):
    session = queries.query_get_prediction_by_uid(db, uid)
    if not session:
        raise HTTPException(status_code=404, detail="Prediction not found")

    accept_header = request.headers.get("accept", "").lower()

    # Let's get the path of the predicted file.
    predicted_path = session.predicted_image
    if not os.path.exists(predicted_path):
        raise HTTPException(status_code=404, detail="Predicted image file not found")

    # Check if the image type is suitable for Accept
    if "image/png" in accept_header or "image/*" in accept_header:
       
        return FileResponse(predicted_path, media_type="image/png")

    elif "image/jpeg" in accept_header or "image/jpg" in accept_header:
       
        return FileResponse(predicted_path, media_type="image/jpeg")

    else:
        raise HTTPException(status_code=406, detail="Not Acceptable")


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    return queries.query_get_prediction_stats(db)

def to_dict(obj):
    """
    Convert an SQLAlchemy model instance or a generic Python object
    into a valid dictionary.

    This helper function inspects the given object:
    - If the object is a SQLAlchemy model instance (has a __table__ attribute),
      it extracts all columns and their values into a dictionary.
    - Otherwise, it attempts to extract all public, non-callable attributes
      from the object and return them in a dictionary.

    Parameters:
        obj (Any): The object to convert.

    Returns:
        dict: A dictionary representation of the object.
    """
    # Check if this is a SQLAlchemy model (has a __table__ attribute)
    if hasattr(obj, '__table__'):
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    else:
        # Fallback: gather all public, non-callable attributes
        d = {}
        for attr in dir(obj):
            if not attr.startswith('_'):  # ignore private/protected attributes
                value = getattr(obj, attr)
                if not callable(value):  # ignore methods
                    d[attr] = value
        return d




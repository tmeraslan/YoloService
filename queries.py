from sqlalchemy.orm import Session
from models import PredictionSession, DetectionObject, User
from datetime import datetime
from typing import Optional

def get_user(db: Session, username: str, password: str) -> Optional[User]:
    return db.query(User).filter(User.username == username, User.password == password).first()

def create_user_if_not_exists(db: Session, username: str, password: str):
    user = get_user(db, username, password)
    if not user:
        user = User(username=username, password=password)
        db.add(user)
        db.commit()

def save_prediction_session(db: Session, uid: str, original_image: str, predicted_image: str, username: Optional[str]):
    session = PredictionSession(
        uid=uid,
        original_image=original_image,
        predicted_image=predicted_image,
        username=username
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def save_detection_object(db: Session, prediction_uid: str, label: str, score: float, box: str):
    obj = DetectionObject(
        prediction_uid=prediction_uid,
        label=label,
        score=score,
        box=box
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_prediction_by_uid(db: Session, uid: str):
    return db.query(PredictionSession).filter(PredictionSession.uid == uid).first()

def delete_prediction_by_uid(db: Session, uid: str):
    prediction = get_prediction_by_uid(db, uid)
    if not prediction:
        return False

    # Delete detection objects first (cascade can be used alternatively)
    db.query(DetectionObject).filter(DetectionObject.prediction_uid == uid).delete()
    db.delete(prediction)
    db.commit()
    return True

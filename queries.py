
#queries.py
from sqlalchemy.orm import Session
from models import PredictionSession, DetectionObject,User
from datetime import datetime, timedelta

def ensure_user(db: Session, username: str):
    if not username:
        return
    user = db.get(User, username)
    if user is None:
        db.add(User(username=username, password="")) 
        db.commit()

def query_save_prediction_session(db: Session, uid: str, original_image: str, predicted_image: str, username=None):
    ensure_user(db, username)
    session = PredictionSession(
        uid=uid,
        original_image=original_image,
        predicted_image=predicted_image,
        username=username,
        timestamp=datetime.utcnow()
    )
    db.add(session)
    db.commit()

def query_save_detection_object(db: Session, prediction_uid: str, label: str, score: float, box: str):
    obj = DetectionObject(prediction_uid=prediction_uid, label=label, score=score, box=str(box))
    db.add(obj)
    db.commit()

def query_get_prediction_by_uid(db: Session, uid: str):
    return db.query(PredictionSession).filter_by(uid=uid).first()

def query_get_predictions_by_label(db: Session, label: str):
    rows = (
        db.query(PredictionSession.uid, PredictionSession.timestamp)
        .join(DetectionObject, DetectionObject.prediction_uid == PredictionSession.uid)
        .filter(DetectionObject.label == label)
        .distinct()
        .all()
    )
    return [{"uid": uid, "timestamp": ts.isoformat() if ts else None} for uid, ts in rows]

def query_get_predictions_by_score(db: Session, min_score: float):
    rows = (
        db.query(PredictionSession.uid, PredictionSession.timestamp)
        .join(DetectionObject, DetectionObject.prediction_uid == PredictionSession.uid)
        .filter(DetectionObject.score >= min_score)
        .distinct()
        .all()
    )
    return [{"uid": uid, "timestamp": ts.isoformat() if ts else None} for uid, ts in rows]

def query_get_prediction_count_last_week(db: Session):
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    return db.query(PredictionSession).filter(PredictionSession.timestamp >= one_week_ago).count()

def query_get_labels_from_last_week(db: Session):
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    rows = (
        db.query(DetectionObject.label)
        .join(PredictionSession, DetectionObject.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.timestamp >= one_week_ago)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]

def query_delete_prediction(db: Session, uid: str):
    prediction = db.query(PredictionSession).filter_by(uid=uid).first()
    if prediction:
        db.query(DetectionObject).filter(DetectionObject.prediction_uid == uid).delete()
        db.delete(prediction)
        db.commit()
        return prediction
    return None

def query_get_prediction_stats(db: Session):
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    total = db.query(PredictionSession).filter(PredictionSession.timestamp >= one_week_ago).count()

    scores = (
        db.query(DetectionObject.score)
        .join(PredictionSession, DetectionObject.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.timestamp >= one_week_ago)
        .all()
    )
    avg_val = round(sum(s[0] for s in scores if s[0] is not None) / len(scores), 2) if scores else 0.0

    label_counts = {}
    labels = (
        db.query(DetectionObject.label)
        .join(PredictionSession, DetectionObject.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.timestamp >= one_week_ago)
        .all()
    )
    for l in labels:
        label_counts[l[0]] = label_counts.get(l[0], 0) + 1

    return {
        "total_predictions": total,
        "average_confidence_score": avg_val,
        "most_common_labels": label_counts,
    }

def query_get_objects_by_uid(db: Session, uid: str):
    return db.query(DetectionObject).filter(DetectionObject.prediction_uid == uid).all()




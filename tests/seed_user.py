# tests/seed_user.py
from db import SessionLocal
from models import User

def seed_test_user():
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(username="testuser").first():
            db.add(User(username="testuser", password="testpass"))
            db.commit()
    finally:
        db.close()

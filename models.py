
# models.py
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from db import Base   

class User(Base):
    __tablename__ = 'users'
    username = Column(String, primary_key=True)
    password = Column(String, nullable=False)
    sessions = relationship("PredictionSession", back_populates="user")

class PredictionSession(Base):
    __tablename__ = 'prediction_sessions'
    uid = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    original_image = Column(String)
    predicted_image = Column(String)
    username = Column(String, ForeignKey('users.username'))
    user = relationship("User", back_populates="sessions")
    objects = relationship("DetectionObject", back_populates="session")

class DetectionObject(Base):
    __tablename__ = 'detection_objects'
    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_uid = Column(String, ForeignKey('prediction_sessions.uid'))
    label = Column(String)
    score = Column(Float)
    box = Column(String)
    session = relationship("PredictionSession", back_populates="objects")

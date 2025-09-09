
# db.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL","sqlite:///./predictions.db")  # קודם מהסביבה
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").lower()



engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()











# # db.py


# import os
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, declarative_base

# DB_BACKEND = os.getenv("DB_BACKEND", "sqlite")

# if DB_BACKEND == "postgres":
#     print("using posgress DATABASE")
#     DATABASE_URL = "postgresql://user:pass@localhost:5432/predictions"   
# else:
#     DATABASE_URL = "sqlite:///./predictions.db"

# engine = create_engine(
#     DATABASE_URL,
#     connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
# )

# SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
# Base = declarative_base()

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

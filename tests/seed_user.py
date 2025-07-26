# # seed_user.py
# from db import engine, Base, SessionLocal
# from models import User

# def seed_test_user():

#     Base.metadata.create_all(bind=engine)

#     db = SessionLocal()
#     try:
#         if not db.query(User).filter_by(username="testuser").first():
       
#             user = User(username="testuser", password="testpass")
#             db.add(user)
#             db.commit()
#     finally:
#         db.close()
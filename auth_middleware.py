# auth_middleware.py
import base64
from fastapi import Request
from fastapi.responses import JSONResponse
from db import SessionLocal
from models import User

def verify_user(username: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username, password=password).first()
        return user is not None
    finally:
        db.close()

def basic_auth_middleware():
    async def middleware(request: Request, call_next):
        open_paths = ["/health"]

        # open endpoints
        if request.url.path in open_paths:
            return await call_next(request)

        # POST /predict - optional auth
        if request.url.path == "/predict" and request.method.upper() == "POST":
            auth = request.headers.get("Authorization")
            if auth:
                try:
                    encoded = auth.split(" ")[1]
                    decoded = base64.b64decode(encoded).decode("utf-8")
                    username, password = decoded.split(":", 1)
                except Exception:
                    return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
                if not verify_user(username, password):
                    return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
                request.state.username = username
            else:
                request.state.username = None
            return await call_next(request)

        # all other routes require auth
        auth = request.headers.get("Authorization")
        if not auth:
            return JSONResponse(status_code=401, content={"detail": "Missing credentials"})
        try:
            encoded = auth.split(" ")[1]
            decoded = base64.b64decode(encoded).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
        if not verify_user(username, password):
            return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
        request.state.username = username
        return await call_next(request)

    return middleware

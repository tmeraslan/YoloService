import base64
import sqlite3
from fastapi import Request
from fastapi.responses import JSONResponse

DB_PATH = "predictions.db"

def verify_user(auth_header: str):
    if not auth_header or not auth_header.startswith("Basic "):
        return None
    try:
        encoded = auth_header.split(" ")[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return None
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        if row:
            return username
    return None

def basic_auth_middleware():
    async def middleware(request: Request, call_next):
        #  Define paths that are open to everyone
        open_paths = ["/health"]

        if request.url.path in open_paths:
            # No authentication required
            return await call_next(request)

        # /predict POST route - optional authentication
        if request.url.path == "/predict" and request.method.upper() == "POST":
            auth = request.headers.get("Authorization")
            if auth:
                username = verify_user(auth)
                if username is None:
                    return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
                request.state.username = username
            else:
                # If no authentication, still allow access
                request.state.username = None
            return await call_next(request)

        # All other routes require authentication
        auth = request.headers.get("Authorization")
        username = verify_user(auth)
        if username is None:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing credentials"})
        request.state.username = username
        return await call_next(request)

    return middleware


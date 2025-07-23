import base64
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from db import get_db
from queries import get_user

async def basic_auth_middleware(request: Request, call_next):
    open_paths = ["/health"]
    if request.url.path in open_paths:
        return await call_next(request)

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Basic "):
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing credentials"})

    try:
        encoded = auth.split(" ")[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid authentication header"})

    # Get DB session
    async for db in get_db():
        user = get_user(db, username, password)
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})
        request.state.username = username
        break

    response = await call_next(request)
    return response

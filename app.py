# app.py

from fastapi import FastAPI
from db import Base, engine
from auth_middleware import basic_auth_middleware
import controllers  


Base.metadata.create_all(bind=engine)

app = FastAPI()
app.middleware("http")(basic_auth_middleware())

app.include_router(controllers.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)

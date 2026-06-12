import os

from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from app.config import database_mode, load_env_file
from app.routes.events import router as events_router
from app.routes.public import router as public_router
from app.services.rekognition import using_real_rekognition
from app.services.s3 import using_real_s3

load_env_file()

app = FastAPI()

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Message(BaseModel):
    text: str

@app.get("/health")
def health():
    return {
        "ok": True,
        "database": database_mode(),
        "s3": "real" if using_real_s3() else "mock",
        "rekognition": "real" if using_real_rekognition() else "mock",
    }

@app.post("/echo")
def echo_message(msg: Message):
    return {
        "original": msg.text,
        "length": len(msg.text),
        "upper": msg.text.upper()
    }

app.include_router(events_router)
app.include_router(public_router)

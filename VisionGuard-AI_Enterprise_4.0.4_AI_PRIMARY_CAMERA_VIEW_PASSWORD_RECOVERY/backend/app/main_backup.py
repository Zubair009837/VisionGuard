from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, SessionLocal
from .models import Base, Camera

app = FastAPI(title="VisionGuard AI API")

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "VisionGuard AI Backend Running"}


@app.get("/health")
def health():
    return {"status": "UP"}


@app.get("/dashboard")
def dashboard():

    db = SessionLocal()

    total = db.query(Camera).count()
    online = db.query(Camera).filter(Camera.status == "Online").count()
    offline = db.query(Camera).filter(Camera.status == "Offline").count()

    return {
        "total": total,
        "online": online,
        "offline": offline,
        "nvr": 1,
    }


@app.get("/cameras")
def cameras():

    db = SessionLocal()

    return db.query(Camera).all()
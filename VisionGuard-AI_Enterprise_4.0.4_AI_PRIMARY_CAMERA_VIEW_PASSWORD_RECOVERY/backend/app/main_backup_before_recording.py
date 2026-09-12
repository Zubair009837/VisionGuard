from .video_monitor import start_video_monitor
from .hikvision_event_listener import start_listener
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Camera
from .schemas import CameraCreate, CameraResponse
from . import crud
from .config import NVRS

import requests
from requests.auth import HTTPDigestAuth

app = FastAPI(title="VisionGuard AI")

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# Startup
# ==========================================================

@app.on_event("startup")
def startup():

    print("=" * 60)
    print("VisionGuard AI Starting...")
    print("=" * 60)

    # Existing Video Monitor
    start_video_monitor()

    # Hikvision Event Listener
    start_listener()

    print("Video Monitor Started Successfully")
    print("Video Loss Listener Started Successfully")

@app.get("/")
def home():
    return {
        "message": "VisionGuard AI Backend Running"
    }


@app.get("/health")
def health():
    return {
        "status": "UP"
    }


@app.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):

    cameras = crud.get_cameras(db)

    total = len(cameras)
    online = len([c for c in cameras if c["status"] == "Online"])
    offline = total - online

    return {
        "total": total,
        "online": online,
        "offline": offline,
        "nvr": len(NVRS)
    }


@app.get("/cameras", response_model=list[CameraResponse])
def get_cameras(db: Session = Depends(get_db)):
    return crud.get_cameras(db)


@app.post("/cameras", response_model=CameraResponse)
def create_camera(camera: CameraCreate, db: Session = Depends(get_db)):
    return crud.create_camera(db, camera)


@app.get("/nvr/status")
def nvr_status():

    result = []

    for nvr in NVRS:

        try:

            response = requests.get(
                f"http://{nvr['ip']}:{nvr['port']}",
                auth=HTTPDigestAuth(
                    nvr["username"],
                    nvr["password"]
                ),
                timeout=5
            )

            if response.status_code in [200, 401]:
                status = "ONLINE"
            else:
                status = "OFFLINE"

        except Exception:
            status = "OFFLINE"

        result.append({
            "name": nvr["name"],
            "ip": nvr["ip"],
            "port": nvr["port"],
            "status": status
        })

    return result


@app.get("/nvr/raw", response_class=PlainTextResponse)
def nvr_raw():

    output = ""

    for nvr in NVRS:

        output += f"\n========== {nvr['name']} ==========\n"

        try:

            response = requests.get(
                f"http://{nvr['ip']}:{nvr['port']}/ISAPI/ContentMgmt/InputProxy/channels",
                auth=HTTPDigestAuth(
                    nvr["username"],
                    nvr["password"]
                ),
                timeout=10
            )

            output += response.text

        except Exception as e:

            output += str(e)

    return output
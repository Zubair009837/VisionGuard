# ==========================================================
# VisionGuard AI - Main FastAPI Application
# Tata 1mg - NVR Security Operations Center
# ==========================================================


# ==========================================================
# STANDARD LIBRARIES
# ==========================================================

import time
import os
import re
import json
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import base64
import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

from typing import List


# ==========================================================
# VIDEO MONITOR
# ==========================================================

from .video_monitor import (
    start_video_monitor,
    rtsp_url,
)


# ==========================================================
# HIKVISION EVENT LISTENER
# ==========================================================

from .hikvision_event_listener import (
    start_listener,
)


# ==========================================================
# RECORDING MONITOR
# ==========================================================

from .recording_monitor import (
    start_recording_monitor,
    get_recording_loss_history,
    get_active_recording_losses,
)


# ==========================================================
# CAMERA ANGLE MONITOR
# ==========================================================

from .camera_angle_monitor import (
    start_camera_angle_monitor,
    stop_camera_angle_monitor,
    get_camera_angle_status,
    get_camera_angle_summary,
)


# ==========================================================
# FASTAPI
# ==========================================================

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
)


# ==========================================================
# CORS
# ==========================================================

from fastapi.middleware.cors import (
    CORSMiddleware
)


# ==========================================================
# RESPONSES
# ==========================================================

from fastapi.responses import (
    PlainTextResponse,
    StreamingResponse,
    Response,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# ==========================================================
# DATABASE
# ==========================================================

from sqlalchemy.orm import Session

from .database import (
    Base,
    engine,
    get_db,
)


# ==========================================================
# SCHEMAS
# ==========================================================

from .schemas import (
    CameraCreate,
    CameraResponse,
)


# ==========================================================
# CRUD
# ==========================================================

from . import crud


# ==========================================================
# CONFIG
# ==========================================================

from .config import (NVRS, DAILY_HEALTH_REPORT_ENABLED, DAILY_HEALTH_REPORT_HOUR, DAILY_HEALTH_REPORT_MINUTE, APP_PASSWORD_RESET_EMAIL, APP_PASSWORD_RESET_TTL_MINUTES, APP_PASSWORD_RESET_COOLDOWN_SECONDS)
from .email_service import send_daily_health_report_email, send_password_recovery_otp, send_hikvision_recovery_qr, send_app_password_reset_email
from .password_recovery import (
    RECOVERY_EMAIL,
    HIKVISION_RECOVERY_EMAIL,
    create_recovery_session,
    mark_qr_submitted,
    record_hikvision_code,
    get_session,
)

from .storage_monitor import storage_snapshot
from .nvr_health import get_health, get_health_history, get_health_insights, start_health_monitor
from .nvr_outage_monitor import start_nvr_outage_monitor, stop_nvr_outage_monitor
from .whatsapp_service import get_whatsapp_config, save_whatsapp_config, send_whatsapp_alert
from .alert_manager import add_alert, HISTORY_FILE
from .enterprise_features import (
    nvr_users,
    get_camera_movement_history,
    camera_movement_summary,
    update_camera,
    MOVEMENT_FILE,
    get_camera_assignment_timeline,
)


# ==========================================================
# REQUESTS
# ==========================================================

import requests

from requests.auth import HTTPDigestAuth


# ==========================================================
# OPENCV
# ==========================================================

import cv2


# ==========================================================
# APPLICATION
# ==========================================================

from .nvr_control_center import router as nvr_control_router, start_time_monitor
from .bulk_camera_config import apply_bulk as apply_bulk_camera_encoding
from .nvr_audit import audit_all as audit_all_nvrs
from .predictive_risk import risk_snapshot
from .password_recovery import supported_recovery_workflow


_DAILY_REPORT_STARTED = False
_DAILY_REPORT_LAST_SENT = ""
_PREDICTIVE_THREAD_STARTED = False
_PREDICTIVE_LAST_ALERT = {}



def _daily_health_report_worker():
    """
    Enterprise daily CCTV verification.

    IMPORTANT:
    - Camera/NVR counts come from the same cache used by the dashboard.
    - NVR clock verification is independent from NVR online/offline status.
    - A failed clock read is NOT treated as an NVR being offline.
    - The report is sent only after the discovery cache is ready.
    """
    global _DAILY_REPORT_LAST_SENT

    ist = timezone(timedelta(hours=5, minutes=30))

    while True:
        try:
            now = datetime.now(ist)
            key = now.strftime("%Y-%m-%d")

            due = (
                now.hour > DAILY_HEALTH_REPORT_HOUR
                or (
                    now.hour == DAILY_HEALTH_REPORT_HOUR
                    and now.minute >= DAILY_HEALTH_REPORT_MINUTE
                )
            )

            if due and _DAILY_REPORT_LAST_SENT != key:

                # --------------------------------------------------
                # CAMERA DISCOVERY / CACHE READINESS
                # --------------------------------------------------
                snapshot = crud.get_dashboard_snapshot() or {}
                cache_ready = bool(snapshot.get("cache_ready", False))

                cameras_total = int(snapshot.get("total", 0) or 0)
                cameras_online = int(snapshot.get("online", 0) or 0)
                cameras_offline = int(
                    snapshot.get(
                        "offline",
                        max(0, cameras_total - cameras_online),
                    ) or 0
                )

                # Never send a false 0-camera report while discovery is
                # still starting. Retry on the next 30-second cycle.
                if not cache_ready or cameras_total <= 0:
                    print(
                        "[DAILY REPORT] Camera discovery/cache is not ready "
                        f"(ready={cache_ready}, total={cameras_total}). "
                        "Waiting before sending report."
                    )
                    time.sleep(30)
                    continue

                # --------------------------------------------------
                # NVR ONLINE/OFFLINE
                # --------------------------------------------------
                # Connectivity is verified independently from the NVR
                # health telemetry and independently from clock checks.
                # A valid HTTP response (including 401/403/400) means the
                # device is reachable. We only call it OFFLINE when the
                # TCP/HTTP connection itself cannot be established.
                def _check_nvr_reachable(nvr):
                    try:
                        url = (
                            f"http://{nvr['ip']}:"
                            f"{nvr.get('port', 80)}"
                        )

                        response = requests.get(
                            url,
                            auth=HTTPDigestAuth(
                                nvr["username"],
                                nvr["password"],
                            ),
                            timeout=5,
                        )

                        return True, response.status_code

                    except Exception as exc:
                        return False, str(exc)

                nvr_status_rows = []

                for nvr in NVRS:
                    reachable, detail = _check_nvr_reachable(nvr)

                    nvr_status_rows.append({
                        "name": nvr.get("name", "Unknown NVR"),
                        "ip": nvr.get("ip", ""),
                        "port": nvr.get("port", ""),
                        "status": "ONLINE" if reachable else "OFFLINE",
                        "detail": detail,
                    })

                nvr_total = len(nvr_status_rows)
                nvr_online = sum(
                    1
                    for item in nvr_status_rows
                    if item["status"] == "ONLINE"
                )
                nvr_offline = max(
                    0,
                    nvr_total - nvr_online,
                )

                # --------------------------------------------------
                # IP CONFLICT

                # --------------------------------------------------
                try:
                    from .ip_conflict_checker import (
                        get_conflict_count,
                        get_conflict_ips,
                    )

                    ip_conflict_count = int(
                        get_conflict_count() or 0
                    )
                    ip_conflict_ips = list(
                        get_conflict_ips() or []
                    )
                except Exception as exc:
                    print(
                        f"[DAILY REPORT] IP conflict check failed: {exc}"
                    )
                    ip_conflict_count = 0
                    ip_conflict_ips = []

                # --------------------------------------------------
                # RECORDING LOSS
                # --------------------------------------------------
                try:
                    recording_losses = (
                        get_active_recording_losses() or []
                    )
                except Exception as exc:
                    print(
                        f"[DAILY REPORT] Recording check failed: {exc}"
                    )
                    recording_losses = []

                recording_loss_count = len(recording_losses)
                recording_ok = recording_loss_count == 0

                # --------------------------------------------------
                # STORAGE / HDD
                # --------------------------------------------------
                try:
                    storage = storage_snapshot(force=True) or {}
                    storage_rows = storage.get("data", []) or []

                    storage_ok = bool(storage_rows)

                    for item in storage_rows:
                        if (
                            str(item.get("status", "")).upper()
                            != "ONLINE"
                            or item.get("error")
                        ):
                            storage_ok = False

                        for hdd in item.get("hdds") or []:
                            hdd_status = str(
                                hdd.get("status", "")
                            ).strip().lower()

                            if hdd_status not in {
                                "ok",
                                "normal",
                                "healthy",
                                "online",
                                "active",
                                "ready",
                            }:
                                storage_ok = False

                except Exception as exc:
                    print(
                        f"[DAILY REPORT] Storage check failed: {exc}"
                    )
                    storage_rows = []
                    storage_ok = False

                # --------------------------------------------------
                # NVR CLOCK CHECK
                # --------------------------------------------------
                # check_one() uses the exact configured NVR HTTP port.
                # Its parser has been hardened in nvr_control_center.py.
                time_results = []

                try:
                    from .nvr_control_center import check_one as check_nvr_time

                    for nvr in NVRS:
                        try:
                            result = check_nvr_time(
                                nvr,
                                send_alert=False,
                            ) or {}

                            # Ensure identifying fields are always present.
                            result.setdefault(
                                "nvr",
                                nvr.get("name", "Unknown NVR"),
                            )
                            result.setdefault(
                                "ip",
                                nvr.get("ip", ""),
                            )
                            result.setdefault(
                                "port",
                                nvr.get("port", ""),
                            )

                            time_results.append(result)

                        except Exception as exc:
                            time_results.append({
                                "nvr": nvr.get("name", "Unknown NVR"),
                                "ip": nvr.get("ip", ""),
                                "port": nvr.get("port", ""),
                                "time_drift": None,
                                "difference_seconds": None,
                                "error": f"Clock check failed: {exc}",
                            })

                except Exception as exc:
                    print(
                        f"[DAILY REPORT] Clock verification unavailable: {exc}"
                    )

                time_drift_count = sum(
                    1
                    for item in time_results
                    if item.get("time_drift") is True
                )

                time_check_failed_count = sum(
                    1
                    for item in time_results
                    if item.get("time_drift") is None
                    or item.get("error")
                )

                # --------------------------------------------------
                # CAMERA ANGLE
                # --------------------------------------------------
                try:
                    angle_summary = (
                        get_camera_angle_summary() or {}
                    )
                    angle_enabled = bool(
                        angle_summary.get("enabled", False)
                    )
                    angle_changed = int(
                        angle_summary.get("changed", 0) or 0
                    )
                except Exception as exc:
                    print(
                        f"[DAILY REPORT] Angle check failed: {exc}"
                    )
                    angle_enabled = False
                    angle_changed = 0

                # --------------------------------------------------
                # OVERALL STATUS
                # --------------------------------------------------
                issues = []

                if cameras_offline > 0:
                    issues.append(
                        f"{cameras_offline} camera(s) offline"
                    )

                if nvr_offline > 0:
                    issues.append(
                        f"{nvr_offline} NVR(s) offline"
                    )

                if ip_conflict_count > 0:
                    issues.append(
                        f"{ip_conflict_count} IP conflict(s) detected"
                    )

                if recording_loss_count > 0:
                    issues.append(
                        f"{recording_loss_count} active recording loss(es)"
                    )

                if not storage_ok:
                    issues.append(
                        "Storage/HDD health requires attention"
                    )

                if time_drift_count > 0:
                    issues.append(
                        f"{time_drift_count} NVR clock(s) outside the allowed tolerance"
                    )

                if time_check_failed_count > 0:
                    issues.append(
                        f"{time_check_failed_count} NVR clock check(s) could not be completed"
                    )

                if angle_enabled and angle_changed > 0:
                    issues.append(
                        f"{angle_changed} camera angle change(s) detected"
                    )

                all_normal = (
                    cameras_total > 0
                    and cameras_offline == 0
                    and nvr_total > 0
                    and nvr_online == nvr_total
                    and ip_conflict_count == 0
                    and recording_loss_count == 0
                    and storage_ok
                    and time_drift_count == 0
                    and time_check_failed_count == 0
                    and (not angle_enabled or angle_changed == 0)
                )

                # --------------------------------------------------
                # SEND
                # --------------------------------------------------
                sent = send_daily_health_report_email(
                    all_normal=all_normal,

                    cameras_online=cameras_online,
                    cameras_total=cameras_total,

                    nvrs_online=nvr_online,
                    nvrs_total=nvr_total,

                    recording_ok=recording_ok,
                    storage_ok=storage_ok,

                    ip_conflict_count=ip_conflict_count,
                    ip_conflict_ips=ip_conflict_ips,

                    recording_loss_count=recording_loss_count,
                    recording_losses=recording_losses,

                    time_results=time_results,
                    time_drift_count=time_drift_count,
                    time_check_failed_count=time_check_failed_count,

                    angle_enabled=angle_enabled,
                    angle_changed=angle_changed,

                    issues=issues,

                    report_time=now.strftime(
                        "%d %b %Y, %I:%M %p IST"
                    ),
                )

                # Mark only after SMTP successfully accepted the email.
                if sent:
                    _DAILY_REPORT_LAST_SENT = key
                    print(
                        f"[DAILY REPORT] Daily report sent successfully: {key}"
                    )
                else:
                    print(
                        "[DAILY REPORT] Email was not sent. "
                        "Will retry."
                    )

        except Exception as exc:
            print(
                f"[DAILY REPORT] worker error: {exc}"
            )

        time.sleep(30)

def start_daily_health_report():
    global _DAILY_REPORT_STARTED
    if not DAILY_HEALTH_REPORT_ENABLED or _DAILY_REPORT_STARTED:
        return
    _DAILY_REPORT_STARTED = True
    thread = threading.Thread(target=_daily_health_report_worker, name="VisionGuard-Daily-Health-Report", daemon=True)
    thread.start()
    print(f"✓ Daily CCTV Health Report scheduled for {DAILY_HEALTH_REPORT_HOUR:02d}:{DAILY_HEALTH_REPORT_MINUTE:02d} IST")


def _predictive_risk_worker():
    """Early-warning monitor. It reports measurable risk signals; it does not claim to predict an exact future failure date."""
    import time as _time
    from .config import PREDICTIVE_RISK_ENABLED, PREDICTIVE_RISK_EMAIL_ENABLED, PREDICTIVE_RISK_CHECK_INTERVAL_SECONDS, PREDICTIVE_RISK_HIGH_SCORE
    from .email_service import send_nvr_health_email
    while True:
        try:
            if PREDICTIVE_RISK_ENABLED:
                snap = risk_snapshot()
                today = datetime.now().strftime('%Y-%m-%d')
                if PREDICTIVE_RISK_EMAIL_ENABLED:
                    for item in snap.get('items', []):
                        if int(item.get('score', 0)) >= int(PREDICTIVE_RISK_HIGH_SCORE) and _PREDICTIVE_LAST_ALERT.get(item.get('nvr')) != today:
                            send_nvr_health_email(nvr=item.get('nvr','NVR'), ip=item.get('ip',''), severity='WARNING', title='EARLY WARNING - NVR RISK', description='VisionGuard detected repeated measurable signals that increase the risk of a future service/recording issue. This is an early-warning assessment, not a guaranteed future-failure prediction.', metric=f"Risk score: {item.get('score')}/100; Signals: {'; '.join(item.get('reasons') or [])}", threshold=f"High risk >= {PREDICTIVE_RISK_HIGH_SCORE}", event_time=datetime.now().strftime('%d-%m-%Y %I:%M:%S %p'))
                            _PREDICTIVE_LAST_ALERT[item.get('nvr')] = today
        except Exception as exc:
            print('[PREDICTIVE] worker error:', exc)
        _time.sleep(900)

app = FastAPI(
    title="VisionGuard AI",
    version="3.9.5 Enterprise Health Intelligence",
)

app.include_router(nvr_control_router)

AUDIT_FILE = os.path.join(os.path.dirname(__file__), "audit_log.json")
APP_USERS_FILE = os.path.join(os.path.dirname(__file__), "app_users.json")
APP_AUTH_SECRET = os.getenv("VISIONGUARD_APP_SECRET", "VisionGuard-AI-Local-Auth-3.9.5")
APP_TOKEN_TTL = 12 * 60 * 60
APP_PBKDF2_ROUNDS = 200_000
_bearer = HTTPBearer(auto_error=False)

# One-time application password reset tokens. Only a SHA-256 digest of the
# token is retained in memory; the raw token exists only inside the email link.
_APP_RESET_TOKENS = {}
_APP_RESET_LAST_REQUEST = {}
_APP_RESET_LOCK = threading.Lock()


def _cleanup_password_reset_tokens():
    now = time.time()
    with _APP_RESET_LOCK:
        for token_hash, record in list(_APP_RESET_TOKENS.items()):
            if float(record.get("expires_at", 0)) <= now or record.get("used"):
                _APP_RESET_TOKENS.pop(token_hash, None)
        for username, requested_at in list(_APP_RESET_LAST_REQUEST.items()):
            if now - float(requested_at) > max(APP_PASSWORD_RESET_COOLDOWN_SECONDS, 60):
                _APP_RESET_LAST_REQUEST.pop(username, None)


def _hash_reset_token(token):
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()



def _load_app_users():
    try:
        if os.path.exists(APP_USERS_FILE):
            with open(APP_USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            return data.get("users", []) if isinstance(data, dict) else []
    except Exception as exc:
        print(f"[AUTH] user store read error: {exc}")
    return []


def _save_app_users(users):
    tmp = APP_USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"users": users}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, APP_USERS_FILE)


def _hash_app_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, APP_PBKDF2_ROUNDS)
    return base64.b64encode(salt).decode(), base64.b64encode(digest).decode()


def _verify_app_password(password, user):
    try:
        salt = base64.b64decode(user["salt"])
        digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, APP_PBKDF2_ROUNDS)
        return hmac.compare_digest(base64.b64encode(digest).decode(), user.get("password_hash", ""))
    except Exception:
        return False


def _token_for(user):
    payload = {"sub": user["username"], "role": user.get("role", "Viewer"), "exp": int(time.time()) + APP_TOKEN_TTL}
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(APP_AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def _user_from_token(token):
    try:
        raw, sig = str(token).split(".", 1)
        expected = hmac.new(APP_AUTH_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padded = raw + "=" * (-len(raw) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return {"username": payload.get("sub"), "role": payload.get("role", "Viewer")}
    except Exception:
        return None


def _current_app_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Application login required")
    user = _user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    stored = next((u for u in _load_app_users() if u.get("username") == user.get("username")), None)
    if not stored or not stored.get("enabled", True):
        raise HTTPException(status_code=401, detail="User disabled or not found")
    return {"username": stored.get("username"), "role": stored.get("role", "Viewer")}


def _require_admin(user):
    if str(user.get("role", "")).lower() not in {"administrator", "admin"}:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def _audit(action, category="SYSTEM", actor="VisionGuard", details="", target=""):
    try:
        rows = []
        if os.path.exists(AUDIT_FILE):
            with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                rows = json.load(f) or []
        rows.append({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action, "category": category, "actor": actor, "target": target, "details": details})
        with open(AUDIT_FILE, "w", encoding="utf-8") as f:
            json.dump(rows[-5000:], f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"[AUDIT] {exc}")



# ==========================================================
# DATABASE
# ==========================================================

Base.metadata.create_all(
    bind=engine
)


# ==========================================================
# CORS
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    # Allow local Vite dev servers on any port (5173, 5174, 5175, ...).
    # This prevents browser "Network Error" when Vite changes ports.
    allow_origins=[],
    # Local/Vite/LAN deployment: allow browser origins used by this on-prem app.
    allow_origin_regex=r"^https?://(?:localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|172(?:\.(?:1[6-9]|2\d|3[0-1]))(?:\.\d{1,3}){2}|192\.168(?:\.\d{1,3}){2})(?::\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================================
# NVR STATUS
#
# Dashboard does NOT perform a live NVR scan.
# crud.py background monitor owns the cache.
# ==========================================================

def get_nvr_status():

    return crud.get_cached_nvr_status()


# ==========================================================
# STARTUP
# ==========================================================

@app.on_event("startup")
def _start_nvr_time_guard():
    start_time_monitor()


@app.on_event("startup")
def startup():

    print("=" * 70)
    print("VisionGuard AI Starting...")
    print("=" * 70)

    start_daily_health_report()

    start_nvr_outage_monitor()

    global _PREDICTIVE_THREAD_STARTED
    if not _PREDICTIVE_THREAD_STARTED:
        threading.Thread(target=_predictive_risk_worker, daemon=True, name="VisionGuardPredictiveRisk").start()
        _PREDICTIVE_THREAD_STARTED = True

    # ------------------------------------------------------
    # CAMERA / NVR BACKGROUND DISCOVERY
    # ------------------------------------------------------

    try:

        start_health_monitor()
        print("✓ NVR Health/CPU Monitor Started")

        crud.start_background_monitor()

        print(
            "✓ NVR/Camera Background Monitor "
            "Started Successfully"
        )

    except Exception as e:

        print(
            f"✗ Camera Monitor Error: {e}"
        )

    # ------------------------------------------------------
    # NVR STATUS
    # ------------------------------------------------------

    try:

        status = crud.get_cached_nvr_status()

        online = sum(
            1
            for nvr in status
            if nvr.get("status") == "ONLINE"
        )

        print(
            f"✓ NVR Cache Ready "
            f"({online}/{len(NVRS)} online)"
        )

    except Exception as e:

        print(
            f"✗ NVR Status Cache Error: {e}"
        )

    # ------------------------------------------------------
    # VIDEO MONITOR
    # ------------------------------------------------------

    try:

        start_video_monitor()

        print(
            "✓ Video Monitor Started Successfully"
        )

    except Exception as e:

        print(
            f"✗ Video Monitor Error: {e}"
        )

    # ------------------------------------------------------
    # HIKVISION EVENT LISTENER
    # ------------------------------------------------------

    try:

        start_listener()

        print(
            "✓ Hikvision Event Listener "
            "Started Successfully"
        )

    except Exception as e:

        print(
            f"✗ Event Listener Error: {e}"
        )

    # ------------------------------------------------------
    # RECORDING LOSS MONITOR
    # ------------------------------------------------------

    try:

        start_recording_monitor()

        print(
            "✓ Recording Loss Monitor "
            "Started Successfully"
        )

    except Exception as e:

        print(
            f"✗ Recording Monitor Error: {e}"
        )

    # ------------------------------------------------------
    # CAMERA ANGLE MONITOR
    # ------------------------------------------------------

    try:

        print("📐 Starting Camera Angle Monitor...")
        start_camera_angle_monitor()

        print(
            "✓ Camera Angle Monitor Started Successfully | "
            "first scan runs immediately; subsequent scans use configured interval"
        )

    except Exception as e:

        print(
            f"✗ Camera Angle Monitor Error: {e}"
        )

    print("=" * 70)


# ==========================================================
# SHUTDOWN
# ==========================================================

@app.on_event("shutdown")
def shutdown():

    print("=" * 70)
    print("VisionGuard AI Shutting Down...")
    print("=" * 70)

    # ------------------------------------------------------
    # NVR / CAMERA BACKGROUND MONITOR
    # ------------------------------------------------------

    try:

        crud.stop_background_monitor()

        print(
            "✓ NVR/Camera Background Monitor Stopped"
        )

    except Exception as e:

        print(
            f"⚠️ Monitor Shutdown Error: {e}"
        )

    # ------------------------------------------------------
    # CAMERA ANGLE MONITOR
    # ------------------------------------------------------

    try:

        stop_camera_angle_monitor()

        print(
            "✓ Camera Angle Monitor Stopped"
        )

    except Exception as e:

        print(
            f"⚠️ Camera Angle Monitor "
            f"Shutdown Error: {e}"
        )



# ==========================================================
# LIVE VIEW / PLAYBACK CONSOLE HELPERS
# ==========================================================

def _nvr_by_id(nvr_id: int):
    for nvr in NVRS:
        if int(nvr.get('id', -1)) == int(nvr_id): return nvr
    return None

def _hik_request(nvr, endpoint, method='GET', body=None, timeout=15):
    url=f"http://{nvr['ip']}:{nvr['port']}{endpoint}"
    try:
        return requests.request(method,url,auth=HTTPDigestAuth(nvr['username'],nvr['password']),data=body,headers={'Accept':'application/xml','Content-Type':'application/xml'},timeout=timeout)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502,detail=f"{nvr['name']} request failed: {exc}")

def _local_xml_text(node,names,default=''):
    if node is None: return default
    wanted={str(x).lower() for x in names}
    for child in node.iter():
        if child.tag.rsplit('}',1)[-1].lower() in wanted and child.text: return child.text.strip()
    return default

def _recording_track_candidates(nvr, channel_id: int):
    """Return Hikvision recording tracks in the most likely order."""
    candidates = []
    try:
        from .recording_monitor import TRACK_CACHE, get_track_candidates
        host = str(nvr.get("ip", nvr.get("host", "")))
        cached = TRACK_CACHE.get(f"{host}:{int(channel_id)}")
        if cached:
            candidates.append(int(cached))
        candidates.extend(get_track_candidates(nvr, int(channel_id)))
    except Exception:
        pass
    candidates.extend([
        int(channel_id) * 100 + 1,
        int(channel_id) * 100 + 2,
        int(channel_id),
        int(channel_id) + 100,
        int(channel_id) + 200,
    ])
    out=[]
    for value in candidates:
        try:
            value=int(value)
        except Exception:
            continue
        if value > 0 and value not in out:
            out.append(value)
    return out


def _build_console_search_xml(search_id, track_id, start_time, end_time):
    """Use the Hikvision CMSearchDescription format accepted by these NVRs."""
    def stamp(value):
        text = str(value).strip().replace(" ", "T")
        if text.endswith("Z") or "+" in text[10:] or "-" in text[10:]:
            return text
        return text + "+05:30"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchDescription>
  <searchID>{search_id}</searchID>
  <trackList><trackID>{int(track_id)}</trackID></trackList>
  <timeSpanList><timeSpan>
    <startTime>{stamp(start_time)}</startTime><endTime>{stamp(end_time)}</endTime>
  </timeSpan></timeSpanList>
  <maxResults>200</maxResults><searchResultPosition>0</searchResultPosition>
  <metadataList><metadataDescriptor>//recordType.meta.std-cgi.com</metadataDescriptor></metadataList>
</CMSearchDescription>"""



def _discover_nvr_cameras_for_history(nvr):
    """Discover camera names directly from one NVR for historical finder."""
    try:
        r = _hik_request(nvr, "/ISAPI/ContentMgmt/InputProxy/channels", "GET", timeout=8)
        if not r.ok:
            return []
        root = ET.fromstring(r.text)
        cameras = []
        for item in root.iter():
            if item.tag.rsplit("}", 1)[-1].lower() != "inputproxychannel":
                continue
            channel = _local_xml_text(item, ("id",), "")
            name = _local_xml_text(item, ("name",), "")
            try:
                channel_id = int(channel)
            except Exception:
                continue
            cameras.append({"channel": channel_id, "name": name.strip() or f"Camera {channel_id}"})
        return cameras
    except Exception:
        return []


def _normalise_camera_name(value):
    """Create a forgiving camera-name key for historical searches.

    Case, spaces and punctuation are ignored, so values such as
    ``B2C-1``, ``b2c1`` and ``B2C 1`` resolve to the same search key.
    """
    text = str(value or "").strip().casefold()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _parse_historical_time(value):
    """Parse the date/time formats used by VisionGuard movement history and UI."""
    if value is None:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    if not text:
        return None
    for parser in (
        lambda x: datetime.fromisoformat(x),
        lambda x: datetime.strptime(x, "%d-%m-%Y %I:%M:%S %p"),
        lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S"),
        lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S"),
    ):
        try:
            dt = parser(text)
            # Historical UI times are local wall-clock times. Normalize
            # offset-aware timestamps to naive local-wall-clock values so
            # overlap comparisons never raise aware/naive TypeError.
            if getattr(dt, "tzinfo", None) is not None:
                dt = dt.replace(tzinfo=None)
            return dt
        except Exception:
            continue
    return None


def _load_camera_movement_events(camera_name):
    """Load persisted camera NVR movement events for a camera name."""
    query = _normalise_camera_name(camera_name)
    if not query:
        return []

    try:
        if not MOVEMENT_FILE.exists():
            return []
        with MOVEMENT_FILE.open("r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception as exc:
        print(f"[HISTORICAL] Movement history read failed: {exc}")
        return []

    events = []
    for item in history if isinstance(history, list) else []:
        event_name = _normalise_camera_name(item.get("camera", ""))
        if not event_name or not (event_name == query or query in event_name or event_name in query):
            continue
        event_time = _parse_historical_time(item.get("time"))
        if not event_time:
            continue
        old_nvr = item.get("previous_nvr")
        old_channel = item.get("previous_channel")
        new_nvr = item.get("current_nvr")
        new_channel = item.get("current_channel")
        if not old_nvr or old_channel is None or not new_nvr or new_channel is None:
            continue
        events.append({
            "time": event_time,
            "previous_nvr": str(old_nvr),
            "previous_channel": int(old_channel),
            "current_nvr": str(new_nvr),
            "current_channel": int(new_channel),
            "camera_name": item.get("camera") or camera_name,
        })

    events.sort(key=lambda x: x["time"])
    return events


def _load_device_registry_candidates(camera_name, start_time, end_time):
    """Use the persistent device registry as a second historical mapping source.

    The registry keeps the NVR/channel key plus first_seen/last_seen. This is
    useful when an older camera assignment exists in the registry even though
    the movement-history event was not recorded.
    """
    registry_file = Path(__file__).resolve().parent / "device_registry.json"
    query = _normalise_camera_name(camera_name)
    start_dt = _parse_historical_time(start_time)
    end_dt = _parse_historical_time(end_time)
    if not query or not start_dt or not end_dt or not registry_file.exists():
        return []

    try:
        with registry_file.open("r", encoding="utf-8") as f:
            registry = json.load(f)
    except Exception as exc:
        print(f"[HISTORICAL] Device registry read failed: {exc}")
        return []

    out = []
    for key, item in registry.items() if isinstance(registry, dict) else []:
        if not isinstance(item, dict):
            continue
        name = item.get("camera", "")
        if not name or not (query == _normalise_camera_name(name) or query in _normalise_camera_name(name)):
            continue

        first_seen = _parse_historical_time(item.get("first_seen"))
        last_seen = _parse_historical_time(item.get("last_seen"))
        if first_seen and first_seen > end_dt:
            continue
        if last_seen and last_seen < start_dt:
            continue

        channel = None
        try:
            channel = int(str(key).rsplit("_", 1)[-1])
        except Exception:
            try:
                channel = int(item.get("channel"))
            except Exception:
                continue

        nvr = _nvr_by_name_or_id(item.get("nvr"))
        if not nvr:
            continue
        out.append((nvr, {
            "channel": channel,
            "name": name,
            "mapping_source": "device-registry",
            "valid_from": first_seen,
            "valid_to": last_seen,
        }))
    return out


def _nvr_by_name_or_id(value):
    """Resolve a historical NVR name/id to the currently configured NVR object."""
    needle = str(value or "").strip().casefold()
    if not needle:
        return None
    for nvr in NVRS:
        if str(nvr.get("name", "")).strip().casefold() == needle:
            return nvr
        if str(nvr.get("id", "")).strip().casefold() == needle:
            return nvr
    return None


def _historical_assignment_candidates(camera_name, start_time, end_time, current_matches):
    """Resolve the NVR/channel that was valid during the requested time.

    Priority:
      1. durable assignment timeline
      2. confirmed movement events
      3. device registry first_seen/last_seen
      4. current discovery only when no historical evidence exists

    If historical evidence exists, a current channel is NOT blindly added to
    an old-date search. This prevents today's channel from being searched for
    yesterday's recording after an IP/NVR migration.
    """
    start_dt = _parse_historical_time(start_time)
    end_dt = _parse_historical_time(end_time)
    if not start_dt or not end_dt:
        return [], False
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt

    candidates = []
    historical_evidence = False

    def overlap(vf, vt):
        if vf and end_dt < vf:
            return False
        if vt and start_dt > vt:
            return False
        return True

    def add(nvr_name, channel, source, camera_label=None,
            valid_from=None, valid_to=None, moved_from=None, moved_to=None):
        try:
            channel = int(channel)
        except Exception:
            return
        nvr = _nvr_by_name_or_id(nvr_name)
        if not nvr or channel <= 0:
            return
        key = (str(nvr.get("id")), channel)
        row = {
            "channel": channel,
            "name": camera_label or camera_name,
            "mapping_source": source,
            "valid_from": valid_from.isoformat(sep=" ") if hasattr(valid_from, "isoformat") else valid_from,
            "valid_to": valid_to.isoformat(sep=" ") if hasattr(valid_to, "isoformat") else valid_to,
            "moved_from": moved_from,
            "moved_to": moved_to,
        }
        for existing in candidates:
            if (str(existing[0].get("id")), int(existing[1]["channel"])) == key:
                # Prefer the strongest source and keep the widest known interval.
                priority = {"assignment-timeline": 4, "movement-history": 3,
                            "device-registry": 2, "current-discovery": 1}
                if priority.get(source, 0) > priority.get(existing[1].get("mapping_source"), 0):
                    existing[1].update(row)
                return
        candidates.append((nvr, row))

    # 1) Durable timeline
    try:
        timeline = get_camera_assignment_timeline(
            camera_name,
            start=start_time,
            end=end_time,
            limit=500,
        )
    except Exception as exc:
        print(f"[HISTORICAL] Assignment timeline read failed: {exc}")
        timeline = []

    for item in timeline:
        vf = _parse_historical_time(item.get("valid_from"))
        vt = _parse_historical_time(item.get("valid_to"))
        if not overlap(vf, vt):
            continue
        historical_evidence = True
        add(
            item.get("nvr"),
            item.get("channel"),
            "assignment-timeline",
            item.get("camera") or camera_name,
            vf,
            vt,
            item.get("moved_from"),
            item.get("moved_to"),
        )

    # 2) Legacy movement history
    if not historical_evidence:
        events = _load_camera_movement_events(camera_name)
        if events:
            historical_evidence = True
            assignment = None
            segment_start = None
            segments = []
            first = events[0]
            assignment = (first["previous_nvr"], first["previous_channel"], first["camera_name"])
            for event in events:
                segment_end = event["time"]
                segments.append((segment_start, segment_end, assignment))
                assignment = (event["current_nvr"], event["current_channel"], event["camera_name"])
                segment_start = segment_end
            segments.append((segment_start, None, assignment))

            for seg_start, seg_end, seg_assignment in segments:
                if (seg_start is None or end_dt >= seg_start) and (seg_end is None or start_dt <= seg_end):
                    add(
                        seg_assignment[0], seg_assignment[1], "movement-history",
                        seg_assignment[2], seg_start, seg_end,
                    )

    # 3) Registry evidence. Registry rows are treated as historical only when
    # their first_seen/last_seen overlaps the requested interval.
    try:
        registry_candidates = _load_device_registry_candidates(
            camera_name, start_time, end_time
        )
    except Exception as exc:
        # A malformed/legacy registry must never turn a recording search into
        # HTTP 500. Historical search can safely continue with timeline,
        # movement history and current discovery evidence.
        print(f"[HISTORICAL] Device registry candidate error: {exc}")
        registry_candidates = []
    if registry_candidates:
        historical_evidence = True
    for nvr, cam in registry_candidates:
        add(
            nvr.get("name") or nvr.get("id"),
            cam.get("channel"),
            "device-registry",
            cam.get("name") or camera_name,
            cam.get("valid_from"),
            cam.get("valid_to"),
        )

    # 4) Current discovery only if there is no historical evidence at all.
    if not historical_evidence:
        for nvr, cam in current_matches:
            add(
                nvr.get("name") or nvr.get("id"),
                cam.get("channel"),
                "current-discovery",
                cam.get("name"),
            )

    return candidates, historical_evidence

def _historical_recording_finder(camera_name, start_time, end_time):
    """Find historical recordings using camera movement history first.

    Current camera discovery is used only as a safety net. If a camera moved
    from NVR-2/CH-7 to NVR-5/CH-4, a February search can therefore query the old
    NVR/channel instead of blindly searching the current CH-4.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    query = _normalise_camera_name(camera_name)
    if not query:
        raise HTTPException(status_code=400, detail="Camera name is required")

    # Discover current camera names across the fleet. This remains useful for
    # new cameras and for searches where no movement history exists yet.
    max_workers = min(12, max(1, len(NVRS)))
    discovery = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_discover_nvr_cameras_for_history, nvr): nvr for nvr in NVRS}
        for future in as_completed(futures):
            nvr = futures[future]
            try:
                for cam in future.result():
                    discovery.append((nvr, cam))
            except Exception:
                continue

    exact = [(nvr, cam) for nvr, cam in discovery if _normalise_camera_name(cam["name"]) == query]
    name_matches = exact or [
        (nvr, cam) for nvr, cam in discovery
        if query in _normalise_camera_name(cam["name"])
    ]

    candidates, history_used = _historical_assignment_candidates(
        camera_name, start_time, end_time, name_matches
    )

    # If there is no persisted movement history, retain the original smart
    # name-match behaviour. If history exists, candidates already include the
    # relevant historical assignments plus current matches.
    if not candidates:
        candidates = [
            (nvr, {
                "channel": int(cam["channel"]),
                "name": cam["name"],
                "mapping_source": "current-discovery",
            })
            for nvr, cam in name_matches
        ]

    def search_one(item):
        nvr, cam = item
        try:
            # Never search outside the interval in which this channel was
            # actually assigned to the camera. This is what makes a request
            # spanning a camera move date-safe.
            effective_start = start_time
            effective_end = end_time
            vf = _parse_historical_time(cam.get("valid_from"))
            vt = _parse_historical_time(cam.get("valid_to"))
            requested_start_dt = _parse_historical_time(start_time)
            requested_end_dt = _parse_historical_time(end_time)
            if vf and requested_start_dt and vf > requested_start_dt:
                effective_start = vf.strftime("%Y-%m-%d %H:%M:%S")
            if vt and requested_end_dt and vt < requested_end_dt:
                effective_end = vt.strftime("%Y-%m-%d %H:%M:%S")
            clips = _search_recordings(
                nvr, int(cam["channel"]), effective_start, effective_end
            )
            return {
                "nvr_id": nvr.get("id"),
                "nvr": nvr.get("name"),
                "nvr_ip": nvr.get("ip"),
                "channel": int(cam["channel"]),
                "camera_name": cam.get("name") or camera_name,
                "mapping_source": cam.get("mapping_source", "current-discovery"),
                "valid_from": cam.get("valid_from"),
                "valid_to": cam.get("valid_to"),
                "moved_from": cam.get("moved_from"),
                "moved_to": cam.get("moved_to"),
                "searched_from": effective_start,
                "searched_to": effective_end,
                "recording_found": bool(clips),
                "recording_count": len(clips),
                "first_recording": clips[0].get("start_time") if clips else None,
                "last_recording": clips[-1].get("end_time") if clips else None,
                "results": clips[:50],
                "error": None,
            }
        except Exception as exc:
            return {
                "nvr_id": nvr.get("id"),
                "nvr": nvr.get("name"),
                "nvr_ip": nvr.get("ip"),
                "channel": int(cam["channel"]),
                "camera_name": cam.get("name") or camera_name,
                "mapping_source": cam.get("mapping_source", "current-discovery"),
                "valid_from": cam.get("valid_from"),
                "valid_to": cam.get("valid_to"),
                "moved_from": cam.get("moved_from"),
                "moved_to": cam.get("moved_to"),
                "searched_from": start_time,
                "searched_to": end_time,
                "recording_found": False,
                "recording_count": 0,
                "first_recording": None,
                "last_recording": None,
                "results": [],
                "error": str(exc),
            }

    results = []
    with ThreadPoolExecutor(max_workers=min(16, max(1, len(candidates)))) as pool:
        futures = [pool.submit(search_one, item) for item in candidates]
        for future in as_completed(futures):
            results.append(future.result())

    # Recording hits first, then historical assignments, then current matches.
    results.sort(key=lambda x: (
        not x["recording_found"],
        x.get("mapping_source") not in {"assignment-timeline", "movement-history", "device-registry"},
        str(x.get("nvr")),
        int(x.get("channel") or 0),
    ))

    return {
        "camera_name": camera_name.strip(),
        "start": start_time,
        "end": end_time,
        "searched_nvr_count": len(NVRS),
        "matched_channels": len(candidates),
        "exact_match": bool(exact),
        "historical_mapping_used": history_used,
        "results": results,
    }

def _search_recordings(nvr, channel_id: int, start_time: str, end_time: str):
    """Fast, compatible Hikvision recording search."""
    candidates = _recording_track_candidates(nvr, channel_id)
    last_error = None
    for track_id in candidates:
        body = _build_console_search_xml(f"VG-{int(time.time()*1000)}-{track_id}", track_id, start_time, end_time)
        try:
            r = _hik_request(nvr, "/ISAPI/ContentMgmt/search", "POST", body, timeout=5)
        except HTTPException as exc:
            last_error = exc
            continue
        if not r.ok:
            last_error = f"HTTP {r.status_code}"
            continue
        try:
            root = ET.fromstring(r.text)
        except ET.ParseError:
            continue
        results = []
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1].lower() != "searchmatchitem":
                continue
            uri = _local_xml_text(node, ("playbackURI", "playbackUrl", "downloadURI"))
            st = _local_xml_text(node, ("startTime",))
            en = _local_xml_text(node, ("endTime",))
            if not uri or not st or not en:
                continue
            results.append({"start_time": st, "end_time": en, "playback_uri": uri,
                            "track_id": _local_xml_text(node, ("sourceID", "trackID"), str(track_id))})
        if results:
            try:
                from .recording_monitor import TRACK_CACHE
                TRACK_CACHE[f"{nvr.get('ip','')}:{int(channel_id)}"] = int(track_id)
            except Exception:
                pass
            results.sort(key=lambda x: x.get("start_time", ""))
            return results
        text = r.text.lower()
        if "<responsestatus>true" in text or "<responsecode>200" in text:
            return []
    if last_error:
        raise HTTPException(status_code=502, detail=f"Recording search failed on {nvr['name']}: {last_error}. Verify the NVR recording track/channel and recording index.")
    return []


def _authenticated_rtsp_uri(nvr,uri:str):
    try:
        from urllib.parse import urlsplit,urlunsplit,quote
        parts=urlsplit(uri)
        if parts.scheme.lower()!='rtsp' or '@' in parts.netloc: return uri
        host=parts.hostname or nvr['ip']; port=f":{parts.port}" if parts.port else ''
        netloc=f"{quote(str(nvr['username']))}:{quote(str(nvr['password']))}@{host}{port}"
        return urlunsplit((parts.scheme,netloc,parts.path,parts.query,parts.fragment))
    except Exception: return uri

def _playback_mjpeg_generator(nvr, uri):
    """Compatibility fallback when FFmpeg is unavailable."""
    cap=None
    try:
        cap=cv2.VideoCapture(_authenticated_rtsp_uri(nvr,uri),cv2.CAP_FFMPEG)
        if not cap.isOpened(): return
        try: cap.set(cv2.CAP_PROP_BUFFERSIZE,1)
        except: pass
        while True:
            ok,frame=cap.read()
            if not ok or frame is None: break
            ok,encoded=cv2.imencode('.jpg',frame,[int(cv2.IMWRITE_JPEG_QUALITY),78])
            if ok: yield b'--frame\r\nContent-Type: image/jpeg\r\nCache-Control: no-cache\r\n\r\n'+encoded.tobytes()+b'\r\n'
    finally:
        if cap is not None: cap.release()


def _ffmpeg_playback_generator(nvr,uri):
    """Stream NVR recording as browser-compatible fragmented MP4."""
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg: return
    source=_authenticated_rtsp_uri(nvr,uri)
    cmd=[ffmpeg,'-hide_banner','-loglevel','error','-rtsp_transport','tcp','-fflags','nobuffer','-flags','low_delay','-i',source,'-map','0:v:0','-map','0:a:0?','-c:v','copy','-c:a','aac','-b:a','96k','-movflags','frag_keyframe+empty_moov+default_base_moof','-f','mp4','pipe:1']
    proc=None
    try:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
        while True:
            chunk=proc.stdout.read(64*1024)
            if not chunk: break
            yield chunk
    finally:
        if proc is not None:
            try: proc.kill()
            except: pass
            try: proc.wait(timeout=2)
            except: pass


# ==========================================================
# FIND NVR FOR LIVE
# ==========================================================

def find_nvr_for_live(
    nvr_name: str
):

    target = str(
        nvr_name
    ).strip().lower()

    for nvr in NVRS:

        if (
            str(
                nvr.get("name", "")
            ).strip().lower()
            == target
        ):

            return nvr

    return None


# ==========================================================
# LIVE MJPEG GENERATOR
# ==========================================================

def _live_stream_ids(nvr, channel_id: int):
    """Prefer low-bitrate sub-stream for fast startup, then main stream."""
    ch = int(channel_id)
    return [ch * 100 + 2, ch * 100 + 1, ch, ch * 100 + 3]


def _ffmpeg_live_generator(nvr, channel_id: int):
    """Low-latency MJPEG proxy using FFmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    for stream_id in _live_stream_ids(nvr, channel_id):
        source = rtsp_url(nvr, stream_id)
        print(f"[LIVE] FFmpeg opening {nvr['name']} CH-{channel_id} stream={stream_id}")
        cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-rtsp_transport", "tcp",
               "-stimeout", "5000000", "-fflags", "nobuffer", "-flags", "low_delay",
               "-an", "-i", source, "-vf", "fps=10,scale='min(960,iw)':-2",
               "-c:v", "mjpeg", "-q:v", "7", "-f", "mpjpeg", "pipe:1"]
        proc = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
            first = proc.stdout.read(256)
            if not first:
                proc.kill(); proc.wait(timeout=2)
                continue
            def chunks():
                try:
                    yield first
                    while True:
                        chunk = proc.stdout.read(64 * 1024)
                        if not chunk: break
                        yield chunk
                finally:
                    try: proc.kill()
                    except Exception: pass
                    try: proc.wait(timeout=2)
                    except Exception: pass
            return chunks()
        except Exception as exc:
            print(f"[LIVE] FFmpeg stream error {nvr['name']} CH-{channel_id}: {exc}")
            if proc is not None:
                try: proc.kill()
                except Exception: pass
    return None


def live_mjpeg_generator(nvr, channel_id: int):
    """FFmpeg-first live stream with OpenCV fallback."""
    stream = _ffmpeg_live_generator(nvr, channel_id)
    if stream is not None:
        yield from stream
        return
    cap = None
    try:
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000|max_delay;500000|fflags;nobuffer|flags;low_delay")
        for stream_id in _live_stream_ids(nvr, channel_id):
            cap = cv2.VideoCapture(rtsp_url(nvr, stream_id), cv2.CAP_FFMPEG)
            if cap.isOpened(): break
            cap.release(); cap = None
        if cap is None: return
        while True:
            ok, frame = cap.read()
            if not ok or frame is None: break
            h, w = frame.shape[:2]
            if w > 960:
                scale = 960.0 / float(w)
                frame = cv2.resize(frame, (960, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
            ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
            if ok: yield b'--frame\r\nContent-Type: image/jpeg\r\nCache-Control: no-cache\r\n\r\n' + encoded.tobytes() + b'\r\n'
    finally:
        if cap is not None:
            try: cap.release()
            except Exception: pass


# ==========================================================
# LIVE STREAM
# ==========================================================

@app.get(
    "/live/stream/{nvr_name}/{channel_id}"
)
def live_stream(
    nvr_name: str,
    channel_id: int
):

    nvr = find_nvr_for_live(
        nvr_name
    )

    if nvr is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"NVR '{nvr_name}' "
                f"not found"
            ),
        )

    if channel_id < 1:

        raise HTTPException(
            status_code=400,
            detail=(
                "Channel ID must be "
                "greater than 0"
            ),
        )

    return StreamingResponse(
        live_mjpeg_generator(
            nvr,
            channel_id
        ),
        media_type=(
            "multipart/"
            "x-mixed-replace;"
            " boundary=frame"
        ),
        headers={
            "Cache-Control":
                "no-cache, no-store, "
                "must-revalidate",

            "Pragma":
                "no-cache",

            "Expires":
                "0",

            "X-Accel-Buffering":
                "no",
        },
    )


# ==========================================================
# LIVE STREAM TEST
# ==========================================================

@app.get(
    "/live/test/{nvr_name}/{channel_id}"
)
def live_test(
    nvr_name: str,
    channel_id: int
):

    nvr = find_nvr_for_live(
        nvr_name
    )

    if nvr is None:

        raise HTTPException(
            status_code=404,
            detail=(
                f"NVR '{nvr_name}' "
                f"not found"
            ),
        )

    if channel_id < 1:

        raise HTTPException(
            status_code=400,
            detail=(
                "Channel ID must be "
                "greater than 0"
            ),
        )

    stream_id = (
        int(channel_id) * 100 + 1
    )

    return {
        "success": True,
        "nvr": nvr["name"],
        "nvr_ip": nvr["ip"],
        "channel": channel_id,
        "stream_id": stream_id,
        "rtsp_port": 554,
        "stream_endpoint": (
            f"/live/stream/"
            f"{nvr['name']}/"
            f"{channel_id}"
        ),
    }



# ==========================================================
# LIVE CONSOLE DATA
# ==========================================================
@app.get('/live/nvrs')
def live_nvrs():
    statuses={str(x.get('name')):x for x in crud.get_cached_nvr_status()}; result=[]
    for nvr in NVRS:
        item=dict(statuses.get(nvr['name'],{})); item.update({'id':nvr['id'],'name':nvr['name'],'ip':nvr['ip'],'port':nvr['port']}); result.append(item)
    return result

@app.get('/live/cameras/{nvr_id}')
def live_cameras_for_nvr(nvr_id:int):
    nvr=_nvr_by_id(nvr_id)
    if not nvr: raise HTTPException(status_code=404,detail='NVR not found')
    cameras=[c for c in crud.get_cached_cameras(online_only=False) if str(c.get('nvr'))==nvr['name']]; cameras.sort(key=lambda c:int(c.get('id',0)))
    return {'nvr':nvr['name'],'ip':nvr['ip'],'cameras':cameras}

@app.get('/live/diagnostics/{nvr_id}/{channel_id}')
def live_diagnostics(nvr_id:int,channel_id:int):
    nvr=_nvr_by_id(nvr_id)
    if not nvr: raise HTTPException(status_code=404,detail='NVR not found')
    camera=next((c for c in crud.get_cached_cameras(online_only=False) if c.get('nvr')==nvr['name'] and int(c.get('id',-1))==int(channel_id)),None)
    health=next((x for x in get_health(force=True) if x.get('name')==nvr['name']),{}); storage=next((x for x in storage_snapshot(force=True).get('data',[]) if x.get('name')==nvr['name']),{})
    issues=[]; cpu=health.get('cpu_percent'); mem=health.get('memory_percent'); temp=health.get('temperature_c')
    if health.get('status')!='ONLINE': issues.append('NVR is unreachable or the health telemetry endpoint is unavailable')
    if health.get('status')=='ONLINE' and health.get('cpu_percent') is None: issues.append('CPU telemetry is not exposed by this NVR firmware')
    if health.get('status')=='ONLINE' and health.get('memory_percent') is None: issues.append('Memory telemetry is not exposed by this NVR firmware')
    if health.get('status')=='ONLINE' and health.get('temperature_c') is None: issues.append('Temperature telemetry is not exposed by this NVR firmware')
    if cpu is not None and cpu>=90: issues.append(f'High CPU utilization: {cpu}%')
    elif cpu is not None and cpu>=75: issues.append(f'Elevated CPU utilization: {cpu}%')
    if mem is not None and mem>=90: issues.append(f'High memory utilization: {mem}%')
    if temp is not None and temp>=80: issues.append(f'Critical NVR temperature: {temp}°C')
    elif temp is not None and temp>=70: issues.append(f'High NVR temperature: {temp}°C')
    for hdd in storage.get('hdds',[]) or []:
        if str(hdd.get('status','')).lower() not in {'ok','normal','healthy','online','active','ready'}: issues.append(f"HDD {hdd.get('id','?')} status: {hdd.get('status')}")
    if camera and str(camera.get('status','')).lower() not in {'online','connected','up'}: issues.append(f"Camera status: {camera.get('status')}")
    if not issues: issues.append('No active hardware/storage issue detected by available telemetry')
    return {'nvr':nvr,'camera':camera,'health':health,'storage':storage,'issues':issues,'generated_at':time.strftime('%d-%m-%Y %I:%M:%S %p')}

@app.post('/live/snapshot/{nvr_name}/{channel_id}')
def live_snapshot(nvr_name:str,channel_id:int):
    nvr=find_nvr_for_live(nvr_name)
    if not nvr: raise HTTPException(status_code=404,detail='NVR not found')
    r=_hik_request(nvr,f'/ISAPI/Streaming/channels/{int(channel_id)*100+1}/picture','GET',timeout=15)
    if not r.ok or not r.content: raise HTTPException(status_code=502,detail=f'Snapshot unavailable: HTTP {r.status_code}')
    return Response(content=r.content,media_type=r.headers.get('Content-Type','image/jpeg'))



# ==========================================================
# RECORDING RETENTION INTELLIGENCE
# ==========================================================
# Retention is calculated from real recording search evidence, not HDD size.
# Results are cached so the dashboard does not repeatedly hit every NVR.
_RETENTION_CACHE = {}
_RETENTION_CACHE_LOCK = threading.RLock()
_RETENTION_CACHE_SECONDS = 15 * 60
_RETENTION_LOOKBACK_DAYS = 45


def _retention_now():
    return datetime.now().replace(microsecond=0)


def _retention_parse(value):
    try:
        return _parse_historical_time(value)
    except Exception:
        return None


def _retention_camera(nvr, cam, now=None):
    """Return actual oldest/newest recording evidence for one channel."""
    now = now or _retention_now()
    start = now - timedelta(days=_RETENTION_LOOKBACK_DAYS)
    try:
        clips = _search_recordings(
            nvr,
            int(cam.get("channel")),
            start.strftime("%Y-%m-%d %H:%M:%S"),
            now.strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as exc:
        return {
            "channel": int(cam.get("channel")),
            "camera_name": cam.get("name") or f"Camera {cam.get('channel')}",
            "recording_found": False,
            "retention_days": None,
            "oldest_recording": None,
            "newest_recording": None,
            "error": str(exc),
        }

    starts = []
    ends = []
    for clip in clips or []:
        st = _retention_parse(clip.get("start_time"))
        en = _retention_parse(clip.get("end_time"))
        if st: starts.append(st)
        if en: ends.append(en)
    oldest = min(starts) if starts else None
    newest = max(ends) if ends else None
    retention_days = None
    if oldest:
        retention_days = round(max(0.0, (now - oldest).total_seconds() / 86400), 1)
    return {
        "channel": int(cam.get("channel")),
        "camera_name": cam.get("name") or f"Camera {cam.get('channel')}",
        "recording_found": bool(oldest),
        "retention_days": retention_days,
        "oldest_recording": oldest.strftime("%Y-%m-%d %H:%M:%S") if oldest else None,
        "newest_recording": newest.strftime("%Y-%m-%d %H:%M:%S") if newest else None,
        "clip_count_sampled": len(clips or []),
        "error": None,
    }


def _retention_summary(force=False):
    now = time.time()
    with _RETENTION_CACHE_LOCK:
        cached = _RETENTION_CACHE.get("summary")
        if cached and not force and now - cached["cached_at_epoch"] < _RETENTION_CACHE_SECONDS:
            return cached["data"]

    from concurrent.futures import ThreadPoolExecutor, as_completed
    discovered = []
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(NVRS)))) as pool:
        futures = {pool.submit(_discover_nvr_cameras_for_history, nvr): nvr for nvr in NVRS}
        for f in as_completed(futures):
            nvr = futures[f]
            try:
                for cam in f.result() or []:
                    discovered.append((nvr, cam))
            except Exception:
                pass

    results_by_nvr = {str(n.get("id")): {
        "nvr_id": n.get("id"), "nvr": n.get("name"), "ip": n.get("ip"),
        "status": "CHECKING", "camera_count": 0, "recording_cameras": 0,
        "missing_cameras": 0, "retention_days": None, "oldest_recording": None,
        "last_checked": _retention_now().strftime("%Y-%m-%d %H:%M:%S"),
        "cameras": [],
    } for n in NVRS}

    # Search channels concurrently, but keep one compact result per channel.
    with ThreadPoolExecutor(max_workers=min(24, max(1, len(discovered)))) as pool:
        future_map = {pool.submit(_retention_camera, nvr, cam): (nvr, cam) for nvr, cam in discovered}
        for f in as_completed(future_map):
            nvr, cam = future_map[f]
            item = results_by_nvr.setdefault(str(nvr.get("id")), {
                "nvr_id": nvr.get("id"), "nvr": nvr.get("name"), "ip": nvr.get("ip"),
                "status": "CHECKING", "camera_count": 0, "recording_cameras": 0,
                "missing_cameras": 0, "retention_days": None, "oldest_recording": None,
                "last_checked": _retention_now().strftime("%Y-%m-%d %H:%M:%S"), "cameras": []
            })
            try:
                item["cameras"].append(f.result())
            except Exception as exc:
                item["cameras"].append({
                    "channel": cam.get("channel"), "camera_name": cam.get("name"),
                    "recording_found": False, "retention_days": None,
                    "oldest_recording": None, "newest_recording": None, "error": str(exc)
                })

    for item in results_by_nvr.values():
        item["cameras"].sort(key=lambda x: int(x.get("channel") or 0))
        item["camera_count"] = len(item["cameras"])
        found = [x for x in item["cameras"] if x.get("recording_found") and x.get("retention_days") is not None]
        item["recording_cameras"] = len(found)
        item["missing_cameras"] = item["camera_count"] - item["recording_cameras"]
        # Conservative NVR retention = oldest evidence across all recording cameras.
        if found:
            item["retention_days"] = round(min(x["retention_days"] for x in found), 1)
            oldest_values = [x["oldest_recording"] for x in found if x.get("oldest_recording")]
            item["oldest_recording"] = min(oldest_values) if oldest_values else None
            item["status"] = "CRITICAL" if item["retention_days"] < 20 else ("WARNING" if item["retention_days"] < 30 else "HEALTHY")
        else:
            item["status"] = "RECORDING FAILURE" if item["camera_count"] else "NO CAMERAS"
    data = {
        "generated_at": _retention_now().strftime("%Y-%m-%d %H:%M:%S"),
        "lookback_days": _RETENTION_LOOKBACK_DAYS,
        "cache_seconds": _RETENTION_CACHE_SECONDS,
        "nvrs": list(results_by_nvr.values()),
    }
    with _RETENTION_CACHE_LOCK:
        _RETENTION_CACHE["summary"] = {"cached_at_epoch": time.time(), "data": data}
    return data


@app.get('/recording-retention/summary')
def recording_retention_summary(refresh: bool = False, user=Depends(_current_app_user)):
    return _retention_summary(force=bool(refresh))


@app.get('/recording-retention/nvr/{nvr_id}')
def recording_retention_nvr(nvr_id: int, refresh: bool = False, user=Depends(_current_app_user)):
    data = _retention_summary(force=bool(refresh))
    for item in data.get("nvrs", []):
        if str(item.get("nvr_id")) == str(nvr_id):
            return item
    raise HTTPException(status_code=404, detail="NVR not found")


@app.get('/historical-recordings/search')
def historical_recording_search(camera_name: str, start: str, end: str, user=Depends(_current_app_user)):
    """Find a named camera's historical recordings across every configured NVR."""
    return _historical_recording_finder(camera_name, start, end)


def _historical_camera_history(camera_name, start_date, end_date):
    """Build a compact day-by-day map of where a named camera was recorded.

    This is intentionally based on recording evidence from the NVRs rather than
    current database mappings, so it can answer historical questions such as
    "where was CAM-17 on 10 July?".
    """
    from datetime import datetime, timedelta
    try:
        first = datetime.strptime(str(start_date), "%Y-%m-%d").date()
        last = datetime.strptime(str(end_date), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Dates must use YYYY-MM-DD format")
    if last < first:
        raise HTTPException(status_code=400, detail="End date cannot be before start date")
    if (last - first).days > 31:
        raise HTTPException(status_code=400, detail="History search is limited to 31 days at a time")

    days=[]
    cursor=first
    while cursor <= last:
        day=cursor.isoformat()
        result=_historical_recording_finder(camera_name, f"{day} 00:00:00", f"{day} 23:59:59")
        locations=[]
        for item in result.get("results", []):
            if item.get("recording_found"):
                locations.append({
                    "nvr_id": item.get("nvr_id"),
                    "nvr": item.get("nvr"),
                    "channel": item.get("channel"),
                    "camera_name": item.get("camera_name"),
                    "first_recording": item.get("first_recording"),
                    "last_recording": item.get("last_recording"),
                    "recording_count": item.get("recording_count", 0),
                })
        days.append({"date": day, "found": bool(locations), "locations": locations})
        cursor += timedelta(days=1)
    return {"camera_name": camera_name.strip(), "start_date": str(first), "end_date": str(last), "days": days}


def _historical_recording_gaps(camera_name, start_time, end_time, gap_minutes=10):
    """Find unusually large gaps in the returned recording clips for a camera."""
    result=_historical_recording_finder(camera_name, start_time, end_time)
    from datetime import datetime
    try:
        threshold=max(1, int(gap_minutes)) * 60
    except Exception:
        threshold=600
    out=[]
    for item in result.get("results", []):
        clips=item.get("results") or []
        previous=None
        gaps=[]
        for clip in clips:
            try:
                st=datetime.fromisoformat(str(clip.get("start_time", "")).replace("Z", "+00:00"))
                en=datetime.fromisoformat(str(clip.get("end_time", "")).replace("Z", "+00:00"))
            except Exception:
                continue
            if previous is not None:
                seconds=(st-previous).total_seconds()
                if seconds >= threshold:
                    gaps.append({"from": previous.isoformat(), "to": st.isoformat(), "duration_seconds": int(seconds)})
            if previous is None or en > previous:
                previous=en
        if item.get("recording_found"):
            out.append({
                "nvr_id": item.get("nvr_id"), "nvr": item.get("nvr"),
                "channel": item.get("channel"), "camera_name": item.get("camera_name"),
                "clip_count": len(clips), "gaps": gaps,
                "largest_gap_seconds": max((g["duration_seconds"] for g in gaps), default=0),
            })
    out.sort(key=lambda x: x["largest_gap_seconds"], reverse=True)
    return {"camera_name": camera_name.strip(), "start": start_time, "end": end_time, "gap_threshold_minutes": int(gap_minutes), "locations": out}


@app.get('/historical-recordings/timeline')
def historical_recording_timeline(
    camera_name: str,
    start: str = None,
    end: str = None,
    user=Depends(_current_app_user),
):
    """Return the camera's confirmed NVR/channel assignment timeline."""
    rows = get_camera_assignment_timeline(
        camera_name,
        start=start,
        end=end,
        limit=500,
    )
    return {
        "camera_name": camera_name.strip(),
        "count": len(rows),
        "timeline": rows,
        "history_available": bool(rows),
    }


@app.get('/historical-recordings/history')
def historical_recording_history(camera_name: str, start_date: str, end_date: str, user=Depends(_current_app_user)):
    return _historical_camera_history(camera_name, start_date, end_date)


@app.get('/historical-recordings/gaps')
def historical_recording_gaps(camera_name: str, start: str, end: str, gap_minutes: int = 10, user=Depends(_current_app_user)):
    return _historical_recording_gaps(camera_name, start, end, gap_minutes)

@app.get('/live/recordings/search/{nvr_id}/{channel_id}')
def live_recording_search(nvr_id:int,channel_id:int,start:str,end:str):
    nvr=_nvr_by_id(nvr_id)
    if not nvr: raise HTTPException(status_code=404,detail='NVR not found')
    return {'nvr':nvr['name'],'channel':channel_id,'results':_search_recordings(nvr,channel_id,start,end)}


@app.get('/live/recordings/download/{nvr_id}/{channel_id}')
def live_recording_download(nvr_id:int,channel_id:int,start:str,end:str):
    nvr=_nvr_by_id(nvr_id)
    if not nvr: raise HTTPException(status_code=404,detail='NVR not found')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg: raise HTTPException(status_code=503,detail='Recording download needs FFmpeg installed on the backend PC. Live view and playback search do not require this download helper.')
    results=_search_recordings(nvr,channel_id,start,end)
    if not results: raise HTTPException(status_code=404,detail='No recording found in selected time window')
    uri=_authenticated_rtsp_uri(nvr,results[0]['playback_uri'])
    folder=tempfile.mkdtemp(prefix='visionguard_clip_')
    output=os.path.join(folder,f"{nvr['name']}_CH-{channel_id}.mp4")
    try:
        subprocess.run([ffmpeg,'-y','-rtsp_transport','tcp','-i',uri,'-t','1800','-map','0:v?','-map','0:a?','-c','copy',output],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=1900,check=True)
    except Exception as exc:
        shutil.rmtree(folder,ignore_errors=True)
        raise HTTPException(status_code=502,detail=f'Clip export failed: {exc}')
    from fastapi.responses import FileResponse
    return FileResponse(output,media_type='video/mp4',filename=os.path.basename(output),background=None)

@app.get('/live/playback/{nvr_id}/{channel_id}')
def live_playback(nvr_id:int,channel_id:int,start:str,end:str):
    nvr=_nvr_by_id(nvr_id)
    if not nvr: raise HTTPException(status_code=404,detail='NVR not found')
    results=_search_recordings(nvr,channel_id,start,end)
    if not results: raise HTTPException(status_code=404,detail='No recording found in selected time window')
    uri=results[0]['playback_uri']
    if shutil.which('ffmpeg'):
        return StreamingResponse(_ffmpeg_playback_generator(nvr,uri),media_type='video/mp4',headers={'Cache-Control':'no-cache, no-store, must-revalidate','X-Accel-Buffering':'no','Accept-Ranges':'none'})
    return StreamingResponse(_playback_mjpeg_generator(nvr,uri),media_type='multipart/x-mixed-replace; boundary=frame',headers={'Cache-Control':'no-cache, no-store, must-revalidate'})

# ==========================================================
# HOME
# ==========================================================

@app.get("/")
def home():

    return {
        "message":
            "VisionGuard AI Backend Running"
    }


# ==========================================================
# HEALTH
# ==========================================================

@app.get("/health")
def health():

    return {
        "status":
            "UP"
    }


# ==========================================================
# APPLICATION AUTHENTICATION
# ==========================================================

@app.post("/auth/password/forgot")
def request_app_password_reset(payload: dict, request: Request):
    """Request a one-time reset link for a VisionGuard application account."""
    _cleanup_password_reset_tokens()
    username = str(payload.get("username", "")).strip()

    # Always return the same public response so the endpoint does not reveal
    # whether a particular username exists.
    public_message = "If the account is eligible, a password reset link has been sent to the registered recovery email."

    if not username:
        return {"success": True, "message": public_message}

    users = _load_app_users()
    user = next((u for u in users if str(u.get("username", "")).casefold() == username.casefold()), None)
    if not user or not user.get("enabled", True):
        return {"success": True, "message": public_message}

    # The recovery mailbox is deliberately server-side configuration, not a
    # value supplied by the browser.
    recovery_email = str(APP_PASSWORD_RESET_EMAIL or "").strip()
    if not recovery_email:
        print("[AUTH] Password reset requested but no recovery email is configured.")
        return {"success": True, "message": public_message}

    now = time.time()
    with _APP_RESET_LOCK:
        last = float(_APP_RESET_LAST_REQUEST.get(user.get("username"), 0))
        if now - last < APP_PASSWORD_RESET_COOLDOWN_SECONDS:
            return {"success": True, "message": public_message}
        _APP_RESET_LAST_REQUEST[user.get("username")] = now

    raw_token = secrets.token_urlsafe(40)
    token_hash = _hash_reset_token(raw_token)
    expires_at = now + (int(APP_PASSWORD_RESET_TTL_MINUTES) * 60)

    with _APP_RESET_LOCK:
        # Invalidate older reset links for the same account.
        for old_hash, record in list(_APP_RESET_TOKENS.items()):
            if str(record.get("username", "")).casefold() == str(user.get("username", "")).casefold():
                _APP_RESET_TOKENS.pop(old_hash, None)
        _APP_RESET_TOKENS[token_hash] = {
            "username": user.get("username"),
            "expires_at": expires_at,
            "used": False,
        }

    origin = str(request.headers.get("origin", "")).strip().rstrip("/")
    frontend_url = origin or os.getenv("VISIONGUARD_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    reset_url = f"{frontend_url}/reset-password?token={raw_token}"

    try:
        send_app_password_reset_email(
            recipient=recovery_email,
            username=user.get("username", username),
            reset_url=reset_url,
            expires_minutes=int(APP_PASSWORD_RESET_TTL_MINUTES),
        )
        _audit("Application password reset requested", "AUTH", user.get("username", username), "Password reset link sent", "Application")
        print(f"[AUTH] Password reset email sent for {user.get('username', username)}")
    except Exception as exc:
        with _APP_RESET_LOCK:
            _APP_RESET_TOKENS.pop(token_hash, None)
        print(f"[AUTH] Password reset email error: {exc}")
        # Return a clear server-side failure so the UI does not report a
        # password reset as successful when the reset email was not sent.
        raise HTTPException(
            status_code=502,
            detail="Password reset email could not be sent. Check the VisionGuard SMTP configuration and backend logs.",
        )

    return {"success": True, "message": public_message}


@app.post("/auth/password/reset")
def reset_app_password(payload: dict):
    """Consume a one-time reset token and set a new application password."""
    _cleanup_password_reset_tokens()
    raw_token = str(payload.get("token", "")).strip()
    new_password = str(payload.get("password", ""))

    if not raw_token:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must contain at least 8 characters")

    token_hash = _hash_reset_token(raw_token)
    with _APP_RESET_LOCK:
        record = _APP_RESET_TOKENS.get(token_hash)
        if not record or record.get("used") or float(record.get("expires_at", 0)) <= time.time():
            _APP_RESET_TOKENS.pop(token_hash, None)
            raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
        username = record.get("username")
        record["used"] = True
        _APP_RESET_TOKENS.pop(token_hash, None)

    users = _load_app_users()
    target = next((u for u in users if str(u.get("username", "")).casefold() == str(username).casefold()), None)
    if not target or not target.get("enabled", True):
        raise HTTPException(status_code=400, detail="Account is unavailable")

    salt, password_hash = _hash_app_password(new_password)
    target["salt"] = salt
    target["password_hash"] = password_hash
    target["password_changed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    _save_app_users(users)
    _audit("Application password reset completed", "AUTH", target.get("username", "Unknown"), "Password reset using one-time email link", "Application")

    return {"success": True, "message": "Password reset successfully. Please sign in with your new password."}


@app.post("/auth/login")
def app_login(payload: dict):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = next((u for u in _load_app_users() if str(u.get("username", "")).lower() == username.lower()), None)
    if not user or not user.get("enabled", True) or not _verify_app_password(password, user):
        _audit("Application login failed", "AUTH", username or "Unknown", "Invalid username/password", "Application")
        raise HTTPException(status_code=401, detail="Invalid username or password")
    clean = {"username": user["username"], "role": user.get("role", "Viewer")}
    token = _token_for(clean)
    _audit("Application login", "AUTH", clean["username"], "Successful login", "Application")
    return {"access_token": token, "token_type": "bearer", "user": clean, "expires_in": APP_TOKEN_TTL}


@app.get("/auth/me")
def app_me(user=Depends(_current_app_user)):
    return user


@app.get("/auth/users")
def app_users(user=Depends(_current_app_user)):
    _require_admin(user)
    return [{"username": u.get("username"), "role": u.get("role", "Viewer"), "enabled": bool(u.get("enabled", True)), "created_at": u.get("created_at", "")} for u in _load_app_users()]


@app.post("/auth/users")
def create_app_user(payload: dict, user=Depends(_current_app_user)):
    _require_admin(user)
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "Viewer")).strip() or "Viewer"
    if not username or len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must contain at least 3 characters")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must contain at least 6 characters")
    allowed_roles = {"Administrator", "Operator", "Viewer"}
    if role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Invalid role")
    users = _load_app_users()
    if any(str(u.get("username", "")).lower() == username.lower() for u in users):
        raise HTTPException(status_code=409, detail="Username already exists")
    salt, password_hash = _hash_app_password(password)
    users.append({"username": username, "role": role, "enabled": True, "salt": salt, "password_hash": password_hash, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    _save_app_users(users)
    _audit("Application user created", "AUTH", user["username"], f"Created {username} ({role})", username)
    return {"success": True, "username": username, "role": role}



@app.put("/auth/users/{username}/password")
def change_app_user_password(username: str, payload: dict, user=Depends(_current_app_user)):
    _require_admin(user)
    username = str(username).strip()
    new_password = str(payload.get("password", ""))
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must contain at least 6 characters")
    users = _load_app_users()
    target = next((u for u in users if str(u.get("username","")).casefold() == username.casefold()), None)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    salt, password_hash = _hash_app_password(new_password)
    target["salt"] = salt
    target["password_hash"] = password_hash
    _save_app_users(users)
    _audit("Application user password changed", "AUTH", user["username"], f"Changed password for {username}", username)
    return {"success": True, "username": username}

@app.delete("/auth/users/{username}")
def delete_app_user(username: str, user=Depends(_current_app_user)):
    _require_admin(user)
    username = str(username).strip()
    if username.lower() == str(user["username"]).lower():
        raise HTTPException(status_code=400, detail="You cannot delete your own administrator account")
    users = _load_app_users()
    kept = [u for u in users if str(u.get("username", "")).lower() != username.lower()]
    if len(kept) == len(users):
        raise HTTPException(status_code=404, detail="User not found")
    _save_app_users(kept)
    _audit("Application user deleted", "AUTH", user["username"], f"Deleted {username}", username)
    return {"success": True}


# ==========================================================
# DASHBOARD
#
# IMPORTANT:
# This endpoint ONLY reads the cache.
# It NEVER scans the NVRs.
# ==========================================================

@app.get("/dashboard")
def dashboard():

    snapshot = (
        crud.get_dashboard_snapshot()
    )

    return snapshot


# ==========================================================
# CAMERAS
#
# Python 3.8 compatible.
# ==========================================================

@app.get(
    "/cameras",
    response_model=List[CameraResponse],
)
def get_cameras():

    return crud.get_cached_cameras(
        online_only=True
    )


# ==========================================================
# CREATE CAMERA
# ==========================================================

@app.post(
    "/cameras",
    response_model=CameraResponse,
)
def create_camera(
    camera: CameraCreate,
    db: Session = Depends(get_db)
):

    created = crud.create_camera(
        db,
        camera
    )

    return created


# ==========================================================
# NVR STATUS
# ==========================================================


@app.put("/nvr/{nvr_id}/name")
def rename_nvr(nvr_id: int, payload: dict, user=Depends(_current_app_user)):
    _require_admin(user)
    new_name = str(payload.get("name", "")).strip()
    if not new_name or len(new_name) > 80:
        raise HTTPException(status_code=400, detail="NVR name is required (1-80 characters)")
    target = next((n for n in NVRS if int(n.get("id")) == int(nvr_id)), None)
    if not target:
        raise HTTPException(status_code=404, detail="NVR not found")
    old_name = str(target.get("name", f"NVR-{nvr_id}"))
    if any(int(n.get("id")) != int(nvr_id) and str(n.get("name","")).casefold() == new_name.casefold() for n in NVRS):
        raise HTTPException(status_code=409, detail="NVR name already exists")
    target["name"] = new_name
    registry = Path(__file__).parent / "nvr_name_registry.json"
    try:
        data = json.loads(registry.read_text(encoding="utf8")) if registry.exists() else {}
        if not isinstance(data, dict): data = {}
        data[str(nvr_id)] = new_name
        registry.write_text(json.dumps(data, indent=2), encoding="utf8")
    except Exception as exc:
        print(f"⚠️ NVR name registry save error: {exc}")
    _audit("NVR name changed", "NVR", old_name, f"Renamed to {new_name}", user["username"])
    return {"success": True, "id": nvr_id, "old_name": old_name, "name": new_name}

@app.get("/nvr/status")
def nvr_status():

    return crud.get_cached_nvr_status()


# ==========================================================
# STORAGE
#
# Reads real HDD telemetry from every configured NVR.
# ==========================================================

@app.get("/storage")
def storage():

    return storage_snapshot(force=False)


@app.get("/storage/refresh")
def storage_refresh():

    return storage_snapshot(force=True)


@app.get("/nvr/health")
def nvr_health(force: bool = False):
    data = get_health(force=force)
    return {"data": data, "configured_nvrs": len(NVRS), "insights": get_health_insights(data), "thresholds": {"cpu_warn": 75, "cpu_critical": 90, "memory_warn": 80, "memory_critical": 90, "temperature_warn": 70, "temperature_critical": 80, "disk_warn": 90, "disk_critical": 98}}


@app.get("/nvr/health/history")
def nvr_health_history(nvr: str = "", minutes: int = 60, limit: int = 720):
    return {"data": get_health_history(nvr_name=nvr or None, minutes=max(1, min(minutes, 1440)), limit=max(1, min(limit, 5000)))}


@app.get("/nvr/diagnostics")
def nvr_diagnostics():
    health = get_health(force=False)
    online = sum(1 for x in health if x.get("status") == "ONLINE")
    return {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "backend": {"status": "UP", "service": "VisionGuard AI", "version": "3.9.5 Health Intelligence"},
        "nvr": {"total": len(health), "online": online, "offline": len(health) - online},
        "health_engine": {"status": "RUNNING", "poll_seconds": 5},
        "recording_monitor": {"status": "RUNNING"},
        "camera_monitor": {"status": "RUNNING"},
        "storage_monitor": {"status": "RUNNING"},
        "alert_engine": {"status": "RUNNING"},
        "latency": [{"name": x.get("name"), "status": x.get("status"), "latency_ms": x.get("latency_ms")} for x in health],
        "insights": get_health_insights(health),
    }


@app.get("/analytics/summary")
def analytics_summary():
    """Live aggregate telemetry for the Analytics dashboard."""
    import json
    from .ip_conflict_checker import get_conflict_count, get_conflict_ips
    from .recording_monitor import get_statistics
    try:
        snapshot = crud.get_dashboard_snapshot()
        alert_data = []
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                alert_data = json.load(f)[-100:]
        recording_stats = get_statistics()
        try:
            storage_data = storage_snapshot(force=False).get("data", [])
        except Exception:
            storage_data = []
        movement = camera_movement_summary()
        try:
            angle = get_camera_angle_summary()
        except Exception:
            angle = {}
        return {
            "overview": {
                "total_cameras": snapshot.get("total", 0),
                "online_cameras": snapshot.get("online", 0),
                "offline_cameras": snapshot.get("offline", 0),
                "total_nvrs": snapshot.get("total_nvr", len(NVRS)),
                "online_nvrs": snapshot.get("online_nvr", 0),
                "offline_nvrs": snapshot.get("offline_nvr", 0),
                "cache_ready": snapshot.get("cache_ready", False),
                "last_update": snapshot.get("last_update"),
            },
            "nvr_health": snapshot.get("nvr_status", []),
            "recent_alerts": list(reversed(alert_data[-30:])),
            "recording": {
                "active_losses": recording_stats.get("active_losses", 0),
                "history": recording_stats.get("history", 0),
                "pending": recording_stats.get("pending", 0),
                "threshold_seconds": recording_stats.get("threshold", 300),
                "running": recording_stats.get("running", False),
            },
            "storage": storage_data,
            "movement": movement,
            "angle": angle,
            "ip_conflicts": {"count": get_conflict_count(), "ips": get_conflict_ips()},
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analytics aggregation failed: {exc}")


@app.get("/alerts")
def alerts():
    try:
        if HISTORY_FILE.exists():
            import json
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            start = max(0, len(data) - 500)
            return [dict(item, _index=i) for i, item in enumerate(data[start:], start=start)]
    except Exception as exc:
        print(f"Alert history read error: {exc}")
    return []


@app.get("/audit")
def audit_log(limit: int = 500):
    try:
        if os.path.exists(AUDIT_FILE):
            with open(AUDIT_FILE, "r", encoding="utf-8") as f:
                rows = json.load(f) or []
            return list(reversed(rows[-max(1, min(limit, 5000)):]))
    except Exception as exc:
        print(f"[AUDIT] read error: {exc}")
    return []


@app.post("/audit")
def create_audit(payload: dict):
    _audit(str(payload.get("action", "Event")), str(payload.get("category", "SYSTEM")), str(payload.get("actor", "User")), str(payload.get("details", "")), str(payload.get("target", "")))
    return {"status": "recorded"}


@app.post("/alerts/{alert_index}/acknowledge")
def acknowledge_alert(alert_index: int, payload: dict = None):
    try:
        if not HISTORY_FILE.exists():
            raise HTTPException(status_code=404, detail="Alert history not found")
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f) or []
        if alert_index < 0 or alert_index >= len(data):
            raise HTTPException(status_code=404, detail="Alert not found")
        alert = data[alert_index]
        actor = (payload or {}).get("actor", "Operator")
        alert["status"] = "ACKNOWLEDGED"
        alert["acknowledged_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        alert["acknowledged_by"] = actor
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _audit("Alert acknowledged", "ALERT", actor=actor, target=alert.get("title") or alert.get("type") or "Alert", details=alert.get("description", ""))
        return alert
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to acknowledge alert: {exc}")


# ----------------------------------------------------------
# NVR SETTINGS / ISAPI
# ----------------------------------------------------------

def _get_nvr(nvr_id: int):
    for nvr in NVRS:
        if int(nvr.get("id")) == int(nvr_id):
            return nvr
    raise HTTPException(status_code=404, detail="NVR not found")


def _nvr_request(nvr, method, endpoint, body=None):
    if not endpoint.startswith("/ISAPI/"):
        raise HTTPException(status_code=400, detail="Only /ISAPI/* endpoints are allowed")
    if any(x in endpoint.lower() for x in ("factoryreset", "updatefirmware", "configurationdata")):
        raise HTTPException(status_code=403, detail="This destructive endpoint is disabled from the web UI")
    try:
        r = requests.request(
            method,
            f"http://{nvr['ip']}:{nvr['port']}{endpoint}",
            auth=HTTPDigestAuth(nvr["username"], nvr["password"]),
            data=body.encode("utf-8") if isinstance(body, str) else body,
            headers={"Accept": "application/xml", "Content-Type": "application/xml"},
            timeout=10,
        )
        if not r.ok:
            raise HTTPException(status_code=r.status_code, detail=r.text[:1000] or "NVR rejected request")
        return {"status": r.status_code, "content_type": r.headers.get("content-type", ""), "body": r.text}
    except HTTPException:
        raise
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"NVR connection failed: {exc}")


@app.get("/nvr/{nvr_id}/settings")
def nvr_settings(nvr_id: int, section: str = "device", endpoint: str = ""):
    nvr = _get_nvr(nvr_id)
    endpoints = {
        "device": "/ISAPI/System/deviceInfo",
        "time": "/ISAPI/System/time",
        "network": "/ISAPI/System/Network/interfaces",
        "capabilities": "/ISAPI/System/capabilities",
    }
    if section == "advanced":
        endpoint = endpoint or "/ISAPI/System/deviceInfo"
        if not endpoint.startswith("/ISAPI/"):
            raise HTTPException(status_code=400, detail="Only /ISAPI/* endpoints are allowed")
    else:
        endpoint = endpoints.get(section)
    if not endpoint:
        raise HTTPException(status_code=400, detail="Unsupported settings section")
    return _nvr_request(nvr, "GET", endpoint)


@app.put("/nvr/{nvr_id}/settings")
def update_nvr_settings(nvr_id: int, payload: dict):
    nvr = _get_nvr(nvr_id)
    endpoint = str(payload.get("endpoint", ""))
    xml = payload.get("xml", "")
    if not xml:
        raise HTTPException(status_code=400, detail="XML payload is required")
    result = _nvr_request(nvr, "PUT", endpoint, xml)
    add_alert("NVR Settings", "INFO", f"{nvr['name']} Settings Changed", f"Updated {endpoint}")
    _audit("NVR settings updated", "NVR", target=nvr["name"], details=endpoint)
    return result


@app.put("/nvr/bulk/settings")
def update_bulk_nvr_settings(payload: dict):
    """Apply one prepared ISAPI XML payload per selected NVR.

    The frontend prepares each NVR's XML independently so unique values such as
    IP addresses are never accidentally copied from one recorder to another.
    """
    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="No NVRs selected")

    results = []
    for item in items:
        try:
            nvr_id = int(item.get("nvr_id"))
            endpoint = str(item.get("endpoint", ""))
            xml = item.get("xml", "")
            nvr = _get_nvr(nvr_id)
            if not xml:
                raise ValueError("XML payload is empty")
            result = _nvr_request(nvr, "PUT", endpoint, xml)
            results.append({
                "nvr_id": nvr_id,
                "nvr": nvr.get("name"),
                "success": True,
                "status": result.get("status"),
                "endpoint": endpoint,
            })
            add_alert(
                "NVR SETTINGS",
                "INFO",
                f"{nvr['name']} Settings Changed",
                f"Bulk update applied to {endpoint}",
            )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                detail = exc.detail
            else:
                detail = str(exc)
            results.append({
                "nvr_id": item.get("nvr_id"),
                "nvr": item.get("name", f"NVR-{item.get('nvr_id', '?')}"),
                "success": False,
                "error": detail,
                "endpoint": item.get("endpoint", ""),
            })

    succeeded = sum(1 for r in results if r.get("success"))
    _audit("Bulk NVR settings update", "NVR", details=f"{succeeded}/{len(results)} succeeded")
    return {
        "success": succeeded == len(results),
        "total": len(results),
        "succeeded": succeeded,
        "failed": len(results) - succeeded,
        "results": results,
    }


@app.post("/nvr/{nvr_id}/reboot")
def reboot_nvr(nvr_id: int):
    nvr = _get_nvr(nvr_id)
    result = _nvr_request(nvr, "PUT", "/ISAPI/System/reboot", "")
    add_alert("NVR Settings", "WARNING", f"{nvr['name']} Reboot Requested", "NVR reboot command was sent from Settings.")
    _audit("NVR reboot requested", "NVR", target=nvr["name"], details="/ISAPI/System/reboot")
    return result


# ==========================================================
# NVR RAW
# ==========================================================

@app.get(
    "/nvr/raw",
    response_class=PlainTextResponse,
)
def nvr_raw():

    output = ""

    for nvr in NVRS:

        output += (
            "\n========== "
            f"{nvr['name']}"
            " ==========\n"
        )

        try:

            response = requests.get(
                f"http://"
                f"{nvr['ip']}:"
                f"{nvr['port']}"
                "/ISAPI/ContentMgmt/"
                "InputProxy/channels",
                auth=HTTPDigestAuth(
                    nvr["username"],
                    nvr["password"],
                ),
                timeout=10,
            )

            output += response.text

        except Exception as e:

            output += str(e)

    return output


# ==========================================================
# WHATSAPP ALERT SETTINGS
# ==========================================================

@app.get("/whatsapp/config")
def whatsapp_config(user=Depends(_current_app_user)):
    _require_admin(user)
    return get_whatsapp_config(mask_secrets=True)

@app.put("/whatsapp/config")
def update_whatsapp_config(payload: dict, user=Depends(_current_app_user)):
    _require_admin(user)
    cfg = save_whatsapp_config(payload)
    _audit("WhatsApp alert settings updated", "ALERT", user["username"], f"WhatsApp alerts {'enabled' if cfg.get('enabled') else 'disabled'}", cfg.get("to", ""))
    return get_whatsapp_config(mask_secrets=True)

@app.post("/whatsapp/test")
def test_whatsapp(user=Depends(_current_app_user)):
    _require_admin(user)
    ok = send_whatsapp_alert("VisionGuard AI\nTEST ALERT\nWhatsApp alert delivery is working.")
    if not ok:
        raise HTTPException(status_code=400, detail="WhatsApp test failed. Check Meta Cloud API token, Phone Number ID, recipient number and template/session policy.")
    return {"success": True}


# ==========================================================
# ENTERPRISE NVR USERS
# ==========================================================

@app.get("/nvr/users")
def get_all_nvr_users():
    return {"configured_nvrs": len(NVRS), "nvrs": nvr_users()}



@app.post("/nvr/users/bulk-create")
def bulk_create_nvr_user(payload: dict, user=Depends(_current_app_user)):
    _require_admin(user)
    nvr_ids = list(dict.fromkeys(int(x) for x in (payload.get("nvr_ids") or [])))
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "Viewer")).strip() or "Viewer"
    if not nvr_ids or not username or len(password) < 6:
        raise HTTPException(status_code=400, detail="Select NVRs, username, and a password of at least 6 characters")
    if role not in {"Administrator", "Operator", "Viewer"}:
        raise HTTPException(status_code=400, detail="Invalid role")

    from xml.sax.saxutils import escape
    results = []
    for nvr_id in nvr_ids:
        try:
            nvr = _get_nvr(nvr_id)

            # Hikvision's ISAPI user-create schema is a single <User> object.
            # The older Enterprise build used the Hikvision namespace and an
            # <enabled> node, which causes many NVR firmware versions to reject
            # the request.  Use the documented ISAPI namespace and include the
            # optional bond list for broad firmware compatibility.
            body = (
                '<User version="2.0" xmlns="http://www.isapi.org/ver20/XMLSchema">'
                '<id>0</id>'
                f'<userName>{escape(username)}</userName>'
                f'<password>{escape(password)}</password>'
                '<bondIpAddressList><bondIpAddress><id>1</id>'
                '<ipAddress>0.0.0.0</ipAddress><ipv6Address>::</ipv6Address>'
                '</bondIpAddress></bondIpAddressList>'
                f'<userLevel>{escape(role)}</userLevel>'
                '<attribute><inherent>false</inherent></attribute>'
                '</User>'
            )
            result = _nvr_request(nvr, "POST", "/ISAPI/Security/users", body)
            results.append({"success": True, "nvr_id": nvr_id, "nvr": nvr["name"], "username": username, "status": result.get("status")})
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            results.append({"success": False, "nvr_id": nvr_id, "nvr": _get_nvr(nvr_id).get("name", f"NVR-{nvr_id}"), "error": str(detail)[:800]})

    ok = sum(1 for x in results if x["success"])
    _audit("Bulk NVR user creation", "SECURITY", user["username"], f"Created {username} on {ok}/{len(results)} NVRs", username)
    return {"success": ok == len(results), "total": len(results), "succeeded": ok, "failed": len(results) - ok, "results": results}

@app.post("/nvr/users/bulk-delete")
def bulk_delete_nvr_user(payload: dict, user=Depends(_current_app_user)):
    _require_admin(user)
    items=payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="No NVR users selected")
    results=[]
    for item in items:
        try:
            nvr=_get_nvr(int(item.get("nvr_id")))
            user_id=str(item.get("user_id") or "")
            if not user_id: raise ValueError("User ID is required")
            result=_nvr_request(nvr,"DELETE",f"/ISAPI/Security/users/{user_id}")
            if int(result.get("status",0)) >= 300:
                raise RuntimeError(f"HTTP {result.get('status')}: {result.get('body','')[:300]}")
            results.append({"success":True,"nvr_id":nvr["id"],"nvr":nvr["name"],"user_id":user_id})
        except Exception as exc:
            results.append({"success":False,"nvr_id":item.get("nvr_id"),"nvr":item.get("nvr"),"user_id":item.get("user_id"),"error":str(exc)})
    ok=sum(1 for x in results if x["success"])
    _audit("Bulk NVR user deletion","SECURITY",user["username"],f"Deleted {ok}/{len(results)} NVR user entries")
    return {"success":ok==len(results),"total":len(results),"succeeded":ok,"failed":len(results)-ok,"results":results}

@app.put("/nvr/users/bulk-update")
def bulk_update_nvr_users(payload: dict):
    """Apply safe user account changes to selected NVR accounts.
    Supported changes: enabled and userLevel/role. Password changes are intentionally excluded.
    """
    items = payload.get("items") or []
    if not items:
        raise HTTPException(status_code=400, detail="No users selected")
    results = []
    for item in items:
        try:
            nvr = _get_nvr(int(item.get("nvr_id")))
            user_id = str(item.get("user_id"))
            if not user_id:
                raise ValueError("User ID is required")
            response = _nvr_request(nvr, "GET", f"/ISAPI/Security/users/{user_id}")
            root = __import__("xml.etree.ElementTree", fromlist=["ElementTree"]).fromstring(response["body"])
            changes = item.get("changes") or {}
            for key in ("enabled", "enable"):
                if key in changes:
                    nodes = root.findall(".//{*}" + key)
                    if nodes:
                        nodes[0].text = "true" if bool(changes[key]) else "false"
                    else:
                        node = ET.SubElement(root, key); node.text = "true" if bool(changes[key]) else "false"
            if "role" in changes or "userLevel" in changes:
                raw_role = str(changes.get("role", changes.get("userLevel"))).strip().lower()
                role_map = {
                    "admin": "Administrator",
                    "administrator": "Administrator",
                    "operator": "Operator",
                    "viewer": "Viewer",
                }
                value = role_map.get(raw_role, str(changes.get("role", changes.get("userLevel"))))
                nodes = root.findall(".//{*}userLevel") or root.findall(".//{*}role")
                if nodes: nodes[0].text = value
            body = ET.tostring(root, encoding="unicode")
            result = _nvr_request(nvr, "PUT", f"/ISAPI/Security/users/{user_id}", body)
            add_alert("NVR USER SETTINGS", "INFO", f"User settings changed - {nvr['name']}", f"User ID {user_id}")
            results.append({"success": True, "nvr_id": nvr["id"], "nvr": nvr["name"], "user_id": user_id, "status": result.get("status")})
        except Exception as exc:
            results.append({"success": False, "nvr_id": item.get("nvr_id"), "nvr": item.get("nvr"), "user_id": item.get("user_id"), "error": str(exc)})
    ok = sum(1 for x in results if x["success"])
    return {"success": ok == len(results), "total": len(results), "succeeded": ok, "failed": len(results)-ok, "results": results}


@app.get("/nvr/users/summary")
def get_nvr_user_summary():
    data = nvr_users()
    return {
        "total_users": sum(int(item.get("user_count", 0)) for item in data),
        "online_nvrs": sum(1 for item in data if item.get("status") == "ONLINE"),
        "configured_nvrs": len(NVRS),
        "nvrs": data,
    }


# ==========================================================
# ENTERPRISE CAMERA MANAGEMENT
# ==========================================================

@app.post("/cameras/bulk-update")
def bulk_update_cameras(payload: dict):
    cameras = payload.get("cameras") or []
    changes = payload.get("changes") or {}
    if not cameras:
        raise HTTPException(status_code=400, detail="No cameras selected")
    if not changes:
        raise HTTPException(status_code=400, detail="No changes supplied")
    results = []
    errors = []
    for item in cameras:
        try:
            result = update_camera(str(item.get("nvr")), int(item.get("id")), changes)
            results.append(result)
        except Exception as exc:
            errors.append({"nvr": item.get("nvr"), "id": item.get("id"), "error": str(exc)})
    _audit("Bulk camera settings update", "CAMERA", details=f"{len(results)} updated, {len(errors)} failed; changes={list(changes.keys())}")
    return {"success": not errors, "updated": len(results), "failed": len(errors), "results": results, "errors": errors}


@app.post("/cameras/{nvr_name}/{channel_id}/settings")
def update_single_camera(nvr_name: str, channel_id: int, payload: dict):
    changes = payload.get("changes") or payload
    try:
        result = update_camera(nvr_name, channel_id, changes)
        _audit("Camera settings updated", "CAMERA", target=f"{nvr_name} CH-{channel_id}", details=str(list(changes.keys())))
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ==========================================================
# CAMERA NVR MOVEMENT HISTORY
# ==========================================================

@app.get("/camera-movements")
def camera_movements(limit: int = 500):
    return {"history": get_camera_movement_history(limit), "summary": camera_movement_summary()}


# ==========================================================
# RECORDING LOSS
# ==========================================================

@app.get("/recording-loss/statistics")
def recording_loss_statistics():
    from .recording_monitor import get_statistics
    return get_statistics()


@app.get("/ip-conflicts")
def ip_conflicts():
    from .ip_conflict_checker import get_conflict_count, get_conflict_ips, active_conflicts
    return {"count": get_conflict_count(), "ips": get_conflict_ips(), "active": list(active_conflicts)}


@app.get("/recording-loss")
def recording_loss():

    return {
        "active":
            get_active_recording_losses(),

        "history":
            get_recording_loss_history(),
    }


# ==========================================================
# CAMERA ANGLE STATUS
# ==========================================================

@app.get(
    "/camera-angle/status"
)
def camera_angle_status():

    return get_camera_angle_status()


# ==========================================================
# CAMERA ANGLE SUMMARY
# ==========================================================

@app.get(
    "/camera-angle/summary"
)
def camera_angle_summary():

    return get_camera_angle_summary()


# ==========================================================
# APPLICATION INFO
# ==========================================================

@app.get("/api/info")
def application_info():

    snapshot = (
        crud.get_dashboard_snapshot()
    )

    return {

        "application":
            "VisionGuard AI",

        "version":
            "3.2 Enterprise",

        "status":
            "running",

        "nvrs":
            snapshot.get(
                "online_nvr",
                0
            ),

        "configured_nvrs":
            len(NVRS),

        "features": [

            "Video Loss Monitoring",

            "Video Recovery Detection",

            "Hikvision Event Listener",

            "Recording Loss Detection",

            "Recording Recovery Detection",

            "Live RTSP Streaming",

            "Camera Management",

            "NVR Status Monitoring",

            "Recording Loss History",

            "Background Camera Discovery",

            "Camera Status Cache",

            "Camera Angle Change Detection",
        ],
    }


# ==========================================================
# V9 BULK CAMERA VIDEO CONFIGURATION
# ==========================================================
@app.post("/v9/cameras/bulk-video-config")
def v9_bulk_video_config(payload: dict):
    cameras = payload.get("cameras") or []
    changes = payload.get("changes") or {}
    streams = tuple(payload.get("streams") or (1, 2))
    dry_run = bool(payload.get("dry_run", False))
    if not cameras:
        raise HTTPException(400, "No cameras selected")
    if not changes:
        raise HTTPException(400, "No video changes supplied")
    result = apply_bulk_camera_encoding(cameras, changes, streams=streams, dry_run=dry_run)
    ok = sum(1 for x in result if x.get("success"))
    return {"success": ok == len(result), "updated": ok, "failed": len(result)-ok, "results": result}

@app.post("/v9/nvrs/bulk-video-config")
def v9_bulk_nvr_video_config(payload: dict):
    selected = {str(x).casefold() for x in (payload.get("nvrs") or [])}
    changes = payload.get("changes") or {}
    streams = tuple(payload.get("streams") or (1, 2))
    dry_run = bool(payload.get("dry_run", False))
    if not selected: raise HTTPException(400, "No NVRs selected")
    cams = [c for c in crud.get_cached_cameras(online_only=False) if str(c.get("nvr","")).casefold() in selected]
    if not cams: raise HTTPException(404, "No discovered cameras found for selected NVRs")
    result = apply_bulk_camera_encoding(cams, changes, streams=streams, dry_run=dry_run)
    ok=sum(1 for x in result if x.get("success"))
    _audit("Bulk camera encoding update", "CAMERA", details=f"{ok}/{len(result)} operations succeeded; changes={list(changes.keys())}")
    return {"success": ok == len(result), "cameras": len(cams), "updated": ok, "failed": len(result)-ok, "results": result}

@app.get("/v9/nvrs/audit")
def v9_nvr_audit():
    return {"generated_at": datetime.now().isoformat(), "nvrs": audit_all_nvrs()}

@app.get("/v9/predictive-risk")
def v9_predictive_risk():
    return risk_snapshot()


@app.post("/v9/password-recovery/start")
def v9_password_recovery_start(payload: dict):
    nvr_name = str(payload.get("nvr_name") or "").strip()
    if not nvr_name:
        raise HTTPException(status_code=400, detail="NVR name is required.")
    nvr = next((x for x in NVRS if str(x.get("name", "")).lower() == nvr_name.lower()), None)
    if not nvr:
        raise HTTPException(status_code=404, detail=f"NVR not found: {nvr_name}")
    session = create_recovery_session(nvr)
    _audit("NVR password recovery started", "SECURITY", nvr_name,
           f"Official Hikvision Reserved Email workflow; recovery mailbox={RECOVERY_EMAIL}", "VisionGuard")
    return {"success": True, **session,
            "nvr_login_url": f"http://{nvr.get('ip')}:{nvr.get('port',80)}",
            "hikvision_recovery_email": HIKVISION_RECOVERY_EMAIL,
            "message": "Open the NVR login page, choose Forgot Password → Verify by Reserved Email, export the QR, then send it to Hikvision."}

@app.post("/v9/password-recovery/send-qr")
async def v9_password_recovery_send_qr(session_id: str, qr_file: UploadFile = File(...)):
    try:
        session=get_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    name=qr_file.filename or "recovery_qr"
    suffix=Path(name).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".bmp", ".zip"}:
        raise HTTPException(status_code=400, detail="Export the Hikvision recovery QR as PNG/JPG/BMP (or the device export ZIP).")
    tmp=Path(tempfile.gettempdir()) / f"visionguard_recovery_{secrets.token_hex(8)}{suffix}"
    try:
        data=await qr_file.read()
        if len(data) > 10*1024*1024:
            raise HTTPException(status_code=413, detail="Recovery file is too large (10 MB max).")
        tmp.write_bytes(data)
        send_hikvision_recovery_qr(attachment_path=str(tmp), nvr_name=session.get("nvr_name","NVR"), nvr_ip=session.get("ip",""))
        mark_qr_submitted(session_id)
        _audit("Hikvision recovery QR relayed", "SECURITY", session.get("nvr_name"),
               "Recovery QR sent to pw_recovery@hikvision.com", "VisionGuard")
        return {"success":True,"status":"HIKVISION_RECOVERY_REQUEST_SENT",
                "message":f"Recovery QR sent to Hikvision. Check {RECOVERY_EMAIL} for the verification code."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to relay recovery QR: {exc}")
    finally:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass

@app.post("/v9/password-recovery/qr-submitted")
def v9_password_recovery_qr_submitted(payload: dict):
    sid=str(payload.get("session_id") or "").strip()
    try:
        result=mark_qr_submitted(sid)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"success":True, **result,
            "message": f"QR submitted. Check {RECOVERY_EMAIL} for the Hikvision verification code."}

@app.post("/v9/password-recovery/submit-code")
def v9_password_recovery_submit_code(payload: dict):
    sid=str(payload.get("session_id") or "").strip()
    code=str(payload.get("verification_code") or "").strip()
    try:
        result=record_hikvision_code(sid, code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    _audit("Hikvision recovery code entered", "SECURITY", result["nvr"].get("nvr_name"),
           "Verification code entered in VisionGuard recovery workflow", "VisionGuard")
    return {"success":True, **result,
            "message":"Code captured. Hikvision must validate it on the official NVR recovery page; VisionGuard does not locally validate or forge reset codes."}

@app.get("/v9/password-recovery/{nvr_name}")
def v9_password_recovery(nvr_name: str):
    return supported_recovery_workflow(nvr_name)

@app.get("/v9/camera-angle/baselines")
def v9_angle_baselines():
    from .camera_angle_monitor import BASELINE_DIR, _STATE
    rows=[]
    for key, item in (_STATE.get("cameras") or {}).items():
        rows.append({"key":key,"camera":item.get("camera"),"nvr":item.get("nvr"),"channel":item.get("channel"),"baseline":item.get("baseline"),"baseline_set_at":item.get("baseline_set_at"),"last_frame_at":item.get("last_frame_at"),"last_score":item.get("last_score")})
    return {"count":len(rows),"baselines":rows}

# ==========================================================
# END OF MAIN.PY
# ==========================================================

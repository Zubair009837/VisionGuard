# ==========================================================
# VisionGuard AI - NVR Outage / Recovery Monitor
# ==========================================================
import threading
import time
import requests
from requests.auth import HTTPDigestAuth
from pathlib import Path
import json

from .config import NVRS, ALERT_DELAY_SECONDS
from . import crud
from .email_service import send_nvr_offline_email, send_nvr_recovery_email
from .whatsapp_service import send_whatsapp_event

STATE_FILE = Path(__file__).parent / "nvr_outage_state.json"
_LOCK = threading.RLock()
_STOP = threading.Event()
_THREAD = None
_STATE = {}

def _load():
    global _STATE
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf8"))
            if isinstance(data, dict): _STATE = data
    except Exception as exc:
        print(f"⚠️ NVR outage state load error: {exc}")

def _save():
    try:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_STATE, indent=2), encoding="utf8")
        tmp.replace(STATE_FILE)
    except Exception as exc:
        print(f"⚠️ NVR outage state save error: {exc}")

def _cameras_for(nvr):
    name = str(nvr.get("name",""))
    try:
        return [dict(c) for c in crud.get_cached_cameras(online_only=False)
                if str(c.get("nvr","")).casefold() == name.casefold()]
    except Exception:
        return []

def _probe(nvr):
    try:
        url = f"http://{nvr['ip']}:{nvr.get('port',80)}/"
        r = requests.get(url, auth=HTTPDigestAuth(nvr["username"], nvr["password"]),
                         timeout=5)
        # Any HTTP response proves network reachability; authentication failure
        # is not the same as a dead NVR.
        return True, r.status_code
    except Exception as exc:
        return False, str(exc)

def scan_once():
    for nvr in NVRS:
        key = str(nvr.get("id"))
        online, detail = _probe(nvr)
        cameras = _cameras_for(nvr)
        now = time.time()
        with _LOCK:
            old = _STATE.get(key, {"status":"UNKNOWN"})
            old_status = old.get("status")
            if online:
                if old_status == "OFFLINE" and old.get("alert_sent"):
                    event_time = time.strftime("%d-%m-%Y %I:%M:%S %p")
                    try:
                        send_nvr_recovery_email(nvr=nvr.get("name"), cameras=cameras, event_time=event_time)
                    except Exception as exc: print(f"⚠️ NVR recovery email error: {exc}")
                    send_whatsapp_event(
                        f"{nvr.get('name')} RECOVERED",
                        f"IP: {nvr.get('ip')}\nCameras restored: {len(cameras)}",
                        "RECOVERY",
                    )
                _STATE[key] = {"status":"ONLINE","since":now,"alert_sent":False}
            else:
                if old_status != "OFFLINE":
                    _STATE[key] = {"status":"OFFLINE","since":now,"alert_sent":False,"detail":str(detail)}
                elif not old.get("alert_sent") and now - float(old.get("since",now)) >= ALERT_DELAY_SECONDS:
                    event_time = time.strftime("%d-%m-%Y %I:%M:%S %p")
                    try:
                        send_nvr_offline_email(nvr=nvr.get("name"), cameras=cameras, event_time=event_time)
                    except Exception as exc: print(f"⚠️ NVR offline email error: {exc}")
                    send_whatsapp_event(
                        f"{nvr.get('name')} OFFLINE",
                        f"IP: {nvr.get('ip')}\nCameras affected: {len(cameras)}\nNVR ID: {nvr.get('id')}",
                        "CRITICAL",
                    )
                    _STATE[key]["alert_sent"] = True
            _STATE[key]["last_check"] = time.time()
    _save()

def _worker():
    _load()
    while not _STOP.is_set():
        try: scan_once()
        except Exception as exc: print(f"⚠️ NVR outage monitor error: {exc}")
        _STOP.wait(10)

def start_nvr_outage_monitor():
    global _THREAD
    if _THREAD and _THREAD.is_alive(): return
    _STOP.clear()
    _THREAD = threading.Thread(target=_worker, name="VisionGuard-NVR-Outage", daemon=True)
    _THREAD.start()
    print("✓ NVR Outage/Recovery Monitor Started")

def stop_nvr_outage_monitor():
    _STOP.set()

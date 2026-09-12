# ==========================================================
# VisionGuard AI - Automatic PTZ Discovery & Position Monitor
# ==========================================================
"""Automatically discovers PTZ cameras across all configured NVRs.

The monitor prefers the camera's own ISAPI interface because many Hikvision
NVRs do not expose PTZ capability/status for an IP camera through the NVR's
PTZCtrl endpoint. It falls back to the NVR channel endpoint when available.

Only cameras with a confirmed PTZ capability are monitored. Fixed cameras are
ignored. The first successful PTZ position becomes the persistent baseline.
"""

import json
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests
from requests.auth import HTTPDigestAuth

from .config import NVRS, PTZ_MONITOR_INTERVAL_SECONDS, PTZ_CONFIRM_READINGS, PTZ_POSITION_TOLERANCE
from .email_service import send_ptz_position_changed_email

STATE_FILE = Path(__file__).parent / "ptz_state.json"
HISTORY_FILE = Path(__file__).parent / "alert_history.json"

_LOCK = threading.RLock()
_STOP = threading.Event()
_THREAD = None

# Runtime state is persisted so a backend restart does not create a fresh
# baseline and lose the previous monitored position.
_state = {
    "cameras": {},
    "last_scan": None,
}


def _camera_key(camera):
    return f"{camera.get('nvr','')}|{camera.get('id','')}|{camera.get('ip','')}"


def _now():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _load_state():
    global _state
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _state.update(data)
    except Exception as exc:
        print(f"⚠️ PTZ state load error: {exc}")


def _save_state():
    try:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_state, indent=2), encoding="utf-8")
        tmp.replace(STATE_FILE)
    except Exception as exc:
        print(f"⚠️ PTZ state save error: {exc}")


def _request_xml(url, username, password, timeout=5):
    try:
        response = requests.get(
            url,
            auth=HTTPDigestAuth(username, password),
            timeout=timeout,
        )
        if response.status_code == 200 and response.text.strip():
            return ET.fromstring(response.text), response.status_code
        return None, response.status_code
    except Exception as exc:
        return None, None


def _camera_urls(camera, nvr, path):
    """Return direct-camera URL first, then NVR channel URL fallback."""
    ip = str(camera.get("ip") or "").strip()
    urls = []
    if ip:
        # Hikvision IP cameras normally expose ISAPI on HTTP/80.
        urls.append((f"http://{ip}:80{path}", camera.get("username") or nvr["username"], camera.get("password") or nvr["password"]))
        urls.append((f"https://{ip}:443{path}", camera.get("username") or nvr["username"], camera.get("password") or nvr["password"]))

    channel = camera.get("id")
    if channel is not None:
        urls.append((
            f"http://{nvr['ip']}:{nvr['port']}/ISAPI/PTZCtrl/channels/{channel}{path}",
            nvr["username"], nvr["password"],
        ))
    return urls


def _truthy(text):
    return str(text or "").strip().lower() in {"true", "1", "yes"}


def _has_ptz_capability(root):
    if root is None:
        return False

    # Official Hikvision ISAPI PTZ capability indicators.
    support = root.find(".//{*}isSupportPTZCtrlStatus")
    if support is not None and _truthy(support.text):
        return True

    if root.find(".//{*}AbsolutePanTiltPositionSpace") is not None:
        return True

    if root.find(".//{*}azimuth") is not None or root.find(".//{*}elevation") is not None:
        return True

    # Some firmware returns a PTZAbility/control list instead of the newer
    # PTZChanelCap schema.
    control = root.find(".//{*}PTZControl")
    if control is not None:
        for node in control.iter():
            text = (node.text or "").strip().lower()
            attr = " ".join(str(v).lower() for v in node.attrib.values())
            if any(word in text or word in attr for word in ("pan", "tilt", "zoomin", "zoomout")):
                return True

    return False


def _find_number(root, names):
    if root is None:
        return None
    wanted = {n.lower() for n in names}
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag in wanted and node.text:
            try:
                return float(node.text.strip())
            except ValueError:
                pass
    return None


def _parse_position(root):
    if root is None:
        return None

    # Support the common PTZ status schema as well as absoluteEx.
    pan = _find_number(root, {"pan", "x", "azimuth", "absolutePan"})
    tilt = _find_number(root, {"tilt", "y", "elevation", "absoluteTilt"})
    zoom = _find_number(root, {"zoom", "z", "absoluteZoom", "pqrsZoom"})

    if pan is None and tilt is None and zoom is None:
        return None

    # Position changes are based on pan/tilt/zoom. Missing axes are retained as
    # None so firmware differences do not manufacture a change.
    return {"pan": pan, "tilt": tilt, "zoom": zoom}


def _position_changed(old, new):
    if not old or not new:
        return False
    for axis in ("pan", "tilt", "zoom"):
        a = old.get(axis)
        b = new.get(axis)
        if a is not None and b is not None and abs(float(a) - float(b)) > PTZ_POSITION_TOLERANCE:
            return True
    return False


def _position_delta(old, new):
    result = []
    labels = {"pan": "Pan", "tilt": "Tilt", "zoom": "Zoom"}
    for axis, label in labels.items():
        a, b = (old or {}).get(axis), (new or {}).get(axis)
        if a is not None and b is not None and abs(float(a) - float(b)) > PTZ_POSITION_TOLERANCE:
            result.append(f"{label}: {a:g} → {b:g}")
    return ", ".join(result) or "PTZ position changed"


def _probe_camera(camera, nvr):
    """Return (supported, position, source, error_type)."""
    cap_path = "/ISAPI/PTZCtrl/channels/1/capabilities"

    for url, user, password in _camera_urls(camera, nvr, cap_path):
        root, code = _request_xml(url, user, password)
        if code == 401:
            continue
        if root is None:
            continue
        if _has_ptz_capability(root):
            base = url.rsplit("/ISAPI/", 1)[0]
            status_urls = [
                (base + "/ISAPI/PTZCtrl/channels/1/status", user, password),
                (base + "/ISAPI/PTZCtrl/channels/1/absoluteEx", user, password),
            ]
            for status_url, su, sp in status_urls:
                status_root, status_code = _request_xml(status_url, su, sp)
                pos = _parse_position(status_root)
                if pos is not None:
                    return True, pos, base, None
            return True, None, base, "PTZ supported but position API unavailable"

    return False, None, None, "not_ptz_or_unreachable"


def _nvr_for_camera(camera):
    nvr_name = camera.get("nvr")
    for nvr in NVRS:
        if nvr["name"] == nvr_name:
            return nvr
    return None


def _append_alert(event):
    history = []
    try:
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
    except Exception:
        history = []

    history.append(event)
    # Keep the history file bounded so it does not grow forever.
    history = history[-5000:]
    try:
        HISTORY_FILE.write_text(json.dumps(history, indent=4), encoding="utf-8")
    except Exception as exc:
        print(f"⚠️ PTZ history save error: {exc}")


def _send_changed_alert(camera, old, new):
    event_time = _now()
    delta = _position_delta(old, new)
    event = {
        "type": "PTZ Position Changed",
        "camera": camera.get("name", ""),
        "nvr": camera.get("nvr", ""),
        "ip": camera.get("ip", ""),
        "channel": camera.get("id", ""),
        "status": "PTZ Position Changed",
        "old_position": old,
        "new_position": new,
        "change": delta,
        "time": event_time,
    }
    _append_alert(event)

    try:
        send_ptz_position_changed_email(
            camera=camera.get("name", ""),
            nvr=camera.get("nvr", ""),
            ip=camera.get("ip", ""),
            channel=camera.get("id", ""),
            change=delta,
            event_time=event_time,
        )
    except Exception as exc:
        print(f"⚠️ PTZ email error | {camera.get('name')} | {exc}")

    print(
        f"🚨 PTZ CAMERA POSITION CHANGED | {camera.get('nvr')} | "
        f"CH {camera.get('id')} | {camera.get('name')} | {delta}"
    )


def _discover_cameras(cameras):
    """Capability discovery is cached; only unknown/stale entries are probed."""
    jobs = []
    now = time.time()
    with _LOCK:
        for camera in cameras:
            key = _camera_key(camera)
            entry = _state["cameras"].get(key, {})
            last_probe = float(entry.get("capability_checked_at", 0) or 0)
            if entry.get("ptz_supported") is True:
                continue
            if entry.get("ptz_supported") is False and now - last_probe < 600:
                continue
            nvr = _nvr_for_camera(camera)
            if nvr and camera.get("ip"):
                jobs.append((camera, nvr))

    if not jobs:
        return

    with ThreadPoolExecutor(max_workers=min(16, max(1, len(jobs)))) as executor:
        futures = {executor.submit(_probe_camera, camera, nvr): (camera, nvr) for camera, nvr in jobs}
        for future in as_completed(futures):
            camera, _nvr = futures[future]
            key = _camera_key(camera)
            try:
                supported, position, source, error = future.result()
            except Exception as exc:
                supported, position, source, error = False, None, None, str(exc)

            with _LOCK:
                entry = _state["cameras"].setdefault(key, {})
                entry.update({
                    "nvr": camera.get("nvr"),
                    "camera": camera.get("name"),
                    "ip": camera.get("ip"),
                    "channel": camera.get("id"),
                    "ptz_supported": bool(supported),
                    "capability_checked_at": time.time(),
                    "source": source,
                    "last_error": error,
                })
                if supported and position is not None and not entry.get("baseline"):
                    entry["baseline"] = position
                    entry["last_position"] = position
                    entry["candidate_position"] = None
                    entry["candidate_count"] = 0
                    entry["baseline_set_at"] = _now()
                    print(
                        f"🎯 PTZ BASELINE SET | {camera.get('nvr')} | CH {camera.get('id')} | {camera.get('name')} | {position}"
                    )

    with _LOCK:
        _save_state()


def _monitor_ptz_cameras(cameras):
    with _LOCK:
        supported = []
        for camera in cameras:
            entry = _state["cameras"].get(_camera_key(camera), {})
            if entry.get("ptz_supported") is True:
                supported.append((camera, entry))

    if not supported:
        return

    def read_one(camera):
        nvr = _nvr_for_camera(camera)
        if not nvr:
            return camera, None
        supported, position, source, error = _probe_camera(camera, nvr)
        return camera, position if supported else None

    with ThreadPoolExecutor(max_workers=min(16, len(supported))) as executor:
        futures = [executor.submit(read_one, camera) for camera, _entry in supported]
        for future in as_completed(futures):
            try:
                camera, position = future.result()
            except Exception as exc:
                print(f"⚠️ PTZ read error: {exc}")
                continue
            if position is None:
                continue

            key = _camera_key(camera)
            with _LOCK:
                entry = _state["cameras"].get(key)
                if not entry:
                    continue

                baseline = entry.get("baseline")
                if baseline is None:
                    entry["baseline"] = position
                    entry["last_position"] = position
                    entry["baseline_set_at"] = _now()
                    entry["candidate_position"] = None
                    entry["candidate_count"] = 0
                    continue

                if _position_changed(baseline, position):
                    candidate = entry.get("candidate_position")
                    if _position_changed(candidate, position):
                        entry["candidate_position"] = position
                        entry["candidate_count"] = int(entry.get("candidate_count", 0)) + 1
                    else:
                        entry["candidate_position"] = position
                        entry["candidate_count"] = 1

                    if entry["candidate_count"] >= PTZ_CONFIRM_READINGS and not entry.get("alert_active"):
                        old = dict(baseline)
                        new = dict(position)
                        entry["alert_active"] = True
                        entry["last_alert_at"] = _now()
                        _send_changed_alert(camera, old, new)
                else:
                    # Camera returned to its baseline position.
                    if entry.get("alert_active"):
                        event = {
                            "type": "PTZ Position Restored",
                            "camera": camera.get("name", ""),
                            "nvr": camera.get("nvr", ""),
                            "ip": camera.get("ip", ""),
                            "channel": camera.get("id", ""),
                            "status": "PTZ Position Restored",
                            "position": position,
                            "time": _now(),
                        }
                        _append_alert(event)
                        print(
                            f"🟢 PTZ POSITION RESTORED | {camera.get('nvr')} | CH {camera.get('id')} | {camera.get('name')}"
                        )
                    entry["alert_active"] = False
                    entry["candidate_position"] = None
                    entry["candidate_count"] = 0

                entry["last_position"] = position

    with _LOCK:
        _state["last_scan"] = _now()
        _save_state()


def _loop():
    print(
        f"🎯 PTZ monitor started | interval={PTZ_MONITOR_INTERVAL_SECONDS}s | "
        f"confirm={PTZ_CONFIRM_READINGS} | tolerance={PTZ_POSITION_TOLERANCE}"
    )
    _load_state()
    while not _STOP.wait(PTZ_MONITOR_INTERVAL_SECONDS):
        try:
            # Local import prevents a crud <-> ptz_monitor import cycle.
            from . import crud
            cameras = crud.get_cached_cameras(online_only=True)
            if not cameras:
                continue
            _discover_cameras(cameras)
            _monitor_ptz_cameras(cameras)
        except Exception as exc:
            print(f"❌ PTZ monitor cycle error: {exc}")


def start_ptz_monitor():
    global _THREAD
    _load_state()
    if _THREAD is not None and _THREAD.is_alive():
        return
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, name="VisionGuard-PTZ-Monitor", daemon=True)
    _THREAD.start()


def stop_ptz_monitor():
    global _THREAD
    _STOP.set()
    if _THREAD is not None and _THREAD.is_alive():
        _THREAD.join(timeout=3)
    _THREAD = None


def get_ptz_status():
    with _LOCK:
        result = []
        for key, entry in _state.get("cameras", {}).items():
            if entry.get("ptz_supported") is True:
                item = dict(entry)
                item["key"] = key
                result.append(item)
        return result


def get_ptz_summary():
    status = get_ptz_status()
    return {
        "ptz_cameras": len(status),
        "monitor_interval_seconds": PTZ_MONITOR_INTERVAL_SECONDS,
        "last_scan": _state.get("last_scan"),
        "cameras": status,
    }

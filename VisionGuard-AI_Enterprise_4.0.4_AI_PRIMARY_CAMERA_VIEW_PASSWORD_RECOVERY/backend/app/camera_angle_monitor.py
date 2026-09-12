# ==========================================================
# VisionGuard AI - Camera Viewpoint / Angle Change Monitor
# ==========================================================

"""
Enterprise Camera Angle / Viewpoint Monitor.

Features:

- Persistent camera baseline
- RTSP frame capture
- ORB based global scene comparison
- Physical movement filtering
- Two consecutive change confirmations
- Latched Camera Angle Changed state
- Strong baseline recovery verification
- Six consecutive recovery confirmations
- Estimated movement direction
- Alert history
"""

import json
import os
import socket
import threading
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


# ==========================================================
# OPENCV FFMPEG
# ==========================================================

os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    "rtsp_transport;tcp|stimeout;10000000",
)

import cv2


# ==========================================================
# CONFIG
# ==========================================================

from .config import (
    ANGLE_MONITOR_ENABLED,
    ANGLE_MONITOR_INTERVAL_SECONDS,
    ANGLE_CONFIRM_READINGS,
    ANGLE_CHANGE_THRESHOLD,
    ANGLE_MIN_GOOD_MATCHES,
    ANGLE_ORB_FEATURES,
    ANGLE_STREAM_READ_TIMEOUT_SECONDS,
    ANGLE_RESTORE_CONFIRM_READINGS,
    ANGLE_RESTORE_MAX_SCORE,
)

try:
    from .config import (
        VISION_AI_ENABLED,
        VISION_AI_CONFIRM_ONLY,
    )
except Exception:
    VISION_AI_ENABLED = False
    VISION_AI_CONFIRM_ONLY = False

try:
    from .config import (
        ANGLE_REPEAT_MOVEMENT_COOLDOWN_SECONDS,
        ANGLE_REPEAT_SCORE_FACTOR,
        VISION_AI_ANALYSIS_INTERVAL_SECONDS,
    )
except Exception:
    ANGLE_REPEAT_MOVEMENT_COOLDOWN_SECONDS = 300
    ANGLE_REPEAT_SCORE_FACTOR = 1.25
    VISION_AI_ANALYSIS_INTERVAL_SECONDS = 30


# ==========================================================
# EMAIL
# ==========================================================

from .email_service import (
    send_camera_angle_changed_email,
    send_camera_angle_restored_email,
)


# ==========================================================
# RTSP
# ==========================================================

from .video_monitor import rtsp_url


# ==========================================================
# IMAGE ENGINE
# ==========================================================

from .camera_angle import compare_frames

# Optional semantic scene-understanding layer.
# If its ML dependencies/model are unavailable, the existing
# geometry detector continues to work unchanged.
try:
    from .vision_ai import analyze_scene_change
except Exception:
    analyze_scene_change = None


# ==========================================================
# PATHS
# ==========================================================

BASE_DIR = Path(__file__).parent

BASELINE_DIR = BASE_DIR / "angle_baselines"
EVIDENCE_DIR = BASE_DIR / "angle_evidence"

STATE_FILE = BASE_DIR / "camera_angle_state.json"

HISTORY_FILE = BASE_DIR / "alert_history.json"


# ==========================================================
# RTSP SCAN CONFIG
# ==========================================================

ANGLE_RTSP_WORKERS = 4

ANGLE_RTSP_ATTEMPTS = 3

ANGLE_RTSP_RETRY_DELAY_SECONDS = 1.0


# ==========================================================
# DISCOVERY
# ==========================================================

ANGLE_DISCOVERY_CHECK_SECONDS = 5

ANGLE_DISCOVERY_STABLE_CHECKS = 2

ANGLE_DISCOVERY_MAX_WAIT_SECONDS = 0


# ==========================================================
# FRAME
# ==========================================================

ANGLE_FRAME_WIDTH = 640

ANGLE_FRAME_HEIGHT = 360

ANGLE_JPEG_QUALITY = 90


# ==========================================================
# THREAD STATE
# ==========================================================

_LOCK = threading.RLock()

_STOP = threading.Event()

_THREAD = None


# ==========================================================
# GLOBAL STATE
# ==========================================================

_STATE = {
    "cameras": {},
    "last_scan": None,
    "last_scan_counts": {},
    "last_scan_camera_count": 0,
    "discovery_ready": False,
    "discovery_ready_at": None,
}


# ==========================================================
# TIME
# ==========================================================

def _now():
    return datetime.now().strftime(
        "%d-%m-%Y %I:%M:%S %p"
    )


# ==========================================================
# CAMERA KEY
# ==========================================================

def _camera_key(camera):
    # Prefer a hardware identity so the same camera keeps one permanent
    # baseline even if its IP/NVR/channel changes. Fall back to camera name.
    identity = (
        camera.get("serial")
        or camera.get("mac")
        or camera.get("device_id")
        or camera.get("identity")
    )
    if identity:
        return f"IDENTITY|{identity}"
    name = str(camera.get("name") or "").strip().casefold()
    if name:
        return f"NAME|{name}"
    return f"LOCATION|{camera.get('nvr', '')}|{camera.get('id', '')}"


# ==========================================================
# SAFE FILE KEY
# ==========================================================

def _safe_key(camera):

    raw = _camera_key(camera)

    return "".join(
        ch
        if ch.isalnum() or ch in "-_."
        else "_"
        for ch in raw
    )


# ==========================================================
# BASELINE
# ==========================================================

def _baseline_path(camera):

    return (
        BASELINE_DIR
        / f"{_safe_key(camera)}.jpg"
    )


# ==========================================================
# LOAD STATE
# ==========================================================

def _load_state():

    global _STATE

    try:

        if not STATE_FILE.exists():
            return

        data = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(data, dict):
            return

        cameras = data.get("cameras")

        if isinstance(cameras, dict):
            _STATE["cameras"] = cameras

        _STATE["last_scan"] = data.get(
            "last_scan"
        )

        _STATE["last_scan_counts"] = data.get(
            "last_scan_counts",
            {},
        )

        _STATE["last_scan_camera_count"] = data.get(
            "last_scan_camera_count",
            0,
        )

        _STATE["discovery_ready"] = bool(
            data.get(
                "discovery_ready",
                False,
            )
        )

        _STATE["discovery_ready_at"] = data.get(
            "discovery_ready_at"
        )

    except Exception as exc:

        print(
            "⚠️ Camera angle state load error: "
            f"{exc}"
        )


# ==========================================================
# SAVE STATE
# ==========================================================

def _save_state():

    try:

        BASELINE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        tmp = STATE_FILE.with_suffix(
            ".tmp"
        )

        with _LOCK:

            payload = json.dumps(
                _STATE,
                indent=2,
            )

        tmp.write_text(
            payload,
            encoding="utf-8",
        )

        tmp.replace(
            STATE_FILE
        )

    except Exception as exc:

        print(
            "⚠️ Camera angle state save error: "
            f"{exc}"
        )


# ==========================================================
# ALERT HISTORY
# ==========================================================

def _append_history(event):

    try:

        if HISTORY_FILE.exists():

            history = json.loads(
                HISTORY_FILE.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(
                history,
                list,
            ):
                history = []

        else:

            history = []

    except Exception:

        history = []

    history.append(event)

    history = history[-5000:]

    try:

        HISTORY_FILE.write_text(
            json.dumps(
                history,
                indent=4,
            ),
            encoding="utf-8",
        )

    except Exception as exc:

        print(
            "⚠️ Camera angle history save error: "
            f"{exc}"
        )


# ==========================================================
# NVR LOOKUP
# ==========================================================

def _get_nvr(camera):

    from .config import NVRS

    name = camera.get("nvr")

    return next(
        (
            nvr
            for nvr in NVRS
            if nvr.get("name") == name
        ),
        None,
    )


# ==========================================================
# STREAM ID
# ==========================================================

def _get_stream_id(
    camera,
    channel_id,
):

    stream_id = camera.get(
        "stream"
    )

    try:

        return int(
            stream_id
        )

    except (
        TypeError,
        ValueError,
    ):

        return (
            channel_id * 100 + 1
        )


# ==========================================================
# DISCOVERY READY
# ==========================================================

def _explicit_discovery_ready(crud):

    candidates = (
        "is_discovery_ready",
        "get_discovery_ready",
    )

    for function_name in candidates:

        function = getattr(
            crud,
            function_name,
            None,
        )

        if not callable(function):
            continue

        try:

            value = function()

            if value is None:
                return None

            return bool(value)

        except TypeError:

            try:

                value = getattr(
                    crud,
                    function_name,
                )

                if isinstance(
                    value,
                    bool,
                ):
                    return value

            except Exception:
                pass

        except Exception as exc:

            print(
                "⚠️ Discovery ready check error | "
                f"{function_name} | {exc}"
            )

            return None

    return None


# ==========================================================
# DISCOVERY STATUS
# ==========================================================

def _get_discovery_status():

    from . import crud

    explicit = _explicit_discovery_ready(
        crud
    )

    cameras = crud.get_cached_cameras(
        online_only=True
    )

    camera_count = len(cameras)

    if explicit is not None:

        return {
            "ready": bool(explicit),
            "camera_count": camera_count,
            "source": "crud_discovery_ready",
        }

    return {
        "ready": camera_count > 0,
        "camera_count": camera_count,
        "source": "cache_fallback",
    }


# ==========================================================
# WAIT DISCOVERY
# ==========================================================

def _wait_for_discovery():

    from . import crud

    print()

    print(
        "----------------------------------------------------------"
    )

    print(
        "⏳ ANGLE MONITOR WAITING FOR DISCOVERY"
    )

    print(
        "----------------------------------------------------------"
    )

    started = time.monotonic()

    previous_signature = None

    stable_checks = 0

    while not _STOP.is_set():

        try:

            status = _get_discovery_status()

            ready = bool(
                status.get("ready")
            )

            camera_count = int(
                status.get(
                    "camera_count",
                    0,
                )
            )

            source = status.get(
                "source",
                "unknown",
            )

            if source == "crud_discovery_ready":

                if ready:

                    with _LOCK:

                        _STATE[
                            "discovery_ready"
                        ] = True

                        _STATE[
                            "discovery_ready_at"
                        ] = _now()

                    _save_state()

                    print(
                        "✅ ANGLE DISCOVERY READY | "
                        f"cameras={camera_count}"
                    )

                    return True

                print(
                    "⏳ ANGLE DISCOVERY NOT READY | "
                    f"cached_cameras={camera_count}"
                )

            else:

                signature = (
                    camera_count,
                    tuple(
                        sorted(
                            _camera_key(
                                camera
                            )
                            for camera
                            in crud.get_cached_cameras(
                                online_only=True
                            )
                        )
                    ),
                )

                if (
                    signature
                    == previous_signature
                ):

                    stable_checks += 1

                else:

                    stable_checks = 0

                    previous_signature = (
                        signature
                    )

                if (
                    camera_count > 0
                    and stable_checks
                    >= ANGLE_DISCOVERY_STABLE_CHECKS
                ):

                    with _LOCK:

                        _STATE[
                            "discovery_ready"
                        ] = True

                        _STATE[
                            "discovery_ready_at"
                        ] = _now()

                    _save_state()

                    print(
                        "✅ ANGLE DISCOVERY READY | "
                        f"cameras={camera_count} | "
                        f"stable_checks={stable_checks}"
                    )

                    return True

                print(
                    "⏳ ANGLE DISCOVERY WAIT | "
                    f"cached_cameras={camera_count} | "
                    f"stable_checks="
                    f"{stable_checks}/"
                    f"{ANGLE_DISCOVERY_STABLE_CHECKS}"
                )

            if (
                ANGLE_DISCOVERY_MAX_WAIT_SECONDS
                > 0
            ):

                elapsed = (
                    time.monotonic()
                    - started
                )

                if (
                    elapsed
                    >= ANGLE_DISCOVERY_MAX_WAIT_SECONDS
                ):

                    print(
                        "⚠️ ANGLE DISCOVERY "
                        "WAIT TIMEOUT"
                    )

                    return False

        except Exception as exc:

            print(
                "⚠️ ANGLE DISCOVERY STATUS ERROR | "
                f"{exc}"
            )

        if _STOP.wait(
            ANGLE_DISCOVERY_CHECK_SECONDS
        ):
            return False

    return False


# ==========================================================
# RTSP TIMEOUT
# ==========================================================

def _get_rtsp_timeout():

    try:

        configured_timeout = float(
            ANGLE_STREAM_READ_TIMEOUT_SECONDS
        )

    except (
        TypeError,
        ValueError,
    ):

        configured_timeout = 4.0

    return max(
        1.0,
        min(
            configured_timeout,
            10.0,
        ),
    )


# ==========================================================
# OPEN RTSP
# ==========================================================

def _open_capture(
    url,
    timeout_ms,
):

    params = [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
        int(timeout_ms),
        cv2.CAP_PROP_READ_TIMEOUT_MSEC,
        int(timeout_ms),
    ]

    try:

        cap = cv2.VideoCapture(
            url,
            cv2.CAP_FFMPEG,
            params,
        )

        if cap is not None:
            return cap

    except (
        TypeError,
        cv2.error,
    ):

        pass

    try:

        return cv2.VideoCapture(
            url,
            cv2.CAP_FFMPEG,
        )

    except Exception:

        return None


# ==========================================================
# READ FRAME
# ==========================================================

def _read_frame(
    nvr,
    camera,
):

    camera_name = camera.get(
        "name",
        "",
    )

    channel = camera.get(
        "id",
        "",
    )

    nvr_name = camera.get(
        "nvr",
        "",
    )

    try:

        channel_id = int(
            channel
        )

    except (
        TypeError,
        ValueError,
    ):

        print(
            "❌ ANGLE RTSP INVALID CHANNEL | "
            f"{nvr_name} | CH={channel}"
        )

        return None

    stream_id = _get_stream_id(
        camera,
        channel_id,
    )

    try:

        url = rtsp_url(
            nvr,
            stream_id,
        )

        parsed = urlsplit(
            url
        )

        host = (
            parsed.hostname
            or str(
                nvr.get(
                    "ip",
                    "",
                )
            ).strip()
        )

        configured_port = nvr.get(
            "rtsp_port"
        )

        if (
            not host
            or configured_port
            in (
                None,
                "",
            )
        ):

            raise ValueError(
                "missing NVR RTSP configuration"
            )

        configured_port = int(
            configured_port
        )

        try:

            with socket.create_connection(
                (
                    host,
                    configured_port,
                ),
                timeout=2.0,
            ):
                pass

        except OSError as exc:

            print(
                "❌ ANGLE RTSP TCP PORT CLOSED | "
                f"{nvr_name} | "
                f"CH={channel_id} | "
                f"PORT={configured_port} | "
                f"{exc}"
            )

            return None

    except Exception as exc:

        print(
            "❌ ANGLE RTSP URL ERROR | "
            f"{nvr_name} | "
            f"CH={channel_id} | "
            f"STREAM={stream_id} | "
            f"{exc}"
        )

        return None

    timeout_seconds = _get_rtsp_timeout()

    timeout_ms = int(
        timeout_seconds * 1000
    )

    last_error = None

    for attempt in range(
        1,
        ANGLE_RTSP_ATTEMPTS + 1,
    ):

        cap = None

        started = time.monotonic()

        try:

            print(
                "🔎 ANGLE RTSP OPEN | "
                f"{nvr_name} | "
                f"CH={channel_id} | "
                f"attempt={attempt}/"
                f"{ANGLE_RTSP_ATTEMPTS}"
            )

            cap = _open_capture(
                url,
                timeout_ms,
            )

            if (
                cap is None
                or not cap.isOpened()
            ):

                last_error = (
                    "capture_not_opened"
                )

                continue

            try:

                cap.set(
                    cv2.CAP_PROP_BUFFERSIZE,
                    1,
                )

            except Exception:
                pass

            ok, frame = cap.read()

            elapsed = (
                time.monotonic()
                - started
            )

            if (
                not ok
                or frame is None
                or frame.size == 0
            ):

                print(
                    "❌ ANGLE FRAME READ FAILED | "
                    f"{nvr_name} | "
                    f"CH={channel_id} | "
                    f"{elapsed:.2f}s"
                )

                last_error = (
                    "frame_read_failed"
                )

                continue

            frame = cv2.resize(
                frame,
                (
                    ANGLE_FRAME_WIDTH,
                    ANGLE_FRAME_HEIGHT,
                ),
                interpolation=cv2.INTER_AREA,
            )

            print(
                "✅ ANGLE FRAME OK | "
                f"{nvr_name} | "
                f"CH={channel_id} | "
                f"{camera_name} | "
                f"{elapsed:.2f}s"
            )

            return frame

        except Exception as exc:

            last_error = str(exc)

            print(
                "❌ ANGLE FRAME ERROR | "
                f"{nvr_name} | "
                f"CH={channel_id} | "
                f"{exc}"
            )

        finally:

            if cap is not None:

                try:
                    cap.release()
                except Exception:
                    pass

        if attempt < ANGLE_RTSP_ATTEMPTS:

            if _STOP.wait(
                ANGLE_RTSP_RETRY_DELAY_SECONDS
            ):
                return None

    print(
        "❌ ANGLE RTSP PROBE FAILED | "
        f"{nvr_name} | "
        f"CH={channel_id} | "
        f"reason={last_error}"
    )

    return None


# ==========================================================
# COMPARE
# ==========================================================

def _compare(
    baseline,
    current,
):
    """AI-primary camera-view comparison.

    PTZ and ORB/homography are diagnostics only. They never decide an alert.
    """
    try:
        _orb_changed, orb_score, orb_details = compare_frames(
            baseline,
            current,
            orb_features=ANGLE_ORB_FEATURES,
            min_good_matches=ANGLE_MIN_GOOD_MATCHES,
            change_threshold=ANGLE_CHANGE_THRESHOLD,
        )
    except Exception as exc:
        _orb_changed = False
        orb_score = 0.0
        orb_details = f"ORB_DIAGNOSTIC_ERROR={exc}"

    if not bool(VISION_AI_ENABLED) or analyze_scene_change is None:
        return False, float(orb_score), (
            "VISION_AI_REQUIRED=TRUE | VISION_AI_UNAVAILABLE | "
            "Camera-view alert suppressed until AI is available | "
            f"ORB_DIAGNOSTIC={orb_details}"
        )

    try:
        ai = analyze_scene_change(baseline, current, enabled=True)
        if not ai.get("available"):
            return False, float(orb_score), (
                "VISION_AI_REQUIRED=TRUE | "
                f"VISION_AI_UNAVAILABLE={ai.get('reason', 'unknown')} | "
                "Camera-view alert suppressed | "
                f"ORB_DIAGNOSTIC={orb_details}"
            )

        changed = bool(ai.get("changed"))
        score = float(ai.get("distance") or 0.0)
        details = (
            "VISION_AI_PRIMARY="
            f"{'CHANGED' if changed else 'STABLE'}"
            f" | distance={ai.get('distance', '-') }"
            f" | label={ai.get('top_label', '-') }"
            f" | reason={ai.get('reason', '-') }"
        )
        if ai.get("risk"):
            risk = ai["risk"]
            details += (
                f" | risk={risk.get('label')}"
                f"({risk.get('probability')})"
            )
        details += (
            " | PTZ_DECISION=NOT_USED"
            " | ORB_DECISION=NOT_USED"
            f" | ORB_DIAGNOSTIC={orb_details}"
        )
        return changed, score, details
    except Exception as exc:
        return False, float(orb_score), (
            "VISION_AI_PRIMARY=ERROR | "
            f"VISION_AI_ERROR={exc} | "
            "Camera-view alert suppressed | "
            f"ORB_DIAGNOSTIC={orb_details}"
        )


# ==========================================================
# CHANGE EMAIL
# ==========================================================

def _send_change_alert(
    camera,
    score,
    details,
):

    event_time = _now()

    key = _camera_key(
        camera
    )

    event = {
        "type": "Camera Angle Changed",
        "camera": camera.get(
            "name",
            "",
        ),
        "nvr": camera.get(
            "nvr",
            "",
        ),
        "ip": camera.get(
            "ip",
            "",
        ),
        "channel": camera.get(
            "id",
            "",
        ),
        "status": "Camera Angle Changed",
        "score": round(
            float(score),
            4,
        ),
        "details": details,
        "time": event_time,
    }

    _append_history(
        event
    )

    try:

        send_camera_angle_changed_email(
            camera=camera.get(
                "name",
                "",
            ),
            nvr=camera.get(
                "nvr",
                "",
            ),
            ip=camera.get(
                "ip",
                "",
            ),
            channel=camera.get(
                "id",
                "",
            ),
            score=f"{float(score):.3f}",
            details=details,
            event_time=event_time,
        )

    except Exception as exc:

        print(
            "⚠️ Camera angle email error | "
            f"{camera.get('name')} | "
            f"{exc}"
        )

    print()
    print(
        "🚨🚨🚨 CAMERA ANGLE CHANGED 🚨🚨🚨"
    )
    print(
        f"   NVR      : {camera.get('nvr')}"
    )
    print(
        f"   CAMERA   : {camera.get('name')}"
    )
    print(
        f"   CHANNEL  : {camera.get('id')}"
    )
    print(
        f"   IP       : {camera.get('ip')}"
    )
    print(
        f"   SCORE    : {float(score):.3f}"
    )
    print(
        f"   MOVEMENT : {details}"
    )
    print(
        f"   TIME     : {event_time}"
    )
    print(
        "🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨🚨"
    )
    print()

    return key


# ==========================================================
# RESTORE EMAIL
# ==========================================================

def _send_restore_alert(
    camera,
):

    event_time = _now()

    event = {
        "type": "Camera Angle Restored",
        "camera": camera.get(
            "name",
            "",
        ),
        "nvr": camera.get(
            "nvr",
            "",
        ),
        "ip": camera.get(
            "ip",
            "",
        ),
        "channel": camera.get(
            "id",
            "",
        ),
        "status": "Camera Angle Restored",
        "time": event_time,
    }

    _append_history(
        event
    )

    try:

        send_camera_angle_restored_email(
            camera=camera.get(
                "name",
                "",
            ),
            nvr=camera.get(
                "nvr",
                "",
            ),
            ip=camera.get(
                "ip",
                "",
            ),
            channel=camera.get(
                "id",
                "",
            ),
            event_time=event_time,
        )

    except Exception as exc:

        print(
            "⚠️ Camera angle recovery email error | "
            f"{camera.get('name')} | {exc}"
        )

    print()
    print(
        "🟢🟢🟢 CAMERA ANGLE RESTORED 🟢🟢🟢"
    )
    print(
        f"   NVR      : {camera.get('nvr')}"
    )
    print(
        f"   CAMERA   : {camera.get('name')}"
    )
    print(
        f"   CHANNEL  : {camera.get('id')}"
    )
    print(
        f"   IP       : {camera.get('ip')}"
    )
    print(
        f"   TIME     : {event_time}"
    )
    print(
        "🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢"
    )
    print()


# ==========================================================
# PROCESS CAMERA
# ==========================================================

def _process_camera(
    camera,
):

    nvr = _get_nvr(
        camera
    )

    if not nvr:

        print(
            "❌ ANGLE NVR NOT FOUND | "
            f"{camera.get('nvr')}"
        )

        return "nvr_missing"

    frame = _read_frame(
        nvr,
        camera,
    )

    if frame is None:

        return "frame_failed"

    key = _camera_key(
        camera
    )

    baseline_path = _baseline_path(
        camera
    )

    with _LOCK:

        entry = _STATE[
            "cameras"
        ].setdefault(
            key,
            {},
        )

        entry.update(
            {
                "nvr": camera.get("nvr"),
                "camera": camera.get("name"),
                "ip": camera.get("ip"),
                "channel": camera.get("id"),
                "baseline": str(
                    baseline_path
                ),
                "last_frame_at": _now(),
            }
        )

    baseline = None

    if baseline_path.exists():

        try:

            baseline = cv2.imread(
                str(
                    baseline_path
                )
            )

        except Exception:

            baseline = None

    # ======================================================
    # FIRST FRAME = BASELINE
    # ======================================================

    if (
        baseline is None
        or baseline.size == 0
    ):

        BASELINE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        success = cv2.imwrite(
            str(
                baseline_path
            ),
            frame,
            [
                cv2.IMWRITE_JPEG_QUALITY,
                ANGLE_JPEG_QUALITY,
            ],
        )

        if not success:

            print(
                "❌ ANGLE BASELINE WRITE FAILED | "
                f"{camera.get('nvr')} | "
                f"CH={camera.get('id')}"
            )

            return "baseline_write_failed"

        with _LOCK:

            entry = _STATE[
                "cameras"
            ].setdefault(
                key,
                {},
            )

            entry.update(
                {
                    "baseline_set_at": _now(),
                    "alert_active": False,
                    "candidate_count": 0,
                    "restore_candidate_count": 0,
                    "last_score": 0.0,
                    "last_details": "baseline_set",
                    "last_changed": False,
                    "last_movement": (
                        "No movement baseline yet"
                    ),
                    "last_ai_result": None,
                    "last_ai_epoch": 0,
                }
            )

        print(
            "📌 ANGLE BASELINE SET | "
            f"{camera.get('nvr')} | "
            f"CH={camera.get('id')} | "
            f"{camera.get('name')}"
        )

        return "baseline_set"

    # ======================================================
    # COMPARE
    # ======================================================

    # AI inference is intentionally sampled less frequently than RTSP polling
    # to keep CPU usage reasonable on multi-camera NVR deployments.
    ai_now = time.time()
    cached_ai = entry.get("last_ai_result") if isinstance(entry, dict) else None
    cached_ai_epoch = float(entry.get("last_ai_epoch", 0) or 0) if isinstance(entry, dict) else 0.0
    if (
        isinstance(cached_ai, dict)
        and ai_now - cached_ai_epoch < float(VISION_AI_ANALYSIS_INTERVAL_SECONDS)
    ):
        changed = bool(cached_ai.get("changed", False))
        score = float(cached_ai.get("score", 0.0) or 0.0)
        details = str(cached_ai.get("details", "VISION_AI_CACHE")) + " | VISION_AI_SAMPLE=CACHED"
    else:
        changed, score, details = _compare(baseline, frame)
        with _LOCK:
            entry = _STATE["cameras"].setdefault(key, {})
            entry["last_ai_result"] = {
                "changed": bool(changed),
                "score": float(score),
                "details": details,
            }
            entry["last_ai_epoch"] = ai_now

    alert_to_send = None

    restore_to_send = False

    with _LOCK:

        entry = _STATE[
            "cameras"
        ].setdefault(
            key,
            {},
        )

        active = bool(
            entry.get(
                "alert_active",
                False,
            )
        )

        # A permanent baseline detects the first physical move, but a latched
        # alert would otherwise suppress later moves forever. Keep a separate
        # last-alert anchor so every subsequent physical move can generate a
        # fresh email without replacing the permanent wall/scene baseline.
        if active:
            anchor_path = entry.get("movement_anchor")
            if anchor_path and os.path.exists(anchor_path):
                try:
                    anchor = cv2.imread(anchor_path)
                    if anchor is not None and anchor.size:
                        anchor_changed, anchor_score, anchor_details = _compare(anchor, frame)
                        elapsed = time.time() - float(entry.get("last_alert_epoch", 0) or 0)
                        last_score = float(entry.get("last_alert_score", 0) or 0)
                        if (
                            anchor_changed
                            and elapsed >= float(ANGLE_REPEAT_MOVEMENT_COOLDOWN_SECONDS)
                            and (last_score <= 0 or anchor_score >= last_score * float(ANGLE_REPEAT_SCORE_FACTOR))
                        ):
                            entry["last_alert_epoch"] = time.time()
                            entry["last_alert_score"] = float(anchor_score)
                            alert_to_send = (float(anchor_score), "ADDITIONAL CAMERA MOVEMENT | " + str(anchor_details))
                            entry["movement_anchor_pending"] = True
                except Exception as exc:
                    print(f"⚠️ ANGLE REPEAT ANCHOR ERROR | {camera.get('nvr')} | CH={camera.get('id')} | {exc}")

        entry[
            "last_checked_at"
        ] = _now()

        entry[
            "last_score"
        ] = round(
            float(score),
            4,
        )

        entry[
            "last_details"
        ] = details

        entry[
            "last_changed"
        ] = bool(changed)

        movement_text = details

        if "ESTIMATED MOVEMENT:" in details:

            movement_text = details.split(
                " | matches=",
                1,
            )[0]

        entry[
            "last_movement"
        ] = movement_text

        # ==================================================
        # PHYSICAL MOVEMENT DETECTED
        # ==================================================

        if changed:

            entry[
                "candidate_count"
            ] = (
                int(
                    entry.get(
                        "candidate_count",
                        0,
                    )
                )
                + 1
            )

            entry[
                "restore_candidate_count"
            ] = 0

            print(
                "⚠️ ANGLE CHANGE CANDIDATE | "
                f"{camera.get('nvr')} | "
                f"CH={camera.get('id')} | "
                f"count="
                f"{entry['candidate_count']}/"
                f"{ANGLE_CONFIRM_READINGS} | "
                f"score={score:.3f} | "
                f"{camera.get('name')}"
            )

            # ----------------------------------------------
            # CONFIRM CHANGE
            # ----------------------------------------------

            if (
                entry[
                    "candidate_count"
                ]
                >= int(
                    ANGLE_CONFIRM_READINGS
                )
                and not active
            ):

                entry[
                    "alert_active"
                ] = True

                entry[
                    "last_alert_at"
                ] = _now()

                entry["last_alert_score"] = float(score)
                entry["last_alert_epoch"] = time.time()
                entry["movement_anchor_pending"] = True
                alert_to_send = (
                    float(score),
                    details,
                )

        # ==================================================
        # NO PHYSICAL MOVEMENT
        # ==================================================

        else:

            entry[
                "candidate_count"
            ] = 0

            # ==================================================
            # IMPORTANT:
            #
            # If alert_active=True, DO NOT immediately restore.
            # ==================================================

            if active:

                recovery_confirmed = (
                    "BASELINE_RECOVERY_CONFIRMED"
                    in str(details)
                    and float(score)
                    <= float(
                        ANGLE_RESTORE_MAX_SCORE
                    )
                )

                if recovery_confirmed:

                    entry[
                        "restore_candidate_count"
                    ] = (
                        int(
                            entry.get(
                                "restore_candidate_count",
                                0,
                            )
                        )
                        + 1
                    )

                    print(
                        "↩️ ANGLE RESTORE CANDIDATE | "
                        f"{camera.get('nvr')} | "
                        f"CH={camera.get('id')} | "
                        f"count="
                        f"{entry['restore_candidate_count']}/"
                        f"{ANGLE_RESTORE_CONFIRM_READINGS} | "
                        f"score={score:.3f}"
                    )

                    # --------------------------------------
                    # CONFIRM RESTORE
                    # --------------------------------------

                    if (
                        entry[
                            "restore_candidate_count"
                        ]
                        >= int(
                            ANGLE_RESTORE_CONFIRM_READINGS
                        )
                    ):

                        entry[
                            "alert_active"
                        ] = False

                        entry[
                            "restore_candidate_count"
                        ] = 0

                        entry[
                            "last_restored_at"
                        ] = _now()

                        restore_to_send = True

                else:

                    # --------------------------------------
                    # LATCH
                    # --------------------------------------

                    entry[
                        "restore_candidate_count"
                    ] = 0

                    print(
                        "🔒 ANGLE STATE LATCHED | "
                        f"{camera.get('nvr')} | "
                        f"CH={camera.get('id')} | "
                        f"score={score:.3f} | "
                        "baseline recovery not confirmed"
                    )

            else:

                entry[
                    "restore_candidate_count"
                ] = 0

            if details not in (
                "baseline_set",
                "no_frame",
            ):

                print(
                    "✓ ANGLE OK | "
                    f"{camera.get('nvr')} | "
                    f"CH={camera.get('id')} | "
                    f"score={score:.3f} | "
                    f"{camera.get('name')}"
                )

    # ======================================================
    # SEND ALERT OUTSIDE LOCK
    # ======================================================

    if alert_to_send is not None:
        alert_score, alert_details = alert_to_send
        try:
            EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            evidence_path = EVIDENCE_DIR / f"{_safe_key(camera)}_{stamp}.jpg"
            cv2.imwrite(str(evidence_path), frame, [cv2.IMWRITE_JPEG_QUALITY, ANGLE_JPEG_QUALITY])
            evidence_files = sorted(EVIDENCE_DIR.glob("*.jpg"), key=lambda x: x.stat().st_mtime, reverse=True)
            for old_file in evidence_files[200:]:
                try: old_file.unlink()
                except OSError: pass
            alert_details = f"{alert_details} | EVIDENCE_FILE={evidence_path}"
            with _LOCK:
                state_entry = _STATE["cameras"].setdefault(_camera_key(camera), {})
                state_entry["movement_anchor"] = str(evidence_path)
                state_entry["movement_anchor_pending"] = False
            _save_state()
        except Exception as exc:
            print(f"⚠️ ANGLE EVIDENCE SAVE FAILED | {camera.get('nvr')} | CH={camera.get('id')} | {exc}")
        _send_change_alert(camera, alert_score, alert_details)

    if restore_to_send:

        _send_restore_alert(
            camera
        )

    if changed:

        return "changed"

    return "ok"


# ==========================================================
# SCAN
# ==========================================================

def _scan_once():

    from . import crud

    cameras = crud.get_cached_cameras(
        online_only=True
    )

    print()
    print(
        "=========================================================="
    )

    print(
        f"🔍 ANGLE SCAN START | CAMERAS={len(cameras)}"
    )

    print(
        "=========================================================="
    )

    if not cameras:

        print(
            "⚠️ ANGLE SCAN SKIPPED | "
            "camera cache is empty"
        )

        return 0

    workers = min(
        ANGLE_RTSP_WORKERS,
        max(
            1,
            len(cameras),
        ),
    )

    print(
        "⚡ ANGLE CONTROLLED RTSP SCAN | "
        f"cameras={len(cameras)} | "
        f"workers={workers}"
    )

    counts = {}

    started = time.monotonic()

    with ThreadPoolExecutor(
        max_workers=workers,
        thread_name_prefix="angle",
    ) as executor:

        futures = {
            executor.submit(
                _process_camera,
                camera,
            ): camera
            for camera in cameras
        }

        for future in as_completed(
            futures
        ):

            camera = futures[
                future
            ]

            try:

                result = future.result()

                counts[result] = (
                    counts.get(
                        result,
                        0,
                    )
                    + 1
                )

            except Exception as exc:

                counts[
                    "worker_error"
                ] = (
                    counts.get(
                        "worker_error",
                        0,
                    )
                    + 1
                )

                print(
                    "⚠️ Camera angle worker error | "
                    f"{camera.get('nvr')} | "
                    f"CH={camera.get('id')} | "
                    f"{camera.get('name')} | "
                    f"{exc}"
                )

    elapsed = (
        time.monotonic()
        - started
    )

    with _LOCK:

        _STATE[
            "last_scan"
        ] = _now()

        _STATE[
            "last_scan_counts"
        ] = counts

        _STATE[
            "last_scan_camera_count"
        ] = len(cameras)

    _save_state()

    print()

    print(
        "=========================================================="
    )

    print(
        "📊 ANGLE SCAN COMPLETE | "
        f"cameras={len(cameras)} | "
        f"elapsed={elapsed:.2f}s"
    )

    print(
        f"📊 ANGLE RESULTS | {counts}"
    )

    print(
        "=========================================================="
    )

    return len(cameras)


# ==========================================================
# LOOP
# ==========================================================

def _loop():

    print()
    print(
        "======================================================================"
    )

    print(
        "📐 VisionGuard AI Camera Angle Monitor"
    )

    print(
        f"   Interval      : "
        f"{ANGLE_MONITOR_INTERVAL_SECONDS}s"
    )

    print(
        f"   Confirmations : "
        f"{ANGLE_CONFIRM_READINGS}"
    )

    print(
        f"   Threshold     : "
        f"{ANGLE_CHANGE_THRESHOLD}"
    )

    print(
        f"   ORB Features  : "
        f"{ANGLE_ORB_FEATURES}"
    )

    print(
        f"   Min Matches   : "
        f"{ANGLE_MIN_GOOD_MATCHES}"
    )

    print(
        f"   RTSP Timeout  : "
        f"{ANGLE_STREAM_READ_TIMEOUT_SECONDS}s"
    )

    print(
        f"   Restore       : "
        f"{ANGLE_RESTORE_CONFIRM_READINGS} confirmations"
    )

    print(
        "   Angle Estimate: image geometry"
    )

    print(
        "======================================================================"
    )

    _load_state()

    discovery_ready = (
        _wait_for_discovery()
    )

    if _STOP.is_set():
        return

    empty_cache_retries = 0

    while not _STOP.is_set():

        try:

            if not discovery_ready:

                discovery_ready = (
                    _wait_for_discovery()
                )

                if not discovery_ready:

                    if _STOP.wait(
                        ANGLE_DISCOVERY_CHECK_SECONDS
                    ):
                        break

                    continue

            print(
                f"\n🔍 ANGLE SCAN START | "
                f"{_now()}"
            )

            camera_count = _scan_once()

            if camera_count == 0:

                empty_cache_retries += 1

                discovery_ready = False

                with _LOCK:

                    _STATE[
                        "discovery_ready"
                    ] = False

                _save_state()

                print(
                    "⏳ ANGLE CACHE EMPTY | "
                    f"retry={empty_cache_retries}"
                )

                if _STOP.wait(
                    ANGLE_DISCOVERY_CHECK_SECONDS
                ):
                    break

                continue

            empty_cache_retries = 0

        except Exception as exc:

            print(
                "❌ Camera angle monitor "
                f"cycle error: {exc}"
            )

        if _STOP.wait(
            ANGLE_MONITOR_INTERVAL_SECONDS
        ):
            break


# ==========================================================
# START
# ==========================================================

def start_camera_angle_monitor():

    global _THREAD

    if not ANGLE_MONITOR_ENABLED:

        print(
            "ℹ️ Camera angle monitor "
            "disabled by configuration"
        )

        return

    _load_state()

    if (
        _THREAD is not None
        and _THREAD.is_alive()
    ):

        print(
            "ℹ️ Camera Angle Monitor "
            "already running"
        )

        return

    _STOP.clear()

    _THREAD = threading.Thread(
        target=_loop,
        name="VisionGuard-Camera-Angle-Monitor",
        daemon=True,
    )

    _THREAD.start()

    print(
        "✓ Camera Angle Monitor "
        "Started Successfully"
    )


# ==========================================================
# STOP
# ==========================================================

def stop_camera_angle_monitor():

    global _THREAD

    _STOP.set()

    if (
        _THREAD is not None
        and _THREAD.is_alive()
    ):

        _THREAD.join(
            timeout=3
        )

    _THREAD = None

    print(
        "✓ Camera Angle Monitor Stopped"
    )


# ==========================================================
# STATUS API
# ==========================================================

def get_camera_angle_status():

    with _LOCK:

        result = []

        for key, entry in (
            _STATE
            .get(
                "cameras",
                {},
            )
            .items()
        ):

            item = dict(
                entry
            )

            item[
                "key"
            ] = key

            result.append(
                item
            )

        return result


# ==========================================================
# SUMMARY API
# ==========================================================

def get_camera_angle_summary():

    status = (
        get_camera_angle_status()
    )

    return {
        "enabled": bool(
            ANGLE_MONITOR_ENABLED
        ),

        "cameras": len(
            status
        ),

        "changed": sum(
            1
            for item in status
            if item.get(
                "alert_active"
            )
        ),

        "last_scan": _STATE.get(
            "last_scan"
        ),

        "last_scan_camera_count":
            _STATE.get(
                "last_scan_camera_count",
                0,
            ),

        "last_scan_counts":
            _STATE.get(
                "last_scan_counts",
                {},
            ),

        "discovery_ready":
            bool(
                _STATE.get(
                    "discovery_ready",
                    False,
                )
            ),

        "discovery_ready_at":
            _STATE.get(
                "discovery_ready_at"
            ),

        "interval_seconds":
            ANGLE_MONITOR_INTERVAL_SECONDS,

        "rtsp_workers":
            ANGLE_RTSP_WORKERS,

        "rtsp_timeout_seconds":
            _get_rtsp_timeout(),

        "rtsp_attempts":
            ANGLE_RTSP_ATTEMPTS,

        "baseline_directory":
            str(
                BASELINE_DIR
            ),

        "angle_estimation": {
            "enabled": True,
            "horizontal_fov_deg": 75.0,
            "vertical_fov_deg": 45.0,
            "note": (
                "Estimated from image geometry; "
                "not a direct PTZ encoder reading."
            ),
        },
    }
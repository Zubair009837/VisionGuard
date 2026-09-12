# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 1 / 10
# Imports + Configuration + Runtime Variables
# ==========================================================

import cv2
import time
from urllib.parse import quote
import threading
import requests
import xml.etree.ElementTree as ET

from datetime import datetime
from requests.auth import HTTPDigestAuth

from .config import NVRS
from .email_service import (
    send_video_loss_email,
    send_video_restored_email,
)

# ==========================================================
# Enterprise Configuration
# ==========================================================

CHECK_INTERVAL = 10          # Monitor every 10 seconds

VIDEO_LOSS_DELAY = 60        # Send alert after 60 sec

REQUEST_TIMEOUT = 10

RTSP_PORT = 554  # fallback only; active NVRs provide rtsp_port
# ==========================================================
# Runtime Storage
# ==========================================================

# Camera Current Status
CAMERA_STATUS = {}

# Offline Start Time
VIDEO_LOSS_TIME = {}

# Alert Protection
LOSS_ALERT_SENT = set()

RESTORE_ALERT_SENT = set()

# Camera Cache
CAMERA_CACHE = {}

# Event History
EVENT_HISTORY = []

# Thread Lock
LOCK = threading.Lock()

# ==========================================================
# Banner
# ==========================================================

print("=" * 70)
print("VisionGuard AI Enterprise Video Monitoring Engine")
print("=" * 70)

# ==========================================================
# Helper Functions
# ==========================================================

def current_time():

    return datetime.now().strftime(
        "%d-%m-%Y %I:%M:%S %p"
    )


def log(message):

    print(
        f"[{current_time()}] {message}"
    )


# ==========================================================
# RTSP URL Builder
# ==========================================================

def rtsp_url(nvr, stream_id):
    """
    Build a Hikvision RTSP URL safely.

    IMPORTANT:
    NVR passwords may contain characters such as @, #, :, /, etc.
    Those characters MUST be URL-encoded inside the RTSP authority.
    Without encoding, OpenCV/FFmpeg can parse the credentials
    incorrectly and every RTSP probe can fail before a frame is read.
    """
    username = quote(str(nvr.get("username", "")), safe="")
    password = quote(str(nvr.get("password", "")), safe="")
    host = str(nvr.get("ip", "")).strip()

    # Each NVR has its own RTSP port. Use the configured NVR port,
    # and keep 554 only as a fallback for older configurations.
    rtsp_port = int(nvr.get("rtsp_port") or RTSP_PORT)

    return (
        f"rtsp://{username}:{password}@"
        f"{host}:{rtsp_port}"
        f"/Streaming/Channels/{int(stream_id)}"
    )


# ==========================================================
# Hikvision ISAPI URL Builder
# ==========================================================

def isapi_url(nvr, endpoint):

    return (

        f"http://"

        f"{nvr['ip']}:{nvr['port']}"

        f"{endpoint}"

    )


# ==========================================================
# HTTP GET Wrapper
# ==========================================================

def hik_get(nvr, endpoint):

    try:

        response = requests.get(

            isapi_url(nvr, endpoint),

            auth=HTTPDigestAuth(

                nvr["username"],
                nvr["password"]

            ),

            timeout=REQUEST_TIMEOUT

        )

        response.raise_for_status()

        return response.text

    except Exception as e:

        log(

            f"{nvr['name']} API Error : {e}"

        )

        return None
# ==========================================================
# NVR Connectivity Check
# ==========================================================

def nvr_online(nvr):

    try:

        response = requests.get(

            isapi_url(
                nvr,
                "/ISAPI/System/deviceInfo"
            ),

            auth=HTTPDigestAuth(
                nvr["username"],
                nvr["password"]
            ),

            timeout=REQUEST_TIMEOUT
        )

        if response.status_code in [200, 401]:

            return True

        return False

    except Exception as e:

        log(
            f"{nvr['name']} NVR Offline : {e}"
        )

        return False
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 2 / 10
# Hikvision Camera APIs
# ==========================================================

# ==========================================================
# Fetch Camera Status
# ==========================================================

def fetch_camera_status(nvr):

    xml = hik_get(

        nvr,

        "/ISAPI/ContentMgmt/InputProxy/channels/status"

    )

    if xml is None:

        return []

    cameras = []

    try:

        root = ET.fromstring(xml)

        for cam in root.findall(".//{*}InputProxyChannelStatus"):

            camera = {}

            id_node = cam.find("{*}id")

            ip_node = cam.find(".//{*}ipAddress")

            online_node = cam.find("{*}online")

            detect_node = cam.find("{*}chanDetectResult")

            if id_node is not None:

                camera["id"] = int(id_node.text)

            else:

                camera["id"] = 0

            if ip_node is not None:

                camera["ip"] = ip_node.text.strip()

            else:

                camera["ip"] = ""

            if online_node is not None:

                camera["online"] = (

                    online_node.text.lower()

                    == "true"

                )

            else:

                camera["online"] = False

            if detect_node is not None:

                camera["detect"] = (

                    detect_node.text.strip()

                )

            else:

                camera["detect"] = "unknown"

            cameras.append(camera)

    except Exception as e:

        log(

            f"{nvr['name']} XML Parse Error : {e}"

        )

    return cameras


# ==========================================================
# Fetch Camera Names
# ==========================================================

def fetch_camera_names(nvr):

    xml = hik_get(

        nvr,

        "/ISAPI/ContentMgmt/InputProxy/channels"

    )

    if xml is None:

        return {}

    names = {}

    try:

        root = ET.fromstring(xml)

        for cam in root.findall(".//{*}InputProxyChannel"):

            id_node = cam.find("{*}id")

            name_node = cam.find("{*}name")

            if id_node is None:

                continue

            cam_id = int(id_node.text)

            if name_node is not None:

                names[cam_id] = (

                    name_node.text.strip()

                )

            else:

                names[cam_id] = (

                    f"Camera {cam_id}"

                )

    except Exception as e:

        log(

            f"{nvr['name']} Name Parse Error : {e}"

        )

    return names


# ==========================================================
# Load Cameras From NVR
# ==========================================================

def load_camera_cache(nvr):

    status = fetch_camera_status(nvr)

    names = fetch_camera_names(nvr)

    cameras = []

    for cam in status:

        stream = cam["id"] * 100 + 1

        cameras.append({

            "id": cam["id"],

            "name": names.get(

                cam["id"],

                f"Camera {cam['id']}"

            ),

            "ip": cam["ip"],

            "online": cam["online"],

            "detect": cam["detect"],

            "stream": stream

        })

    CAMERA_CACHE[nvr["name"]] = cameras

    log(

        f"{nvr['name']} : "

        f"{len(cameras)} Cameras Loaded"

    )

    return cameras


# ==========================================================
# Get Cameras
# ==========================================================

def get_cameras(nvr):

    if nvr["name"] not in CAMERA_CACHE:

        return load_camera_cache(nvr)

    return CAMERA_CACHE[nvr["name"]]
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 3 / 10
# RTSP Video Stream Checker
# ==========================================================

# ==========================================================
# Check RTSP Stream
# ==========================================================

def stream_alive(nvr, stream_id):

    url = rtsp_url(

        nvr,

        stream_id

    )

    cap = None

    try:

        cap = cv2.VideoCapture(

            url,

            cv2.CAP_FFMPEG

        )

        if not cap.isOpened():

            return False

        success, frame = cap.read()

        if not success:

            return False

        if frame is None:

            return False

        return True

    except Exception as e:

        log(

            f"{nvr['name']} Stream Error : {e}"

        )

        return False

    finally:

        if cap is not None:

            cap.release()


# ==========================================================
# Get Current Camera State
# ==========================================================

def camera_online(nvr, camera):

    try:

        return camera.get(
            "online",
            False
        )

    except Exception as e:

        log(
            f"{nvr['name']} Camera Status Error : {e}"
        )

        return False


# ==========================================================
# Initialize Camera Status
# ==========================================================

def initialize_camera(camera_key, current_state):

    CAMERA_STATUS[camera_key] = current_state

    if current_state:

        log(

            f"{camera_key} -> ONLINE"

        )

    else:

        log(

            f"{camera_key} -> OFFLINE"

        )


# ==========================================================
# Save Video Loss Time
# ==========================================================

def start_loss_timer(camera_key):

    if camera_key not in VIDEO_LOSS_TIME:

        VIDEO_LOSS_TIME[camera_key] = datetime.now()

        log(

            f"{camera_key} Loss Timer Started"

        )


# ==========================================================
# Stop Video Loss Timer
# ==========================================================

def stop_loss_timer(camera_key):

    if camera_key in VIDEO_LOSS_TIME:

        downtime = (

            datetime.now()

            -

            VIDEO_LOSS_TIME[camera_key]

        )

        del VIDEO_LOSS_TIME[camera_key]

        return downtime

    return None


# ==========================================================
# Loss Duration
# ==========================================================

def loss_seconds(camera_key):

    if camera_key not in VIDEO_LOSS_TIME:

        return 0

    return (

        datetime.now()

        -

        VIDEO_LOSS_TIME[camera_key]

    ).total_seconds()


# ==========================================================
# Reset Camera Alerts
# ==========================================================

def reset_alerts(camera_key):

    LOSS_ALERT_SENT.discard(

        camera_key

    )

    RESTORE_ALERT_SENT.discard(

        camera_key

    )
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 4 / 10
# Video Loss Detection Engine
# ==========================================================

# ==========================================================
# Send Video Loss Alert
# ==========================================================

def handle_video_loss(nvr, camera, camera_key):

    start_loss_timer(camera_key)

    seconds = loss_seconds(camera_key)

    if seconds < VIDEO_LOSS_DELAY:

        log(

            f"{camera['name']} Waiting "

            f"{int(seconds)}/{VIDEO_LOSS_DELAY}s"

        )

        return

    if camera_key in LOSS_ALERT_SENT:

        return

    log("=" * 60)

    log(f"VIDEO LOSS DETECTED : {camera['name']}")

    log(f"NVR     : {nvr['name']}")

    log(f"IP      : {camera['ip']}")

    log("=" * 60)

    try:

        send_video_loss_email(

            camera=camera["name"],

            nvr=nvr["name"],

            ip=camera["ip"],

            event_time=current_time()

        )

        log(

            f"Email Sent : {camera['name']}"

        )

    except Exception as e:

        log(

            f"Email Error : {e}"

        )

    LOSS_ALERT_SENT.add(camera_key)

    RESTORE_ALERT_SENT.discard(camera_key)

    EVENT_HISTORY.append({

        "time": current_time(),

        "camera": camera["name"],

        "nvr": nvr["name"],

        "status": "VIDEO LOST"

    })


# ==========================================================
# Save Current Camera State
# ==========================================================

def update_camera_state(camera_key, state):

    CAMERA_STATUS[camera_key] = state


# ==========================================================
# Process Offline Camera
# ==========================================================

def process_offline_camera(

    nvr,

    camera,

    camera_key

):

    handle_video_loss(

        nvr,

        camera,

        camera_key

    )

    update_camera_state(

        camera_key,

        False

    )


# ==========================================================
# Is First Scan
# ==========================================================

def is_first_scan(camera_key):

    return camera_key not in CAMERA_STATUS
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 5 / 10
# Video Recovery Engine
# ==========================================================

# ==========================================================
# Send Recovery Email
# ==========================================================

def handle_video_restore(nvr, camera, camera_key):

    downtime = stop_loss_timer(camera_key)

    if camera_key in RESTORE_ALERT_SENT:

        update_camera_state(

            camera_key,

            True

        )

        return

    log("=" * 60)

    log(f"VIDEO RESTORED : {camera['name']}")

    log(f"NVR      : {nvr['name']}")

    log(f"IP       : {camera['ip']}")

    if downtime is not None:

        log(f"Downtime : {downtime}")

    log("=" * 60)

    try:

        send_video_restored_email(

            camera=camera["name"],

            nvr=nvr["name"],

            ip=camera["ip"],

            event_time=current_time()

        )

        log(

            f"Recovery Email Sent : {camera['name']}"

        )

    except Exception as e:

        log(

            f"Recovery Email Error : {e}"

        )

    RESTORE_ALERT_SENT.add(camera_key)

    LOSS_ALERT_SENT.discard(camera_key)

    EVENT_HISTORY.append({

        "time": current_time(),

        "camera": camera["name"],

        "nvr": nvr["name"],

        "status": "VIDEO RESTORED",

        "downtime": str(downtime)

    })

    update_camera_state(

        camera_key,

        True

    )


# ==========================================================
# Process One Camera
# ==========================================================

def process_camera(nvr, camera):

    camera_key = (

        f"{nvr['name']}_"

        f"{camera['id']}"

    )

    current_state = camera_online(

        nvr,

        camera

    )

    if is_first_scan(camera_key):

        initialize_camera(

            camera_key,

            current_state

        )

        return

    previous_state = CAMERA_STATUS.get(

        camera_key,

        False

    )

    # -----------------------------
    # Camera Online
    # -----------------------------

    if current_state:

        if not previous_state:

            handle_video_restore(

                nvr,

                camera,

                camera_key

            )

        else:

            update_camera_state(

                camera_key,

                True

            )

        return

    # -----------------------------
    # Camera Offline
    # -----------------------------

    if previous_state:

        process_offline_camera(

            nvr,

            camera,

            camera_key

        )

    else:

        handle_video_loss(

            nvr,

            camera,

            camera_key

        )
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 6 / 10
# NVR Scanner
# ==========================================================

# ==========================================================
# Scan One NVR
# ==========================================================

# ==========================================================
# Scan One NVR
# ==========================================================

def check_nvr(nvr):

    log("=" * 60)
    log(f"Scanning {nvr['name']}")

    # ------------------------------------------------------
    # STEP 1: Check NVR connectivity first
    # ------------------------------------------------------

    if not nvr_online(nvr):

        log(f"NVR OFFLINE : {nvr['name']}")

        # Use already discovered cameras from cache
        cameras = CAMERA_CACHE.get(
            nvr["name"],
            []
        )

        # If cache is empty, we cannot know how many
        # cameras belong to this NVR yet.
        if not cameras:

            log(
                f"{nvr['name']} : "
                "No cached cameras available"
            )

            return

        total = len(cameras)

        online = 0
        offline = 0

        # --------------------------------------------------
        # NVR is offline
        # Therefore ALL its cameras are offline
        # --------------------------------------------------

        for camera in cameras:

            key = (
                f"{nvr['name']}_"
                f"{camera['id']}"
            )

            previous_state = CAMERA_STATUS.get(
                key,
                False
            )

            # First time this camera is seen
            if key not in CAMERA_STATUS:

                initialize_camera(
                    key,
                    False
                )

            # Camera was previously ONLINE
            # Now entire NVR is offline
            elif previous_state:

                process_offline_camera(
                    nvr,
                    camera,
                    key
                )

            else:

                update_camera_state(
                    key,
                    False
                )

            offline += 1

        # --------------------------------------------------
        # NVR Summary
        # --------------------------------------------------

        log("-" * 60)

        log(f"NVR     : {nvr['name']}")

        log("Status  : OFFLINE")

        log(f"Total   : {total}")

        log(f"Online  : {online}")

        log(f"Offline : {offline}")

        log("=" * 60)

        return

    # ------------------------------------------------------
    # STEP 2: NVR is ONLINE
    # ------------------------------------------------------

    log(f"NVR ONLINE : {nvr['name']}")

    cameras = get_cameras(nvr)

    if not cameras:

        log("No Cameras Found")

        return

    total = len(cameras)

    online = 0
    offline = 0

    # ------------------------------------------------------
    # STEP 3: Check individual cameras
    # ------------------------------------------------------

    for camera in cameras:

        try:

            process_camera(
                nvr,
                camera
            )

            key = (
                f"{nvr['name']}_"
                f"{camera['id']}"
            )

            state = CAMERA_STATUS.get(
                key,
                False
            )

            if state:

                online += 1

            else:

                offline += 1

        except Exception as e:

            log(
                f"{camera['name']} Error : {e}"
            )

            offline += 1

    # ------------------------------------------------------
    # NVR Summary
    # ------------------------------------------------------

    log("-" * 60)

    log(f"NVR     : {nvr['name']}")

    log("Status  : ONLINE")

    log(f"Total   : {total}")

    log(f"Online  : {online}")

    log(f"Offline : {offline}")

    log("=" * 60)


# ==========================================================
# Scan All NVRs
# ==========================================================

def scan_all_nvrs():

    total_cameras = 0

    total_online = 0

    total_offline = 0

    start = time.time()

    log("")

    log("=" * 70)

    log("VisionGuard AI Enterprise Scan Started")

    log("=" * 70)

    for nvr in NVRS:

        try:

            check_nvr(

                nvr

            )

        except Exception as e:

            log(

                f"{nvr['name']} Scan Error : {e}"

            )

    for key, state in CAMERA_STATUS.items():

        total_cameras += 1

        if state:

            total_online += 1

        else:

            total_offline += 1

    elapsed = round(

        time.time() - start,

        2

    )

    log("=" * 70)

    log("Enterprise Scan Completed")

    log(f"Total Cameras : {total_cameras}")

    log(f"Online        : {total_online}")

    log(f"Offline       : {total_offline}")

    log(f"Scan Time     : {elapsed} sec")

    log("=" * 70)
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 7 / 10
# Background Monitor Thread
# ==========================================================

MONITOR_RUNNING = False

MONITOR_THREAD = None


# ==========================================================
# Monitor Loop
# ==========================================================

def monitor():

    global MONITOR_RUNNING

    log("=" * 70)
    log("VisionGuard Video Monitor Started")
    log("=" * 70)

    MONITOR_RUNNING = True

    while MONITOR_RUNNING:

        try:

            scan_all_nvrs()

        except Exception as e:

            log(f"Monitor Error : {e}")

        time.sleep(CHECK_INTERVAL)


# ==========================================================
# Start Monitor
# ==========================================================

def start_video_monitor():

    global MONITOR_THREAD

    if MONITOR_THREAD is not None:

        if MONITOR_THREAD.is_alive():

            log("Video Monitor Already Running")

            return

    MONITOR_THREAD = threading.Thread(

        target=monitor,

        daemon=True,

        name="VisionGuardVideoMonitor"

    )

    MONITOR_THREAD.start()

    log("Video Monitor Started Successfully")


# ==========================================================
# Stop Monitor
# ==========================================================

def stop_video_monitor():

    global MONITOR_RUNNING

    MONITOR_RUNNING = False

    log("Stopping Video Monitor...")

    if MONITOR_THREAD is not None:

        MONITOR_THREAD.join(timeout=5)

    log("Video Monitor Stopped")


# ==========================================================
# Monitor Status
# ==========================================================

def monitor_status():

    if MONITOR_THREAD is None:

        return False

    return MONITOR_THREAD.is_alive()


# ==========================================================
# Restart Monitor
# ==========================================================

def restart_video_monitor():

    stop_video_monitor()

    time.sleep(2)

    start_video_monitor()
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 8 / 10
# Event History & Statistics
# ==========================================================

MAX_HISTORY = 1000


# ==========================================================
# Add Event
# ==========================================================

def add_event(
    camera,
    nvr,
    status,
    ip="",
    downtime=""
):

    event = {

        "time": current_time(),

        "camera": camera,

        "nvr": nvr,

        "ip": ip,

        "status": status,

        "downtime": downtime

    }

    EVENT_HISTORY.append(event)

    if len(EVENT_HISTORY) > MAX_HISTORY:

        EVENT_HISTORY.pop(0)


# ==========================================================
# Get Event History
# ==========================================================

def get_event_history():

    return EVENT_HISTORY.copy()


# ==========================================================
# Clear History
# ==========================================================

def clear_event_history():

    EVENT_HISTORY.clear()

    log("Event History Cleared")


# ==========================================================
# Statistics
# ==========================================================

def get_statistics():

    total = len(CAMERA_STATUS)

    online = 0

    offline = 0

    for status in CAMERA_STATUS.values():

        if status:

            online += 1

        else:

            offline += 1

    return {

        "total": total,

        "online": online,

        "offline": offline,

        "alerts": len(EVENT_HISTORY),

        "loss_alerts": len(LOSS_ALERT_SENT),

        "restore_alerts": len(RESTORE_ALERT_SENT)

    }


# ==========================================================
# Print Statistics
# ==========================================================

def print_statistics():

    stats = get_statistics()

    log("=" * 60)

    log("VisionGuard Enterprise Statistics")

    log("=" * 60)

    log(f"Total Cameras : {stats['total']}")

    log(f"Online        : {stats['online']}")

    log(f"Offline       : {stats['offline']}")

    log(f"Events        : {stats['alerts']}")

    log(f"Loss Alerts   : {stats['loss_alerts']}")

    log(f"Recovery      : {stats['restore_alerts']}")

    log("=" * 60)


# ==========================================================
# Print Recent Events
# ==========================================================

def print_recent_events(limit=10):

    log("=" * 60)

    log("Recent Events")

    log("=" * 60)

    events = EVENT_HISTORY[-limit:]

    if not events:

        log("No Events")

        return

    for event in events:

        log(

            f"[{event['time']}] "

            f"{event['camera']} | "

            f"{event['status']} | "

            f"{event['nvr']}"

        )

    log("=" * 60)
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 9 / 10
# Startup, Health & FastAPI Integration
# ==========================================================

START_TIME = datetime.now()


# ==========================================================
# Engine Health
# ==========================================================

def health():

    uptime = datetime.now() - START_TIME

    return {

        "status": "running" if monitor_status() else "stopped",

        "uptime": str(uptime).split(".")[0],

        "total_cameras": len(CAMERA_STATUS),

        "offline_cameras": sum(

            1

            for status in CAMERA_STATUS.values()

            if not status

        ),

        "events": len(EVENT_HISTORY)

    }


# ==========================================================
# Print Health
# ==========================================================

def print_health():

    h = health()

    log("=" * 60)

    log("VisionGuard Enterprise Health")

    log("=" * 60)

    log(f"Status    : {h['status']}")

    log(f"Uptime    : {h['uptime']}")

    log(f"Cameras   : {h['total_cameras']}")

    log(f"Offline   : {h['offline_cameras']}")

    log(f"Events    : {h['events']}")

    log("=" * 60)


# ==========================================================
# Startup
# ==========================================================

def startup():

    log("=" * 70)

    log("VisionGuard AI Enterprise Starting")

    log("=" * 70)

    start_video_monitor()

    log("Startup Completed")


# ==========================================================
# Shutdown
# ==========================================================

def shutdown():

    log("=" * 70)

    log("VisionGuard AI Enterprise Stopping")

    log("=" * 70)

    stop_video_monitor()

    log("Shutdown Completed")


# ==========================================================
# Force Refresh Camera Cache
# ==========================================================

def refresh_camera_cache():

    CAMERA_CACHE.clear()

    log("Refreshing Camera Cache...")

    for nvr in NVRS:

        try:

            load_camera_cache(nvr)

        except Exception as e:

            log(

                f"{nvr['name']} Cache Error : {e}"

            )

    log("Camera Cache Updated")


# ==========================================================
# Manual Scan
# ==========================================================

def manual_scan():

    log("Manual Scan Started")

    scan_all_nvrs()

    print_statistics()

    print_recent_events()
# ==========================================================
# VisionGuard AI Enterprise Video Monitoring Engine
# PART 10 / 10
# Main Entry Point
# ==========================================================

def run():

    startup()

    try:

        while True:

            time.sleep(60)

    except KeyboardInterrupt:

        log("Keyboard Interrupt Received")

        shutdown()

    except Exception as e:

        log(f"Fatal Error : {e}")

        shutdown()


# ==========================================================
# Export Functions
# ==========================================================

__all__ = [

    "start_video_monitor",

    "stop_video_monitor",

    "restart_video_monitor",

    "monitor_status",

    "manual_scan",

    "refresh_camera_cache",

    "get_statistics",

    "get_event_history",

    "clear_event_history",

    "health",

    "print_health"

]


# ==========================================================
# Banner
# ==========================================================

log("=" * 70)

log("VisionGuard AI Enterprise Video Monitor Loaded")

log("=" * 70)


# ==========================================================
# Direct Run
# ==========================================================

if __name__ == "__main__":

    run()
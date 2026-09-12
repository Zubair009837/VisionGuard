# ==========================================================
# VisionGuard AI Enterprise Recording Engine v2
# Enterprise Recording Monitor (Part 1/4)
# ==========================================================

import threading
import time
import uuid
import requests
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta
from requests.auth import HTTPDigestAuth

# ==========================================================
# Import Config
# ==========================================================

try:
    from .config import NVRS, RECORDING_LOSS_THRESHOLD_SECONDS, RECORDING_INDEX_DELAY_SECONDS, RECORDING_SEARCH_WINDOW_SECONDS
except Exception:
    NVRS = []
    RECORDING_INDEX_DELAY_SECONDS = 600
    RECORDING_SEARCH_WINDOW_SECONDS = 1800

try:
    from .alert_manager import add_alert
except Exception:

    def add_alert(*args, **kwargs):
        print("[ALERT]", args, kwargs)

try:
    from .email_service import (
        send_recording_loss_email,
        send_recording_recovery_email,
    )
except Exception:

    def send_recording_loss_email(*args, **kwargs):
        pass

    def send_recording_recovery_email(*args, **kwargs):
        pass


# ==========================================================
# Enterprise Settings
# ==========================================================

CHECK_INTERVAL = 30

RECHECK_DELAY = 0

RECORDING_GAP_THRESHOLD = RECORDING_LOSS_THRESHOLD_SECONDS

SEARCH_WINDOW = RECORDING_SEARCH_WINDOW_SECONDS
# Fast mode: current recording window is evaluated immediately.
RECORDING_INDEX_DELAY = RECORDING_INDEX_DELAY_SECONDS

REQUEST_TIMEOUT = 15


# ==========================================================
# Global Runtime
# ==========================================================

RUNNING = False

THREAD = None

LOCK = threading.Lock()

ACTIVE_LOSSES = {}

LOSS_HISTORY = []

TRACK_CACHE = {}

PENDING_VERIFICATION = {}
NVR_RECORDING_OUTAGES = {}


# ==========================================================
# Date Helpers
# ==========================================================

def now():
    return datetime.now()


def format_time(dt=None):

    if dt is None:
        dt = now()

    return dt.strftime("%d-%m-%Y %I:%M:%S %p")


def format_duration(seconds):

    seconds = int(max(0, seconds))

    h, r = divmod(seconds, 3600)

    m, s = divmod(r, 60)

    if h:
        return f"{h}h {m}m {s}s"

    if m:
        return f"{m}m {s}s"

    return f"{s}s"


# ==========================================================
# NVR Helper
# ==========================================================

def nvr_value(nvr, *keys, default=None):

    for key in keys:

        if isinstance(nvr, dict):

            if key in nvr:
                return nvr[key]

        elif hasattr(nvr, key):

            return getattr(nvr, key)

    return default


# ==========================================================
# Hikvision Request
# ==========================================================

def hik_request(
    nvr,
    endpoint,
    method="GET",
    body=None,
    quiet=False,
):

    host = nvr_value(nvr, "ip", "host", default="")
    port = nvr_value(nvr, "port", default=80)
    user = nvr_value(nvr, "username", "user", default="")
    password = nvr_value(nvr, "password", "pass", default="")

    if not host:
        return None

    url = f"http://{host}:{port}{endpoint}"

    try:

        response = requests.request(

            method,

            url,

            auth=HTTPDigestAuth(user, password),

            data=body,

            headers={
                "Content-Type": "application/xml"
            },

            timeout=REQUEST_TIMEOUT

        )

        if response.status_code != 200:

            if not quiet:

                print(
                    f"[HTTP {response.status_code}]",
                    url
                )

            return None

        return response.text

    except Exception as exc:

        if not quiet:
            print(exc)

        return None


# ==========================================================
# Camera Discovery
# ==========================================================

def get_cameras(nvr):

    xml = hik_request(
        nvr,
        "/ISAPI/ContentMgmt/InputProxy/channels"
    )

    if not xml:
        return []

    cameras = []

    try:

        root = ET.fromstring(xml)

        for item in root.findall(".//{*}InputProxyChannel"):

            node_id = item.find("{*}id")

            node_name = item.find("{*}name")

            if node_id is None:
                continue

            channel = int(node_id.text)

            if (
                node_name is not None
                and node_name.text
            ):
                name = node_name.text.strip()
            else:
                name = f"Camera {channel}"

            cameras.append({

                "id": channel,

                "name": name

            })

    except Exception as exc:

        print(
            "[Camera Parse Error]",
            exc
        )

    return cameras


# ==========================================================
# Track Candidates
# ==========================================================

def get_track_candidates(
    nvr,
    channel
):

    host = nvr_value(
        nvr,
        "ip",
        "host",
        default=""
    )

    cache_key = f"{host}:{channel}"

    result = []

    cached = TRACK_CACHE.get(cache_key)

    if cached:

        result.append(cached)

    result.extend([

        channel * 100 + 1,

        channel * 100 + 2,

        channel,

        channel + 100,

        channel + 200,

        channel + 1000

    ])

    unique = []

    for value in result:

        try:
            value = int(value)
        except:
            continue

        if value not in unique:
            unique.append(value)

    return unique


print("VisionGuard Enterprise Recording Engine v2 Loaded")
# ==========================================================
# Build Recording Search XML
# ==========================================================

def build_search_xml(
    search_id,
    track_id,
    start_time,
    end_time
):

    start = start_time.strftime(
        "%Y-%m-%dT%H:%M:%S+05:30"
    )

    end = end_time.strftime(
        "%Y-%m-%dT%H:%M:%S+05:30"
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<CMSearchDescription>

<searchID>{search_id}</searchID>

<trackList>
<trackID>{track_id}</trackID>
</trackList>

<timeSpanList>

<timeSpan>

<startTime>{start}</startTime>

<endTime>{end}</endTime>

</timeSpan>

</timeSpanList>

<maxResults>1000</maxResults>

<searchResultPosition>0</searchResultPosition>

<metadataList>

<metadataDescriptor>
//recordType.meta.std-cgi.com
</metadataDescriptor>

</metadataList>

</CMSearchDescription>
"""


# ==========================================================
# Parse Recording Result
# ==========================================================

def parse_recordings(xml):

    recordings = []

    if not xml:
        return recordings

    try:

        root = ET.fromstring(xml)

    except Exception:

        return recordings

    for item in root.findall(".//{*}searchMatchItem"):

        s = item.find(".//{*}startTime")

        e = item.find(".//{*}endTime")

        if s is None or e is None:
            continue

        try:

            start = datetime.fromisoformat(
                s.text.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            end = datetime.fromisoformat(
                e.text.replace("Z", "+00:00")
            ).replace(tzinfo=None)

            recordings.append({

                "start": start,

                "end": end

            })

        except Exception:

            pass

    recordings.sort(
        key=lambda x: x["start"]
    )

    return recordings


# ==========================================================
# Recording Search
# ==========================================================

def search_recording(
    nvr,
    channel,
    start_time,
    end_time
):

    host = nvr_value(
        nvr,
        "ip",
        "host",
        default=""
    )

    cache_key = f"{host}:{channel}"

    tracks = get_track_candidates(
        nvr,
        channel
    )

    for track in tracks:

        xml = build_search_xml(

            str(uuid.uuid4()),

            track,

            start_time,

            end_time

        )

        result = hik_request(

            nvr,

            "/ISAPI/ContentMgmt/search",

            method="POST",

            body=xml,

            quiet=True

        )

        if not result:
            continue

        lower = result.lower()

        if "invalid track id" in lower:
            continue

        clips = parse_recordings(result)

        if clips:

            TRACK_CACHE[cache_key] = track

            return clips

        if "<responsestatus>true" in lower:

            TRACK_CACHE[cache_key] = track

            return []

    return []


# ==========================================================
# Recording Gap Detection
# ==========================================================

def find_gap(
    recordings,
    current_time
):

    if not recordings:
        return None

    last_end = recordings[0]["end"]

    for clip in recordings[1:]:

        gap = (

            clip["start"]

            -

            last_end

        ).total_seconds()

        if gap > RECORDING_GAP_THRESHOLD:

            return {

                "start": last_end,

                "end": clip["start"],

                "duration": int(gap)

            }

        last_end = max(

            last_end,

            clip["end"]

        )

    tail_gap = (

        current_time

        -

        last_end

    ).total_seconds()

    if tail_gap > RECORDING_GAP_THRESHOLD:

        return {

            "start": last_end,

            "end": current_time,

            "duration": int(tail_gap)

        }

    return None


# ==========================================================
# Enterprise Double Verification
# ==========================================================

# ==========================================================
# Enterprise Double Verification
# ==========================================================

def verify_gap(nvr, camera, gap):

    key = f"{nvr_value(nvr,'name')}:{camera['id']}"

    current = now()

    pending = PENDING_VERIFICATION.get(key)

    # First Detection
    if pending is None:

        PENDING_VERIFICATION[key] = {
            "first_seen": current,
            "gap": gap
        }

        return None

    # --------------------------------------------------
    # Agar recording gap abhi 5 minute se kam hai
    # to mail mat bhejo.
    # Hikvision aksar recording 2-5 minute baad index karta hai.
    # --------------------------------------------------

    if gap["duration"] < RECORDING_GAP_THRESHOLD:
        return None

    # Double verification (30 sec)
    elapsed = (current - pending["first_seen"]).total_seconds()

    if elapsed < RECHECK_DELAY:
        return None

    del PENDING_VERIFICATION[key]

    return gap


# ==========================================================
# Clear Verification
# ==========================================================

def clear_verification(
    nvr,
    camera
):

    key = (

        f"{nvr_value(nvr,'name')}"

        f":{camera['id']}"

    )

    if key in PENDING_VERIFICATION:

        del PENDING_VERIFICATION[key]
# ==========================================================
# Recording Loss Reason / Diagnostic
# ==========================================================
def _parse_bool_text(value):
    if value is None:
        return None
    value = str(value).strip().lower()
    if value in {"true", "1", "yes", "on", "enabled", "enable"}:
        return True
    if value in {"false", "0", "no", "off", "disabled", "disable"}:
        return False
    return None


def _channel_diagnostics(nvr, channel):
    """Read live channel state from Hikvision for evidence-based diagnosis."""
    result = {
        "enabled": None,
        "record_enabled": None,
        "online": None,
        "detect": None,
        "record_status": None,
    }

    # Channel configuration: enabled / recording flags.
    try:
        xml = hik_request(
            nvr,
            f"/ISAPI/ContentMgmt/InputProxy/channels/{int(channel)}",
            quiet=True,
        )
        if xml:
            root = ET.fromstring(xml)
            for node in root.iter():
                name = node.tag.rsplit("}", 1)[-1].lower()
                text = (node.text or "").strip()
                if not text:
                    continue
                if name in {"enabled", "enable"} and result["enabled"] is None:
                    result["enabled"] = _parse_bool_text(text)
                if name in {
                    "enablerecord", "recordenable", "recordenabled",
                    "recordingenable", "recordingenabled"
                } and result["record_enabled"] is None:
                    result["record_enabled"] = _parse_bool_text(text)
    except Exception:
        pass

    # Live camera/input state.  This is useful for distinguishing a
    # recording/storage problem from a camera/video-signal problem.
    try:
        xml = hik_request(
            nvr,
            "/ISAPI/ContentMgmt/InputProxy/channels/status",
            quiet=True,
        )
        if xml:
            root = ET.fromstring(xml)
            for item in root.findall(".//{*}InputProxyChannelStatus"):
                node = item.find("{*}id")
                if node is None or str(node.text).strip() != str(channel):
                    continue
                online = item.find("{*}online")
                detect = item.find("{*}chanDetectResult")
                if online is not None:
                    result["online"] = _parse_bool_text(online.text)
                if detect is not None and detect.text:
                    result["detect"] = detect.text.strip()
                break
    except Exception:
        pass

    # Firmware-dependent record-status resources.  Not every NVR exposes
    # these, so failure to read them is deliberately treated as UNKNOWN.
    endpoints = [
        "/ISAPI/System/Video/inputs/streams/recordStatus",
        f"/ISAPI/ContentMgmt/channels/{int(channel)}/record",
        f"/ISAPI/ContentMgmt/channels/{int(channel)}/record/status",
        f"/ISAPI/ContentMgmt/channels/{int(channel)}/recordStatus",
    ]
    for endpoint in endpoints:
        try:
            xml = hik_request(nvr, endpoint, quiet=True)
            if not xml:
                continue
            root = ET.fromstring(xml)
            values = []
            for node in root.iter():
                name = node.tag.rsplit("}", 1)[-1].lower()
                if name in {"recordstatus", "status", "recordingstatus"} and node.text:
                    values.append(node.text.strip())
            if values:
                result["record_status"] = values[0]
                break
        except Exception:
            continue

    return result


def _storage_diagnostics(nvr):
    """Return current storage evidence without treating unavailable telemetry as healthy."""
    try:
        from .storage_monitor import get_storage
        items = get_storage(force=True)
        target = nvr_value(nvr, "name", default="NVR")
        item = next((x for x in items if x.get("name") == target), None)
        if not item:
            return None
        return item
    except Exception as exc:
        print("[Recording Diagnostic] storage check failed:", exc)
        return None


def diagnose_recording_loss(nvr, camera, gap, recordings):
    """Diagnose a recording gap from live NVR evidence.

    Important: ISAPI normally tells us the *current* state.  It cannot always
    prove what happened several minutes ago.  Therefore this function only
    labels a root cause when the NVR currently exposes direct evidence; otherwise
    it reports that no root cause is currently proven instead of guessing.
    """
    nvr_name = nvr_value(nvr, "name", default="NVR")
    channel = camera.get("id")

    # 1) NVR reachability.
    status_xml = hik_request(nvr, "/ISAPI/System/status", quiet=True)
    if not status_xml:
        return (
            "DETECTED REASON: NVR UNREACHABLE\n"
            f"Evidence: {nvr_name} did not respond to /ISAPI/System/status during verification.\n"
            "This is the strongest detected cause for the recording interruption."
        )

    # 2) Channel configuration and live video state.
    channel_state = _channel_diagnostics(nvr, channel)

    if channel_state.get("enabled") is False:
        return (
            "DETECTED REASON: CHANNEL DISABLED\n"
            f"Evidence: CH-{channel} is currently disabled in the NVR channel configuration.\n"
            "Recording cannot be expected while the channel is disabled."
        )

    if channel_state.get("record_enabled") is False:
        return (
            "DETECTED REASON: RECORDING DISABLED\n"
            f"Evidence: CH-{channel} reports recording disabled in the NVR configuration.\n"
            "This directly explains why recording is unavailable for the channel."
        )

    # 3) Camera/video signal.
    detect = str(channel_state.get("detect") or "").strip().lower()
    if channel_state.get("online") is False or any(
        token in detect for token in ("nosignal", "no signal", "offline", "disconnect", "lost")
    ):
        detail = channel_state.get("detect") or "online=false"
        return (
            "DETECTED REASON: CAMERA VIDEO SIGNAL LOST\n"
            f"Evidence: CH-{channel} currently reports {detail}.\n"
            "The NVR is reachable, but the camera/input is not providing a normal video signal."
        )

    # 4) HDD / storage evidence.
    storage = _storage_diagnostics(nvr)
    if storage:
        hdds = storage.get("hdds") or []
        bad = [
            d for d in hdds
            if str(d.get("status", "")).strip().lower()
            not in {"ok", "normal", "healthy", "online"}
        ]
        if bad:
            statuses = ", ".join(
                f"HDD {d.get('id', '?')}: {d.get('status', 'unknown')}"
                for d in bad
            )
            return (
                "DETECTED REASON: HDD / STORAGE FAULT\n"
                f"Evidence: {statuses}.\n"
                "The NVR is reachable but its storage reports a non-healthy state; this can stop recording."
            )

        # Storage percentage alone is not treated as a recording fault because normal NVR overwrite is expected.

    # 5) Live recording-status evidence, when the firmware exposes it.
    record_status = str(channel_state.get("record_status") or "").strip().lower()
    if record_status in {"pause", "paused", "idle", "stop", "stopped", "disabled"}:
        return (
            "DETECTED REASON: RECORDING NOT ACTIVE\n"
            f"Evidence: CH-{channel} record status is '{channel_state.get('record_status')}'.\n"
            "The NVR is reachable, but its live recording-status endpoint reports that recording is not active."
        )

    # 6) No direct fault found.  Do NOT invent a root cause.
    evidence = [f"NVR reachable: YES", f"CH-{channel} enabled: {channel_state.get('enabled')}"]
    if channel_state.get("record_enabled") is not None:
        evidence.append(f"Recording enabled: {channel_state.get('record_enabled')}")
    if channel_state.get("online") is not None:
        evidence.append(f"Camera online: {channel_state.get('online')}")
    if channel_state.get("detect"):
        evidence.append(f"Video detect state: {channel_state.get('detect')}")
    if storage:
        evidence.append(f"Storage status: {storage.get('status', 'UNKNOWN')}")
        if storage.get("used_percent") is not None:
            evidence.append(f"Storage used: {storage.get('used_percent')}%")
    if record_status:
        evidence.append(f"Record status: {channel_state.get('record_status')}")

    return (
        "DETECTED REASON: NO HARDWARE/CONFIGURATION FAULT CURRENTLY PROVEN\n"
        f"Evidence: {'; '.join(evidence)}.\n"
        f"A recording gap of {format_duration(gap['duration'])} is confirmed for CH-{channel}, "
        "but the current NVR diagnostics do not expose a direct root cause. "
        "Most consistent with a temporary recording/indexing interruption; exact historical cause cannot be proven from the current ISAPI state."
    )


# ==========================================================
# Enterprise Recording Loss Alert
# ==========================================================

def send_recording_loss_alert(
    nvr_name,
    nvr_ip,
    camera_name,
    camera_id,
    gap,
    reason="Recording gap verified by Hikvision search."
):

    key = f"{nvr_name}:{camera_id}"

    # Duplicate Protection
    if key in ACTIVE_LOSSES:
        return

    ACTIVE_LOSSES[key] = {

        "nvr": nvr_name,
        "nvr_ip": nvr_ip,
        "camera": camera_name,
        "camera_id": camera_id,

        "loss_start": gap["start"],
        "loss_end": gap["end"],

        "status": "RECORDING LOST",
        "reason": reason,

        "created": now()

    }

    print("\n" + "=" * 70)
    print("[CRITICAL] RECORDING LOSS")
    print("=" * 70)
    print("NVR      :", nvr_name)
    print("Camera   :", camera_name)
    print("Channel  :", camera_id)
    print("IP       :", nvr_ip)
    print("From     :", format_time(gap["start"]))
    print("To       :", format_time(gap["end"]))
    print("Duration :", format_duration(gap["duration"]))
    print("Reason   :", reason)
    print("=" * 70)

    try:

        add_alert(

            alert_type="RECORDING LOSS",

            severity="CRITICAL",

            title=f"Recording Loss - {camera_name}",

            description=(
                f"NVR : {nvr_name}\n"
                f"Camera : {camera_name}\n"
                f"IP : {nvr_ip}\n"
                f"Recording Missing\n"
                f"Reason : {reason}"
            )

        )

    except Exception:
        pass

    try:

        send_recording_loss_email(

            camera=camera_name,

            nvr=nvr_name,

            ip=nvr_ip,

            loss_from=format_time(gap["start"]),

            loss_to=format_time(gap["end"]),

            duration=format_duration(gap["duration"]),

            reason=reason

        )

    except Exception as exc:

        print("EMAIL ERROR :", exc)


# ==========================================================
# Recording Recovery Alert
# ==========================================================

def send_recording_recovery_alert(key):

    if key not in ACTIVE_LOSSES:
        return

    event = ACTIVE_LOSSES[key]

    restore_time = now()

    duration = int(

        (
            restore_time

            -

            event["loss_start"]

        ).total_seconds()

    )

    print("\n" + "=" * 70)
    print("[RECOVERY]")
    print("=" * 70)
    print("NVR      :", event["nvr"])
    print("Camera   :", event["camera"])
    print("IP       :", event["nvr_ip"])
    print("Restored :", format_time(restore_time))
    print("=" * 70)

    try:

        send_recording_recovery_email(

            camera=event["camera"],

            nvr=event["nvr"],

            ip=event["nvr_ip"],

            loss_from=format_time(event["loss_start"]),

            loss_to=format_time(event["loss_end"]),

            restored_at=format_time(restore_time),

            duration=format_duration(duration)

        )

    except Exception as exc:

        print("Recovery Email Error :", exc)

    LOSS_HISTORY.append({

        **event,

        "restored": restore_time,

        "duration": duration

    })

    del ACTIVE_LOSSES[key]


# ==========================================================
# Check Single Camera
# ==========================================================

def check_camera(
    nvr,
    camera
):

    nvr_name = nvr_value(
        nvr,
        "name",
        default="NVR"
    )

    nvr_ip = nvr_value(
        nvr,
        "ip",
        default=""
    )

    current = now()
    # Fast recording-loss mode: evaluate the live/current window instead of
    # waiting for Hikvision's historical indexing tail.  The configured
    # threshold is now 60 seconds, so one full minute without a searchable
    # recording can raise an alert.
    finalized_end = current - timedelta(seconds=RECORDING_INDEX_DELAY)
    start = finalized_end - timedelta(seconds=max(SEARCH_WINDOW, RECORDING_GAP_THRESHOLD))
    recordings = search_recording(nvr, camera["id"], start, finalized_end)
    gap = find_gap(recordings, finalized_end)
    if not recordings:
        gap_start = finalized_end - timedelta(seconds=RECORDING_GAP_THRESHOLD)
        gap = {"start": gap_start, "end": finalized_end, "duration": RECORDING_GAP_THRESHOLD}

    key = f"{nvr_name}:{camera['id']}"

    # Recording OK

    if gap is None:

        clear_verification(
            nvr,
            camera
        )

        if key in ACTIVE_LOSSES:

            send_recording_recovery_alert(
                key
            )

        return

    # Double Verification

    verified = verify_gap(

        nvr,

        camera,

        gap

    )

    if verified is None:

        return

    reason = diagnose_recording_loss(
        nvr,
        camera,
        verified,
        recordings,
    )

    send_recording_loss_alert(

        nvr_name,

        nvr_ip,

        camera["name"],

        camera["id"],

        verified,

        reason=reason

    )
# ==========================================================
# Scan One NVR
# ==========================================================

def scan_nvr(nvr):

    nvr_name = nvr_value(
        nvr,
        "name",
        default="NVR"
    )

    print(f"[RECORDING] Scanning {nvr_name}")

    cameras = get_cameras(nvr)

    if not cameras:

        print(
            f"[RECORDING] {nvr_name} : No Cameras Found"
        )

        return

    print(
        f"[RECORDING] {nvr_name}: "
        f"{len(cameras)} Cameras"
    )

    for camera in cameras:
        try:
            check_camera(nvr, camera)
        except Exception as exc:
            print("[RECORDING]", camera.get("name"), exc)

    # NVR-wide outage: if most/all channels have an active confirmed
    # recording loss for the configured threshold, alert at NVR level.
    try:
        from .config import NVR_RECORDING_OUTAGE_ENABLED, NVR_RECORDING_OUTAGE_THRESHOLD_SECONDS, NVR_RECORDING_OUTAGE_MIN_CAMERA_PERCENT
        from .email_service import send_nvr_health_email
        if NVR_RECORDING_OUTAGE_ENABLED and cameras:
            nvr_name = nvr_value(nvr, "name", default="NVR")
            active = [x for x in ACTIVE_LOSSES.values() if x.get("nvr") == nvr_name]
            ratio = len(active) / max(1, len(cameras))
            oldest = min((x.get("loss_start") for x in active if x.get("loss_start")), default=None)
            duration = (now() - oldest).total_seconds() if oldest else 0
            if ratio >= float(NVR_RECORDING_OUTAGE_MIN_CAMERA_PERCENT) and duration >= int(NVR_RECORDING_OUTAGE_THRESHOLD_SECONDS):
                if nvr_name not in NVR_RECORDING_OUTAGES:
                    NVR_RECORDING_OUTAGES[nvr_name] = {"started": oldest, "camera_count": len(active), "total": len(cameras)}
                    send_nvr_health_email(nvr=nvr_name, ip=nvr_value(nvr, "ip", default=""), severity="CRITICAL", title="NVR RECORDING OUTAGE", description=f"{len(active)}/{len(cameras)} cameras have confirmed recording loss for about {format_duration(duration)}. This indicates the NVR may not be recording.", metric=f"Affected cameras: {len(active)}/{len(cameras)}", threshold=f"{NVR_RECORDING_OUTAGE_THRESHOLD_SECONDS}s", event_time=format_time())
                    print(f"🚨 [NVR RECORDING OUTAGE] {nvr_name} | {len(active)}/{len(cameras)} | {format_duration(duration)}")
            elif nvr_name in NVR_RECORDING_OUTAGES and ratio < float(NVR_RECORDING_OUTAGE_MIN_CAMERA_PERCENT):
                event = NVR_RECORDING_OUTAGES.pop(nvr_name)
                send_nvr_health_email(nvr=nvr_name, ip=nvr_value(nvr, "ip", default=""), severity="INFO", title="NVR RECORDING RECOVERED", description=f"NVR recording outage condition cleared. Active recording-loss channels are now {len(active)}/{len(cameras)}.", metric=f"Affected cameras: {len(active)}/{len(cameras)}", threshold=f"{NVR_RECORDING_OUTAGE_THRESHOLD_SECONDS}s", event_time=format_time())
    except Exception as exc:
        print("[NVR RECORDING OUTAGE]", exc)


# ==========================================================
# Scan All NVRs
# ==========================================================

def scan_all():

    for nvr in NVRS:

        try:

            scan_nvr(nvr)

        except Exception as exc:

            print(
                "[SCAN ERROR]",
                exc
            )


# ==========================================================
# Monitor Loop
# ==========================================================

def monitor_loop():

    global RUNNING

    print("=" * 70)
    print("[RECORDING] Enterprise Recording Monitor Started")
    print(f"Threshold : {RECORDING_GAP_THRESHOLD}s")
    print(f"Recheck   : {RECHECK_DELAY}s")
    print(f"Interval  : {CHECK_INTERVAL}s")
    print("=" * 70)

    while RUNNING:

        try:

            scan_all()

        except Exception as exc:

            print(
                "[MONITOR]",
                exc
            )

        time.sleep(CHECK_INTERVAL)


# ==========================================================
# Start Monitor
# ==========================================================

def start_recording_monitor():

    global THREAD
    global RUNNING

    if THREAD and THREAD.is_alive():

        print(
            "[RECORDING] Already Running"
        )

        return

    RUNNING = True

    THREAD = threading.Thread(

        target=monitor_loop,

        daemon=True,

        name="VisionGuardRecording"

    )

    THREAD.start()

    print(
        "Recording Loss Monitor Started Successfully"
    )


# ==========================================================
# Stop Monitor
# ==========================================================

def stop_recording_monitor():

    global RUNNING

    RUNNING = False

    print(
        "Recording Monitor Stopped"
    )


# ==========================================================
# APIs
# ==========================================================

def get_active_recording_losses():

    return list(
        ACTIVE_LOSSES.values()
    )


def get_recording_loss_history():

    return list(
        reversed(
            LOSS_HISTORY
        )
    )


def clear_recording_history():

    ACTIVE_LOSSES.clear()

    LOSS_HISTORY.clear()

    PENDING_VERIFICATION.clear()

    print(
        "[RECORDING] History Cleared"
    )


def get_statistics():

    return {

        "running":
            RUNNING,

        "active_losses":
            len(
                ACTIVE_LOSSES
            ),

        "history":
            len(
                LOSS_HISTORY
            ),

        "pending":
            len(
                PENDING_VERIFICATION
            ),

        "cached_tracks":
            len(
                TRACK_CACHE
            ),

        "interval":
            CHECK_INTERVAL,

        "threshold":
            RECORDING_GAP_THRESHOLD,

        "recheck":
            RECHECK_DELAY,

    }


# ==========================================================
# Manual Scan
# ==========================================================

def run_recording_scan():

    print(
        "[RECORDING] Manual Scan Started"
    )

    scan_all()

    print(
        "[RECORDING] Manual Scan Completed"
    )


# ==========================================================
# Module Loaded
# ==========================================================

print("=" * 70)
print("VisionGuard AI Enterprise Recording Engine v2 Loaded")
print("Double Verification Enabled")
print("Duplicate Email Protection Enabled")
print("Recovery Detection Enabled")
print("False Recording Alert Filter Enabled")
print("=" * 70)
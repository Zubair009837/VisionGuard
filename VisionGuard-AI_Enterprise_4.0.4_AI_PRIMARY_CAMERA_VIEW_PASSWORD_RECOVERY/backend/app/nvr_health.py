
"""Live NVR health telemetry and enterprise email alert generation."""

import threading
import time
import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.auth import HTTPDigestAuth

from .config import NVRS, ENABLE_NVR_HEALTH_EMAIL_ALERT
from .alert_manager import add_alert
from .email_service import send_nvr_health_email


TIMEOUT = 5
POLL_SECONDS = 5

CPU_WARN = 75
CPU_CRITICAL = 90

MEM_WARN = 80
MEM_CRITICAL = 90

TEMP_WARN = 70
TEMP_CRITICAL = 80

DISK_WARN = 90
DISK_CRITICAL = 98

ALERT_COOLDOWN = 60

_lock = threading.RLock()
_cache = {}
_alert_state = {}

_started = False
_thread = None

_HISTORY_FILE = __import__("pathlib").Path(__file__).with_name(
    "nvr_health_history.json"
)

_HISTORY_LIMIT = 5000


# ============================================================
# XML HELPERS
# ============================================================

def _lname(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _text(node, names, default=None):
    wanted = {str(n).lower() for n in names}

    for child in node.iter():
        if _lname(child.tag) in wanted and child.text:
            return child.text.strip()

    return default


def _float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# ============================================================
# HIKVISION API REQUEST
# ============================================================

def _get(nvr, endpoint):
    """
    Perform a Hikvision ISAPI GET request using Digest Authentication.

    Returns:
        Response text when successful.
        None when the request fails.
    """

    url = f"http://{nvr['ip']}:{nvr['port']}{endpoint}"

    try:
        response = requests.get(
            url,
            auth=HTTPDigestAuth(
                nvr["username"],
                nvr["password"],
            ),
            headers={
                "Accept": "application/xml",
            },
            timeout=TIMEOUT,
        )

        if response.ok and response.text:
            return response.text

        print(
            f"[NVR API] {nvr['name']} | "
            f"{endpoint} | HTTP {response.status_code}"
        )

    except requests.RequestException as exc:
        print(
            f"[NVR API] {nvr['name']} | "
            f"{endpoint} | {exc}"
        )

    return None


# ============================================================
# STATUS XML PARSER
# ============================================================

def _parse_status(xml_text):
    if not xml_text:
        return None

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------

    cpus = []

    for node in root.iter():

        if _lname(node.tag) == "cpu":

            value = _float(
                _text(
                    node,
                    (
                        "cpuUtilization",
                        "utilization",
                    ),
                )
            )

            if value is not None:

                cpus.append(
                    {
                        "description": _text(
                            node,
                            (
                                "cpuDescription",
                                "description",
                            ),
                            "CPU",
                        ),
                        "usage": max(
                            0,
                            min(
                                100,
                                round(value, 1),
                            ),
                        ),
                    }
                )

    # --------------------------------------------------------
    # MEMORY
    # --------------------------------------------------------

    memories = []

    for node in root.iter():

        if _lname(node.tag) == "memory":

            used = _float(
                _text(
                    node,
                    (
                        "memoryUsage",
                        "usage",
                    ),
                )
            )

            available = _float(
                _text(
                    node,
                    (
                        "memoryAvailable",
                        "available",
                    ),
                )
            )

            if used is not None:

                total = (
                    used + available
                    if available is not None
                    else None
                )

                memories.append(
                    {
                        "description": _text(
                            node,
                            (
                                "memoryDescription",
                                "description",
                            ),
                            "Memory",
                        ),
                        "used_mb": round(
                            used,
                            2,
                        ),
                        "available_mb": (
                            round(
                                available,
                                2,
                            )
                            if available is not None
                            else None
                        ),
                        "usage_percent": (
                            round(
                                (used / total) * 100,
                                1,
                            )
                            if total and total > 0
                            else None
                        ),
                    }
                )

    # --------------------------------------------------------
    # TEMPERATURE
    # --------------------------------------------------------

    temps = []

    temperature_tags = {
        "temperature",
        "tempsensor",
        "temperaturevalue",
        "devicetemperature",
        "chassistemperature",
        "boardtemperature",
    }

    temperature_value_tags = {
        "temperature",
        "temp",
        "temperaturevalue",
        "value",
        "currenttemperature",
        "celsius",
        "temperaturec",
    }

    for node in root.iter():

        lname = _lname(node.tag)

        value = None

        if (
            lname in temperature_tags
            and (node.text or "").strip()
        ):
            value = _float(node.text)

        if value is None and lname in temperature_tags:

            value = _float(
                _text(
                    node,
                    temperature_value_tags,
                )
            )

        if value is None:

            for child in node.iter():

                child_name = _lname(
                    child.tag
                )

                if (
                    child_name
                    in temperature_value_tags
                    and (child.text or "").strip()
                ):

                    value = _float(
                        child.text
                    )

                    if value is not None:
                        break

        if (
            value is not None
            and -40 <= value <= 150
        ):

            description = _text(
                node,
                (
                    "tempSensorDescription",
                    "temperatureDescription",
                    "description",
                    "name",
                ),
                "Temperature",
            )

            temps.append(
                {
                    "description": description,
                    "celsius": round(
                        value,
                        1,
                    ),
                }
            )

    # --------------------------------------------------------
    # UPTIME / DEVICE TIME
    # --------------------------------------------------------

    uptime = _float(
        _text(
            root,
            (
                "deviceUpTime",
                "uptime",
            ),
        )
    )

    current_time = _text(
        root,
        (
            "currentDeviceTime",
        ),
    )

    return {
        "cpus": cpus,

        "cpu_percent": (
            round(
                sum(
                    x["usage"]
                    for x in cpus
                )
                / len(cpus),
                1,
            )
            if cpus
            else None
        ),

        "memories": memories,

        "memory_percent": next(
            (
                x["usage_percent"]
                for x in memories
                if x["usage_percent"]
                is not None
            ),
            None,
        ),

        "temperatures": temps,

        "temperature_c": max(
            (
                x["celsius"]
                for x in temps
            ),
            default=None,
        ),

        "uptime_seconds": (
            round(uptime)
            if uptime is not None
            else None
        ),

        "device_time": current_time,
    }


# ============================================================
# EMAIL
# ============================================================

def _send_health_email(
    nvr,
    severity,
    title,
    description,
    metric="",
    threshold="",
    ip=None,
):
    """Send NVR health email."""

    if not ENABLE_NVR_HEALTH_EMAIL_ALERT:
        return

    try:

        send_nvr_health_email(
            nvr=nvr["name"],
            ip=ip or nvr.get(
                "ip",
                "",
            ),
            severity=severity,
            title=title,
            description=description,
            metric=metric,
            threshold=threshold,
            event_time=time.strftime(
                "%d-%m-%Y %I:%M:%S %p"
            ),
        )

    except Exception as exc:

        print(
            f"[NVR HEALTH EMAIL ERROR] "
            f"{nvr['name']}: {exc}"
        )


# ============================================================
# ALERT STATE
# ============================================================

def _alert_once(
    key,
    severity,
    title,
    description,
    *,
    active=True,
    email=None,
    confirm_readings=1,
):
    """Stateful alert with consecutive-reading confirmation."""

    now = time.time()

    state = _alert_state.get(
        key,
        {},
    )

    required = max(
        1,
        int(confirm_readings or 1),
    )

    if active:

        state["candidate"] = (
            int(
                state.get(
                    "candidate",
                    0,
                )
            )
            + 1
        )

        if (
            not state.get("active")
            and state["candidate"] < required
        ):

            _alert_state[key] = state
            return

        if (
            state.get("active")
            and now - state.get(
                "last",
                0,
            )
            < ALERT_COOLDOWN
        ):

            _alert_state[key] = state
            return

        add_alert(
            "NVR Health",
            severity,
            title,
            description,
        )

        if email:
            _send_health_email(
                **email
            )

        _alert_state[key] = {
            "active": True,
            "last": now,
            "severity": severity,
            "candidate": state[
                "candidate"
            ],
        }

    elif state.get("active"):

        add_alert(
            "NVR Recovery",
            "INFO",
            f"Recovered: {title}",
            description,
        )

        recovery_email = dict(
            email or {}
        )

        if recovery_email:

            recovery_email.update(
                {
                    "severity": "INFO",
                    "title": (
                        f"Recovered: {title}"
                    ),
                    "description": description,
                }
            )

            _send_health_email(
                **recovery_email
            )

        _alert_state[key] = {
            "active": False,
            "last": now,
            "severity": "INFO",
            "candidate": 0,
        }

    elif state:

        state["candidate"] = 0

        _alert_state[key] = state


# ============================================================
# NVR COLLECTION
# ============================================================

def _collect(nvr):
    """
    Collect live NVR health.

    IMPORTANT:
    A Hikvision NVR is not considered offline only because
    /ISAPI/System/status is unavailable.

    Fallback order:

        1. /ISAPI/System/status
        2. /ISAPI/System/deviceInfo
        3. /ISAPI/ContentMgmt/InputProxy/channels

    This allows NVR-10/11/12 to appear ONLINE when their
    HTTP/API port is reachable but their firmware does not
    expose /ISAPI/System/status.
    """

    started = time.perf_counter()

    # ========================================================
    # 1. PRIMARY HEALTH ENDPOINT
    # ========================================================

    xml = _get(
        nvr,
        "/ISAPI/System/status",
    )

    if xml:

        latency_ms = round(
            (
                time.perf_counter()
                - started
            )
            * 1000,
            1,
        )

        parsed = (
            _parse_status(xml)
            or {}
        )

        temperature_source = (
            "/ISAPI/System/status"
        )

        # ----------------------------------------------------
        # Temperature fallback endpoints
        # ----------------------------------------------------

        if (
            parsed.get(
                "temperature_c"
            )
            is None
        ):

            for endpoint in (
                "/ISAPI/System/Hardware",
                "/ISAPI/System/Hardware/temperature",
                "/ISAPI/System/temperature",
            ):

                hardware_xml = _get(
                    nvr,
                    endpoint,
                )

                if not hardware_xml:
                    continue

                hardware_parsed = (
                    _parse_status(
                        hardware_xml
                    )
                    or {}
                )

                if hardware_parsed.get(
                    "temperatures"
                ):

                    parsed[
                        "temperatures"
                    ] = hardware_parsed[
                        "temperatures"
                    ]

                    parsed[
                        "temperature_c"
                    ] = hardware_parsed.get(
                        "temperature_c"
                    )

                    temperature_source = (
                        endpoint
                    )

                    break

        print(
            f"🟢 {nvr['name']} ONLINE | "
            f"System/status OK | "
            f"{nvr['ip']}:{nvr['port']}"
        )

        return {
            "id": nvr["id"],
            "name": nvr["name"],
            "ip": nvr["ip"],
            "port": nvr["port"],
            "status": "ONLINE",
            "error": None,
            "latency_ms": latency_ms,
            "temperature_source": (
                temperature_source
                if parsed.get(
                    "temperature_c"
                )
                is not None
                else None
            ),
            **parsed,
        }

    # ========================================================
    # 2. DEVICE INFO FALLBACK
    # ========================================================

    device_info_xml = _get(
        nvr,
        "/ISAPI/System/deviceInfo",
    )

    if device_info_xml:

        latency_ms = round(
            (
                time.perf_counter()
                - started
            )
            * 1000,
            1,
        )

        print(
            f"🟢 {nvr['name']} ONLINE | "
            f"deviceInfo API OK | "
            f"{nvr['ip']}:{nvr['port']}"
        )

        return {
            "id": nvr["id"],
            "name": nvr["name"],
            "ip": nvr["ip"],
            "port": nvr["port"],
            "status": "ONLINE",
            "error": None,
            "latency_ms": latency_ms,
            "temperature_source": None,
            "cpus": [],
            "cpu_percent": None,
            "memories": [],
            "memory_percent": None,
            "temperatures": [],
            "temperature_c": None,
            "uptime_seconds": None,
            "device_time": None,
            "health_note": (
                "NVR is reachable. "
                "/ISAPI/System/status is unavailable, "
                "but /ISAPI/System/deviceInfo is responding."
            ),
        }

    # ========================================================
    # 3. CONTENT MANAGEMENT FALLBACK
    # ========================================================

    channels_xml = _get(
        nvr,
        "/ISAPI/ContentMgmt/InputProxy/channels",
    )

    if channels_xml:

        latency_ms = round(
            (
                time.perf_counter()
                - started
            )
            * 1000,
            1,
        )

        print(
            f"🟢 {nvr['name']} ONLINE | "
            f"ContentMgmt channels API OK | "
            f"{nvr['ip']}:{nvr['port']}"
        )

        return {
            "id": nvr["id"],
            "name": nvr["name"],
            "ip": nvr["ip"],
            "port": nvr["port"],
            "status": "ONLINE",
            "error": None,
            "latency_ms": latency_ms,
            "temperature_source": None,
            "cpus": [],
            "cpu_percent": None,
            "memories": [],
            "memory_percent": None,
            "temperatures": [],
            "temperature_c": None,
            "uptime_seconds": None,
            "device_time": None,
            "health_note": (
                "NVR is reachable through "
                "ContentMgmt/InputProxy/channels."
            ),
        }

    # ========================================================
    # 4. ALL API CHECKS FAILED
    # ========================================================

    latency_ms = round(
        (
            time.perf_counter()
            - started
        )
        * 1000,
        1,
    )

    print(
        f"🔴 {nvr['name']} OFFLINE | "
        f"All Hikvision API checks failed | "
        f"{nvr['ip']}:{nvr['port']}"
    )

    return {
        "id": nvr["id"],
        "name": nvr["name"],
        "ip": nvr["ip"],
        "port": nvr["port"],
        "status": "OFFLINE",
        "cpu_percent": None,
        "memory_percent": None,
        "temperature_c": None,
        "uptime_seconds": None,
        "cpus": [],
        "memories": [],
        "temperatures": [],
        "latency_ms": latency_ms,
        "temperature_source": None,
        "error": (
            "NVR unreachable or all Hikvision "
            "ISAPI health endpoints failed."
        ),
    }


# ============================================================
# REFRESH HEALTH
# ============================================================

def refresh_health():

    # IMPORTANT:
    # This uses the complete NVRS list from config.py.
    # If NVRS contains 12 NVRs, all 12 are scanned.
    with ThreadPoolExecutor(
        max_workers=max(
            1,
            len(NVRS),
        )
    ) as executor:

        results = list(
            executor.map(
                _collect,
                NVRS,
            )
        )

    # ========================================================
    # STORAGE
    # ========================================================

    try:

        from .storage_monitor import get_storage

        storage = {
            x["name"]: x
            for x in get_storage(
                force=False
            )
        }

    except Exception as exc:

        print(
            f"[NVR HEALTH STORAGE] "
            f"Unable to load storage: {exc}"
        )

        storage = {}

    # ========================================================
    # PROCESS EACH NVR
    # ========================================================

    for item in results:

        name = item["name"]

        nvr_cfg = next(
            (
                n
                for n in NVRS
                if n["name"] == name
            ),
            item,
        )

        disk = storage.get(
            name
        )

        if disk:

            item[
                "storage_status"
            ] = disk.get(
                "status"
            )

            item[
                "storage_used_percent"
            ] = disk.get(
                "used_percent"
            )

            item[
                "hdd_count"
            ] = len(
                disk.get(
                    "hdds"
                )
                or []
            )

            item[
                "hdd_issues"
            ] = [
                {
                    "id": d.get(
                        "id"
                    ),
                    "status": d.get(
                        "status"
                    ),
                }
                for d in (
                    disk.get(
                        "hdds"
                    )
                    or []
                )
                if str(
                    d.get(
                        "status",
                        "",
                    )
                ).strip().lower()
                not in {
                    "ok",
                    "normal",
                    "healthy",
                    "online",
                    "active",
                    "ready",
                }
            ]

            item[
                "storage_error"
            ] = disk.get(
                "error"
            )

        # ====================================================
        # OFFLINE ALERT
        # ====================================================

        if item["status"] == "OFFLINE":

            _alert_once(
                f"{name}:offline",
                "CRITICAL",
                f"{name} Offline",
                (
                    f"{name} at "
                    f"{item['ip']}:{item['port']} "
                    "is unreachable. "
                    "All HTTP/ISAPI health checks failed."
                ),
                email={
                    "nvr": name,
                    "ip": item["ip"],
                    "severity": "CRITICAL",
                    "title": f"{name} Offline",
                    "description": (
                        f"{name} at "
                        f"{item['ip']}:{item['port']} "
                        "is unreachable. "
                        "All Hikvision ISAPI health "
                        "checks failed."
                    ),
                    "metric": (
                        "Connectivity: OFFLINE"
                    ),
                    "threshold": (
                        "At least one Hikvision "
                        "ISAPI endpoint should respond"
                    ),
                },
            )

            continue

        # ====================================================
        # RECOVERY
        # ====================================================

        _alert_once(
            f"{name}:offline",
            "CRITICAL",
            f"{name} Offline",
            f"{name} is reachable again.",
            active=False,
            email={
                "nvr": name,
                "ip": item["ip"],
                "severity": "INFO",
                "title": f"{name} Offline",
                "description": (
                    f"{name} is reachable again."
                ),
                "metric": (
                    "Connectivity: ONLINE"
                ),
                "threshold": (
                    "At least one Hikvision "
                    "ISAPI endpoint should respond"
                ),
            },
        )

        # ====================================================
        # CPU
        # ====================================================

        cpu = item.get(
            "cpu_percent"
        )

        _alert_once(
            f"{name}:cpu_critical",
            "CRITICAL",
            f"{name} High CPU",
            (
                f"CPU usage is {cpu}% "
                f"(critical threshold "
                f"{CPU_CRITICAL}%)."
            ),
            active=(
                cpu is not None
                and cpu >= CPU_CRITICAL
            ),
            confirm_readings=3,
            email={
                "nvr": name,
                "ip": item["ip"],
                "severity": "CRITICAL",
                "title": f"{name} High CPU",
                "description": (
                    f"CPU usage is {cpu}%. "
                    "This can affect recording, "
                    "live view and NVR response."
                ),
                "metric": (
                    f"CPU: {cpu}%"
                ),
                "threshold": (
                    f"Critical >= "
                    f"{CPU_CRITICAL}%"
                ),
            },
        )

        _alert_once(
            f"{name}:cpu_warning",
            "WARNING",
            f"{name} CPU Warning",
            (
                f"CPU usage is {cpu}% "
                f"(warning threshold "
                f"{CPU_WARN}%)."
            ),
            active=(
                cpu is not None
                and CPU_WARN <= cpu < CPU_CRITICAL
            ),
            confirm_readings=3,
            email={
                "nvr": name,
                "ip": item["ip"],
                "severity": "WARNING",
                "title": f"{name} CPU Warning",
                "description": (
                    f"CPU usage is {cpu}%. "
                    "Monitor the NVR because "
                    "sustained high CPU may affect "
                    "recording and live view."
                ),
                "metric": (
                    f"CPU: {cpu}%"
                ),
                "threshold": (
                    f"Warning >= "
                    f"{CPU_WARN}%"
                ),
            },
        )

        # ====================================================
        # MEMORY
        # ====================================================

        mem = item.get(
            "memory_percent"
        )

        _alert_once(
            f"{name}:memory_critical",
            "CRITICAL",
            f"{name} High Memory",
            (
                f"Memory usage is {mem}% "
                f"(critical threshold "
                f"{MEM_CRITICAL}%)."
            ),
            active=(
                mem is not None
                and mem >= MEM_CRITICAL
            ),
            confirm_readings=3,
            email={
                "nvr": name,
                "ip": item["ip"],
                "severity": "CRITICAL",
                "title": f"{name} High Memory",
                "description": (
                    f"Memory usage is {mem}%. "
                    "High memory can cause service "
                    "instability or delayed "
                    "recording/indexing."
                ),
                "metric": (
                    f"Memory: {mem}%"
                ),
                "threshold": (
                    f"Critical >= "
                    f"{MEM_CRITICAL}%"
                ),
            },
        )

        _alert_once(
            f"{name}:memory_warning",
            "WARNING",
            f"{name} Memory Warning",
            (
                f"Memory usage is {mem}% "
                f"(warning threshold "
                f"{MEM_WARN}%)."
            ),
            active=(
                mem is not None
                and MEM_WARN <= mem < MEM_CRITICAL
            ),
            confirm_readings=3,
            email={
                "nvr": name,
                "ip": item["ip"],
                "severity": "WARNING",
                "title": f"{name} Memory Warning",
                "description": (
                    f"Memory usage is {mem}%. "
                    "Monitor for continued growth."
                ),
                "metric": (
                    f"Memory: {mem}%"
                ),
                "threshold": (
                    f"Warning >= "
                    f"{MEM_WARN}%"
                ),
            },
        )

        # ====================================================
        # TEMPERATURE
        # ====================================================

        temp = item.get(
            "temperature_c"
        )

        _alert_once(
            f"{name}:temp_critical",
            "CRITICAL",
            f"{name} High Temperature",
            (
                f"Device temperature is "
                f"{temp}°C "
                f"(critical threshold "
                f"{TEMP_CRITICAL}°C)."
            ),
            active=(
                temp is not None
                and temp >= TEMP_CRITICAL
            ),
            confirm_readings=2,
            email={
                "nvr": name,
                "ip": item["ip"],
                "severity": "CRITICAL",
                "title": (
                    f"{name} High Temperature"
                ),
                "description": (
                    f"Device temperature is "
                    f"{temp}°C. Check ventilation, "
                    "fan status and ambient "
                    "temperature."
                ),
                "metric": (
                    f"Temperature: {temp}°C"
                ),
                "threshold": (
                    f"Critical >= "
                    f"{TEMP_CRITICAL}°C"
                ),
            },
        )

        _alert_once(
            f"{name}:temp_warning",
            "WARNING",
            f"{name} Temperature Warning",
            (
                f"Device temperature is "
                f"{temp}°C "
                f"(warning threshold "
                f"{TEMP_WARN}°C)."
            ),
            active=(
                temp is not None
                and TEMP_WARN <= temp < TEMP_CRITICAL
            ),
            confirm_readings=2,
            email={
                "nvr": name,
                "ip": item["ip"],
                "severity": "WARNING",
                "title": (
                    f"{name} Temperature Warning"
                ),
                "description": (
                    f"Device temperature is "
                    f"{temp}°C. Check ventilation "
                    "if it remains high."
                ),
                "metric": (
                    f"Temperature: {temp}°C"
                ),
                "threshold": (
                    f"Warning >= "
                    f"{TEMP_WARN}°C"
                ),
            },
        )

        # ====================================================
        # HDD / STORAGE
        # ====================================================

        disk = storage.get(
            name
        )

        if (
            disk
            and disk.get("status")
            == "ONLINE"
        ):

            hdds = (
                disk.get("hdds")
                or []
            )

            healthy_states = {
                "ok",
                "normal",
                "healthy",
                "online",
                "active",
                "ready",
            }

            if hdds:

                bad = [
                    d
                    for d in hdds
                    if str(
                        d.get(
                            "status",
                            "",
                        )
                    ).strip().lower()
                    not in healthy_states
                ]

                if bad:

                    statuses = ", ".join(
                        (
                            f"HDD "
                            f"{d.get('id', '?')}: "
                            f"{d.get('status', 'unknown')}"
                        )
                        for d in bad
                    )

                    _alert_once(
                        f"{name}:hdd",
                        "CRITICAL",
                        f"{name} HDD Issue",
                        (
                            f"{len(bad)} HDD(s) "
                            "report a non-healthy "
                            f"status. Detected: "
                            f"{statuses}."
                        ),
                        active=True,
                        confirm_readings=2,
                        email={
                            "nvr": name,
                            "ip": item["ip"],
                            "severity": "CRITICAL",
                            "title": (
                                f"{name} HDD Issue"
                            ),
                            "description": (
                                f"{len(bad)} HDD(s) "
                                "report a non-healthy "
                                f"status. Detected: "
                                f"{statuses}. "
                                "Recording may be affected."
                            ),
                            "metric": (
                                f"Unhealthy HDDs: "
                                f"{len(bad)}"
                            ),
                            "threshold": (
                                "HDD status should be "
                                "healthy/normal"
                            ),
                        },
                    )

                else:

                    _alert_once(
                        f"{name}:hdd",
                        "CRITICAL",
                        f"{name} HDD Issue",
                        (
                            "HDD status has "
                            f"returned to healthy/normal "
                            f"on {name}."
                        ),
                        active=False,
                        email={
                            "nvr": name,
                            "ip": item["ip"],
                            "severity": "INFO",
                            "title": (
                                f"{name} HDD Issue"
                            ),
                            "description": (
                                "All detected HDDs are "
                                "reporting a healthy/"
                                "normal state."
                            ),
                            "metric": (
                                "Unhealthy HDDs: 0"
                            ),
                            "threshold": (
                                "HDD status should be "
                                "healthy/normal"
                            ),
                        },
                    )

                _alert_once(
                    f"{name}:hdd_telemetry",
                    "WARNING",
                    f"{name} HDD Detection Unavailable",
                    "HDD telemetry is available again.",
                    active=False,
                    email={
                        "nvr": name,
                        "ip": item["ip"],
                        "severity": "INFO",
                        "title": (
                            f"{name} HDD Detection Recovered"
                        ),
                        "description": (
                            "HDD telemetry is "
                            "available again."
                        ),
                        "metric": (
                            f"HDD entries: "
                            f"{len(hdds)}"
                        ),
                        "threshold": (
                            "At least one HDD "
                            "should be detectable"
                        ),
                    },
                )

            else:

                reason = (
                    disk.get("error")
                    or "NVR returned no HDD entries."
                )

                _alert_once(
                    f"{name}:hdd_telemetry",
                    "WARNING",
                    f"{name} HDD Detection Unavailable",
                    reason,
                    active=True,
                    confirm_readings=2,
                    email={
                        "nvr": name,
                        "ip": item["ip"],
                        "severity": "WARNING",
                        "title": (
                            f"{name} HDD Detection Unavailable"
                        ),
                        "description": (
                            f"HDD telemetry could "
                            f"not be verified for "
                            f"{name}. Reason: "
                            f"{reason}. "
                            "The NVR itself is reachable."
                        ),
                        "metric": (
                            "HDD entries: 0"
                        ),
                        "threshold": (
                            "At least one HDD "
                            "should be detectable"
                        ),
                    },
                )

        elif disk:

            reason = (
                disk.get("error")
                or "Storage/HDD resource is not reporting ONLINE."
            )

            _alert_once(
                f"{name}:storage_unavailable",
                "CRITICAL",
                f"{name} Storage Unavailable",
                reason,
                active=True,
                confirm_readings=2,
                email={
                    "nvr": name,
                    "ip": item["ip"],
                    "severity": "CRITICAL",
                    "title": (
                        f"{name} Storage Unavailable"
                    ),
                    "description": (
                        reason
                        + " Recording may be affected. "
                        "Check HDD status and storage service."
                    ),
                    "metric": (
                        "Storage status: OFFLINE"
                    ),
                    "threshold": (
                        "Storage should be ONLINE"
                    ),
                },
            )

    # ========================================================
    # SAVE HISTORY
    # ========================================================

    try:

        existing = []

        if _HISTORY_FILE.exists():

            with _HISTORY_FILE.open(
                "r",
                encoding="utf-8",
            ) as f:

                existing = (
                    json.load(f)
                    or []
                )

        timestamp = time.time()

        for item in results:

            existing.append(
                {
                    "timestamp": timestamp,
                    "time": time.strftime(
                        "%Y-%m-%dT%H:%M:%S"
                    ),
                    "id": item.get(
                        "id"
                    ),
                    "name": item.get(
                        "name"
                    ),
                    "ip": item.get(
                        "ip"
                    ),
                    "status": item.get(
                        "status"
                    ),
                    "cpu_percent": item.get(
                        "cpu_percent"
                    ),
                    "memory_percent": item.get(
                        "memory_percent"
                    ),
                    "temperature_c": item.get(
                        "temperature_c"
                    ),
                    "latency_ms": item.get(
                        "latency_ms"
                    ),
                    "storage_used_percent": item.get(
                        "storage_used_percent"
                    ),
                    "uptime_seconds": item.get(
                        "uptime_seconds"
                    ),
                }
            )

        existing = existing[
            -_HISTORY_LIMIT:
        ]

        with _HISTORY_FILE.open(
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                existing,
                f,
                ensure_ascii=False,
            )

    except Exception as exc:

        print(
            f"[NVR HEALTH HISTORY] "
            f"write error: {exc}"
        )

    # ========================================================
    # UPDATE CACHE
    # ========================================================

    with _lock:

        _cache.clear()

        _cache.update(
            {
                x["name"]: x
                for x in results
            }
        )

        online = sum(
            1
            for x in results
            if x.get("status")
            == "ONLINE"
        )

        offline = sum(
            1
            for x in results
            if x.get("status")
            == "OFFLINE"
        )

        print(
            f"[NVR HEALTH] "
            f"SCAN COMPLETE | "
            f"TOTAL={len(results)} | "
            f"ONLINE={online} | "
            f"OFFLINE={offline}"
        )

        return list(
            _cache.values()
        )


# ============================================================
# HISTORY
# ============================================================

def get_health_history(
    nvr_name=None,
    minutes=60,
    limit=720,
):
    """Return persisted NVR telemetry samples."""

    try:

        if not _HISTORY_FILE.exists():
            return []

        with _HISTORY_FILE.open(
            "r",
            encoding="utf-8",
        ) as f:

            rows = (
                json.load(f)
                or []
            )

        cutoff = (
            time.time()
            - max(
                1,
                int(minutes),
            )
            * 60
        )

        rows = [
            r
            for r in rows
            if float(
                r.get(
                    "timestamp",
                    0,
                )
                or 0
            )
            >= cutoff
        ]

        if nvr_name:

            rows = [
                r
                for r in rows
                if str(
                    r.get(
                        "name",
                        "",
                    )
                ).lower()
                == str(
                    nvr_name
                ).lower()
            ]

        return rows[
            -max(
                1,
                int(limit),
            ):
        ]

    except Exception as exc:

        print(
            f"[NVR HEALTH HISTORY] "
            f"read error: {exc}"
        )

        return []


# ============================================================
# HEALTH INSIGHTS
# ============================================================

def get_health_insights(health):

    insights = []

    for item in health or []:

        name = item.get(
            "name",
            "NVR",
        )

        cpu = item.get(
            "cpu_percent"
        )

        mem = item.get(
            "memory_percent"
        )

        temp = item.get(
            "temperature_c"
        )

        latency = item.get(
            "latency_ms"
        )

        if item.get(
            "status"
        ) == "OFFLINE":

            insights.append(
                {
                    "severity": "CRITICAL",
                    "nvr": name,
                    "title": (
                        f"{name} is offline"
                    ),
                    "detail": (
                        "All available Hikvision "
                        "health/API endpoints "
                        "are unreachable."
                    ),
                }
            )

            continue

        if (
            temp is not None
            and temp >= TEMP_CRITICAL
        ):

            insights.append(
                {
                    "severity": "CRITICAL",
                    "nvr": name,
                    "title": (
                        f"{name} temperature critical"
                    ),
                    "detail": (
                        f"Temperature is {temp}°C; "
                        "investigate cooling immediately."
                    ),
                }
            )

        elif (
            temp is not None
            and temp >= TEMP_WARN
        ):

            insights.append(
                {
                    "severity": "WARNING",
                    "nvr": name,
                    "title": (
                        f"{name} temperature elevated"
                    ),
                    "detail": (
                        f"Temperature is {temp}°C; "
                        "monitor airflow and load."
                    ),
                }
            )

        elif temp is None:

            insights.append(
                {
                    "severity": "INFO",
                    "nvr": name,
                    "title": (
                        f"{name} temperature "
                        "sensor unavailable"
                    ),
                    "detail": (
                        "This NVR did not expose "
                        "a readable thermal sensor "
                        "in the available ISAPI endpoints."
                    ),
                }
            )

        if (
            mem is not None
            and mem >= MEM_CRITICAL
        ):

            insights.append(
                {
                    "severity": "CRITICAL",
                    "nvr": name,
                    "title": (
                        f"{name} memory critical"
                    ),
                    "detail": (
                        f"Memory usage is {mem}%."
                    ),
                }
            )

        elif (
            mem is not None
            and mem >= MEM_WARN
        ):

            insights.append(
                {
                    "severity": "WARNING",
                    "nvr": name,
                    "title": (
                        f"{name} memory elevated"
                    ),
                    "detail": (
                        f"Memory usage is {mem}%."
                    ),
                }
            )

        if (
            cpu is not None
            and cpu >= CPU_CRITICAL
        ):

            insights.append(
                {
                    "severity": "CRITICAL",
                    "nvr": name,
                    "title": (
                        f"{name} CPU critical"
                    ),
                    "detail": (
                        f"CPU usage is {cpu}%."
                    ),
                }
            )

        elif (
            cpu is not None
            and cpu >= CPU_WARN
        ):

            insights.append(
                {
                    "severity": "WARNING",
                    "nvr": name,
                    "title": (
                        f"{name} CPU elevated"
                    ),
                    "detail": (
                        f"CPU usage is {cpu}%."
                    ),
                }
            )

        if (
            latency is not None
            and latency >= 500
        ):

            insights.append(
                {
                    "severity": "WARNING",
                    "nvr": name,
                    "title": (
                        f"{name} network latency high"
                    ),
                    "detail": (
                        f"Health API latency is "
                        f"{latency} ms."
                    ),
                }
            )

    return insights


# ============================================================
# PUBLIC HEALTH API
# ============================================================

def get_health(force=False):

    if force or not _cache:
        return refresh_health()

    with _lock:
        return list(
            _cache.values()
        )


# ============================================================
# BACKGROUND MONITOR
# ============================================================

def _loop():

    while True:

        try:

            refresh_health()

        except Exception as exc:

            print(
                f"NVR health monitor error: {exc}"
            )

        time.sleep(
            POLL_SECONDS
        )


# ============================================================
# START MONITOR
# ============================================================

def start_health_monitor():

    global _started
    global _thread

    if _started:
        return

    _started = True

    _thread = threading.Thread(
        target=_loop,
        name="nvr-health-monitor",
        daemon=True,
    )

    _thread.start()

    print(
        f"[NVR HEALTH] Monitor started | "
        f"Configured NVRs: {len(NVRS)}"
    )
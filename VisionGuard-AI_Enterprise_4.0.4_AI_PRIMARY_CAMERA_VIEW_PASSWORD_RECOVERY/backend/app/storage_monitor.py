"""Live Hikvision NVR HDD/storage telemetry.

Hikvision ISAPI reports HDD ``capacity`` and ``freeSpace`` in MB for the
ContentMgmt/Storage HDD resource.  This module keeps the raw MB values and
normalizes them to bytes internally so the UI can display GB/TB correctly.
"""

import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests
from requests.auth import HTTPDigestAuth

from .config import NVRS


STORAGE_TIMEOUT = 6
STORAGE_REFRESH_SECONDS = 15
MAX_WORKERS = max(1, len(NVRS))

_lock = threading.RLock()
_cache = {}
_last_update = None


def _local_name(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _find_text(node, names, default=""):
    wanted = {str(x).lower() for x in names}
    for child in node.iter():
        if _local_name(child.tag) in wanted and child.text:
            return child.text.strip()
    return default


def _number(value):
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def _value_to_mb(value):
    """Convert an ISAPI storage value to MB.

    Official Hikvision ISAPI documentation defines HDD capacity/freeSpace as
    MB.  Some firmware builds append a unit, so explicit units are honoured;
    unit-less values are treated as MB.
    """
    if value is None:
        return None

    text = str(value).strip().upper().replace(",", "")
    units = (("TB", 1024 * 1024), ("GB", 1024), ("MB", 1), ("KB", 1 / 1024))
    for suffix, multiplier in units:
        if text.endswith(suffix):
            number = _number(text[:-len(suffix)])
            return number * multiplier if number is not None else None

    number = _number(text)
    return number


def _mb_to_bytes(mb):
    return max(0.0, float(mb)) * 1024 * 1024


def _parse_storage(xml_text):
    if not xml_text:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    disks = []
    for node in root.iter():
        if _local_name(node.tag) not in {"hdd", "storage"}:
            continue

        capacity_raw = _find_text(node, ("capacity", "totalCapacity"))
        free_raw = _find_text(node, ("freeSpace", "freeCapacity", "availableSpace"))
        status = _find_text(node, ("status", "healthStatus", "state"), "unknown")
        disk_id = _find_text(node, ("id", "hddID", "harddiskID", "storageID"), str(len(disks) + 1))

        capacity_mb = _value_to_mb(capacity_raw)
        free_mb = _value_to_mb(free_raw)
        normalized_status = str(status).strip() or "unknown"
        if capacity_mb is None or capacity_mb <= 0:
            disks.append({"id":str(disk_id),"status":normalized_status,"capacity_mb":None,"free_mb":None,"used_mb":None,"free_known":False,"capacity_bytes":0,"telemetry_partial":True})
            continue
        free_known = free_mb is not None
        if free_mb is not None:
            free_mb = min(max(free_mb, 0), capacity_mb)
            used_mb = capacity_mb - free_mb
        else:
            used_mb = None
        disks.append({"id":str(disk_id),"status":normalized_status,"capacity_mb":round(capacity_mb,2),"free_mb":round(free_mb,2) if free_mb is not None else None,"used_mb":round(used_mb,2) if used_mb is not None else None,"free_known":free_known,"capacity_bytes":_mb_to_bytes(capacity_mb),"telemetry_partial":False})

    # Avoid duplicates when a firmware response nests an <hdd> inside a
    # wrapper also called <storage>.
    unique = []
    seen = set()
    for disk in disks:
        key = (disk["id"], disk["capacity_mb"])
        if key not in seen:
            seen.add(key)
            unique.append(disk)
    return unique


def _request(nvr, endpoint):
    url = f"http://{nvr['ip']}:{nvr['port']}{endpoint}"
    try:
        response = requests.get(
            url,
            auth=HTTPDigestAuth(nvr["username"], nvr["password"]),
            headers={"Accept": "application/xml"},
            timeout=STORAGE_TIMEOUT,
        )
        if response.status_code == 200 and response.text:
            return response.text
    except requests.RequestException:
        pass
    return None


def _fetch_nvr(nvr):
    # Newer and older Hikvision firmwares expose the same HDD information at
    # one of these resources. Try the collection first, then the HDD resource.
    disks = []
    for endpoint in (
        "/ISAPI/ContentMgmt/Storage",
        "/ISAPI/ContentMgmt/Storage/hdd",
    ):
        xml = _request(nvr, endpoint)
        parsed = _parse_storage(xml)
        if parsed:
            disks = parsed
            break

    if not disks:
        # A storage resource can be disabled/unsupported on a particular
        # firmware even though the NVR itself is reachable. Check the device
        # endpoint before calling the NVR offline.
        device_xml = _request(nvr, "/ISAPI/System/deviceInfo")
        device_online = device_xml is not None
        return {
            "name": nvr["name"],
            "ip": nvr["ip"],
            "port": nvr["port"],
            "status": "ONLINE" if device_online else "OFFLINE",
            "total_bytes": 0,
            "used_bytes": None if device_online else 0,
            "free_bytes": None if device_online else 0,
            "used_percent": None if device_online else 0,
            "hdds": [],
            "error": "Storage telemetry unavailable" if device_online else "NVR unreachable",
        }

    capacity_disks = [d for d in disks if d.get("capacity_bytes",0) > 0]
    total = sum(d["capacity_bytes"] for d in capacity_disks)
    free_known = bool(capacity_disks) and all(d["free_known"] for d in capacity_disks)
    free = sum(_mb_to_bytes(d["free_mb"]) for d in capacity_disks if d["free_mb"] is not None)
    used = total - free if free_known else None
    percent = (used / total * 100) if used is not None and total else None

    return {
        "name": nvr["name"],
        "ip": nvr["ip"],
        "port": nvr["port"],
        "status": "ONLINE",
        "total_bytes": round(total),
        "used_bytes": round(used) if used is not None else None,
        "free_bytes": round(free) if free_known else None,
        "used_percent": round(percent, 1) if percent is not None else None,
        "hdds": disks,
        "error": None,
    }


def refresh_storage(force=True):
    global _last_update
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        results = list(executor.map(_fetch_nvr, NVRS))

    with _lock:
        _cache.clear()
        _cache.update({item["name"]: item for item in results})
        _last_update = time.time()
        return list(_cache.values())


def get_storage(force=False):
    with _lock:
        fresh = _last_update is not None and (time.time() - _last_update) < STORAGE_REFRESH_SECONDS
        if fresh and not force:
            return list(_cache.values())

    return refresh_storage(force=True)


def storage_snapshot(force=False):
    data = get_storage(force=force)
    return {
        "nvr_count": len(NVRS),
        "online_nvr": sum(1 for x in data if x["status"] == "ONLINE"),
        "data": data,
        "last_update": _last_update,
    }

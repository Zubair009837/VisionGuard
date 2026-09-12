"""VisionGuard AI enterprise extensions.

Adds NVR user discovery, camera movement tracking, camera bulk/single
configuration helpers and persistent movement history without replacing the
existing monitoring engines.
"""
from __future__ import annotations

import json
import threading
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPDigestAuth

from .config import NVRS
from .alert_manager import add_alert
from .email_service import send_camera_migration_email

BASE_DIR = Path(__file__).resolve().parent
MOVEMENT_FILE = BASE_DIR / "camera_movement_history.json"
MOVEMENT_STATE_FILE = BASE_DIR / "camera_assignment_state.json"
MOVEMENT_PENDING_FILE = BASE_DIR / "camera_assignment_pending.json"
# Durable assignment timeline. Unlike movement events, this file records the
# full validity interval of every confirmed NVR/channel assignment.
MOVEMENT_TIMELINE_FILE = BASE_DIR / "camera_assignment_timeline.json"
MOVEMENT_CONFIRMATION_SECONDS = 20  # current test window: 20 seconds
LOCK = threading.RLock()


def _load_json(path: Path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as exc:
        print(f"[ENTERPRISE] JSON read error {path.name}: {exc}")
    return default


def _save_json(path: Path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, default=str)
    tmp.replace(path)


def _now():
    return datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")


def _nvr_request(nvr: dict, method: str, endpoint: str, body=None):
    url = f"http://{nvr['ip']}:{nvr['port']}{endpoint}"
    return requests.request(
        method,
        url,
        auth=HTTPDigestAuth(nvr["username"], nvr["password"]),
        data=body.encode("utf-8") if isinstance(body, str) else body,
        headers={"Accept": "application/xml", "Content-Type": "application/xml"},
        timeout=12,
    )


def nvr_users() -> List[dict]:
    """Discover users from every configured NVR."""
    result = []
    for nvr in NVRS:
        entry = {
            "nvr": nvr["name"],
            "nvr_id": nvr["id"],
            "ip": nvr["ip"],
            "status": "ONLINE",
            "user_count": 0,
            "users": [],
        }
        try:
            r = _nvr_request(nvr, "GET", "/ISAPI/Security/users")
            if not r.ok:
                entry["status"] = f"HTTP {r.status_code}"
                result.append(entry)
                continue
            root = ET.fromstring(r.text)
            users = []
            nodes = root.findall(".//{*}User")
            if not nodes and root.tag.endswith("User"):
                nodes = [root]
            for node in nodes:
                def txt(*names):
                    for name in names:
                        child = node.find(f"{{*}}{name}")
                        if child is not None and child.text:
                            return child.text.strip()
                    return ""
                users.append({
                    "id": txt("id"),
                    "userName": txt("userName", "username"),
                    "role": txt("userLevel", "role"),
                    "enabled": txt("enabled", "enable") or "true",
                    "ipAddress": txt("ipAddress"),
                })
            entry["users"] = users
            entry["user_count"] = len(users)
        except Exception as exc:
            entry["status"] = "ERROR"
            entry["error"] = str(exc)
        result.append(entry)
    return result


def _camera_key(camera: dict) -> str:
    # Camera name is the most useful stable identity in a multi-NVR migration
    # scenario; IP is retained as a fallback for unnamed cameras.
    name = str(camera.get("name", "")).strip().lower()
    ip = str(camera.get("ip", "")).strip()
    if name and not name.startswith("camera "):
        return f"name:{name}"
    return f"ip:{ip}" if ip else f"channel:{camera.get('id')}"



def _timeline_identity(camera: dict) -> str:
    """Stable identity used by the historical assignment timeline."""
    return _camera_key(camera)


def _timeline_update(camera: dict, now_dt: datetime, previous: Optional[dict]):
    """Create/close confirmed assignment intervals.

    This is deliberately independent from the alert email. A camera can move
    because of an IP conflict and the historical finder must still know which
    channel was valid at a specific time.
    """
    timeline = _load_json(MOVEMENT_TIMELINE_FILE, {})
    key = _timeline_identity(camera)
    rows = timeline.get(key, [])
    nvr = camera.get("nvr", "Unknown NVR")
    channel = camera.get("id")
    name = camera.get("name", "Unknown Camera")
    ip = camera.get("ip", "")
    stamp = now_dt.isoformat(timespec="seconds")

    def same(row):
        return (
            str(row.get("nvr")) == str(nvr)
            and int(row.get("channel") or 0) == int(channel or 0)
        )

    if not rows:
        rows.append({
            "camera": name,
            "identity": key,
            "nvr": nvr,
            "channel": channel,
            "ip": ip,
            "valid_from": stamp,
            "valid_to": None,
            "moved_from": None,
            "moved_to": None,
            "source": "live-discovery",
        })
    else:
        active = rows[-1]
        if active.get("valid_to") is None and same(active):
            active["camera"] = name
            active["ip"] = ip
        elif active.get("valid_to") is None:
            active["valid_to"] = stamp
            old_nvr = active.get("nvr")
            old_channel = active.get("channel")
            rows.append({
                "camera": name,
                "identity": key,
                "nvr": nvr,
                "channel": channel,
                "ip": ip,
                "valid_from": stamp,
                "valid_to": None,
                "moved_from": f"{old_nvr} CH-{old_channel}",
                "moved_to": f"{nvr} CH-{channel}",
                "source": "confirmed-move",
            })
        else:
            # If a timeline was closed previously, avoid duplicate intervals.
            if not same(active):
                rows.append({
                    "camera": name,
                    "identity": key,
                    "nvr": nvr,
                    "channel": channel,
                    "ip": ip,
                    "valid_from": stamp,
                    "valid_to": None,
                    "moved_from": f"{active.get('nvr')} CH-{active.get('channel')}",
                    "moved_to": f"{nvr} CH-{channel}",
                    "source": "live-discovery",
                })

    timeline[key] = rows[-500:]
    _save_json(MOVEMENT_TIMELINE_FILE, timeline)


def get_camera_assignment_timeline(camera_name: str, start=None, end=None, limit=500):
    """Return confirmed NVR/channel intervals for a camera name."""
    query = _normalise_name_for_timeline(camera_name)
    start_dt = _parse_timeline_time(start) if start else None
    end_dt = _parse_timeline_time(end) if end else None
    timeline = _load_json(MOVEMENT_TIMELINE_FILE, {})
    out = []
    for rows in timeline.values() if isinstance(timeline, dict) else []:
        for row in rows if isinstance(rows, list) else []:
            name = str(row.get("camera", ""))
            norm = _normalise_name_for_timeline(name)
            if not norm or not (norm == query or query in norm or norm in query):
                continue
            vf = _parse_timeline_time(row.get("valid_from"))
            vt = _parse_timeline_time(row.get("valid_to"))
            if start_dt and vt and vt < start_dt:
                continue
            if end_dt and vf and vf > end_dt:
                continue
            out.append(dict(row))
    out.sort(key=lambda x: x.get("valid_from") or "")
    return out[-limit:]


def _normalise_name_for_timeline(value):
    return re.sub(r"[\W_]+", "", str(value or "").strip().casefold(), flags=re.UNICODE)


def _parse_timeline_time(value):
    if value is None:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def track_camera_assignment(camera: dict):
    """Confirm an NVR/channel move only after it remains stable for the configured confirmation window.

    A transient discovery on another recorder is kept as a pending candidate.
    The move is written to history, surfaced in Analytics and emailed only after
    the same camera is continuously discovered under the new NVR for 600 seconds.
    If it returns to the previous NVR before confirmation, the candidate is cleared.
    """
    key = _camera_key(camera)
    now_dt = datetime.now()
    current = {
        "identity": key,
        "camera": camera.get("name", "Unknown Camera"),
        "ip": camera.get("ip", ""),
        "nvr": camera.get("nvr", "Unknown NVR"),
        "channel": camera.get("id"),
        "last_seen": _now(),
    }

    with LOCK:
        state = _load_json(MOVEMENT_STATE_FILE, {})
        pending = _load_json(MOVEMENT_PENDING_FILE, {})
        previous = state.get(key)

        # First sighting establishes the confirmed baseline.
        if not previous:
            state[key] = current
            pending.pop(key, None)
            _save_json(MOVEMENT_STATE_FILE, state)
            _save_json(MOVEMENT_PENDING_FILE, pending)
            _timeline_update(camera, now_dt, None)
            return None

        # Same NVR + same channel means stable. A channel change on the same NVR is also a movement event.
        same_assignment = previous.get("nvr") == current["nvr"] and previous.get("channel") == current.get("channel")
        if same_assignment:
            if key in pending:
                pending.pop(key, None)
                _save_json(MOVEMENT_PENDING_FILE, pending)
            state[key] = current
            _save_json(MOVEMENT_STATE_FILE, state)
            return None

        # Camera is being seen under a different NVR or channel. Start/continue
        # the configured confirmation timer without changing the confirmed baseline yet.
        candidate = pending.get(key)
        if not candidate or candidate.get("nvr") != current["nvr"] or candidate.get("channel") != current.get("channel"):
            pending[key] = {
                "started_at": now_dt.isoformat(),
                "candidate": current,
                "confirmation_seconds": MOVEMENT_CONFIRMATION_SECONDS,
            }
            _save_json(MOVEMENT_PENDING_FILE, pending)
            return None

        try:
            elapsed = (now_dt - datetime.fromisoformat(candidate["started_at"])).total_seconds()
        except Exception:
            elapsed = 0

        if elapsed < MOVEMENT_CONFIRMATION_SECONDS:
            return None

        # Assignment stayed changed for the configured confirmation window: confirm the event.
        state[key] = current
        pending.pop(key, None)
        _save_json(MOVEMENT_STATE_FILE, state)
        _save_json(MOVEMENT_PENDING_FILE, pending)
        _timeline_update(camera, now_dt, previous)

        event = {
            "time": current["last_seen"],
            "type": "CAMERA NVR MOVEMENT",
            "severity": "CRITICAL",
            "camera": current["camera"],
            "ip": current["ip"],
            "previous_nvr": previous.get("nvr"),
            "previous_channel": previous.get("channel"),
            "current_nvr": current["nvr"],
            "current_channel": current.get("channel"),
            "confirmation_seconds": MOVEMENT_CONFIRMATION_SECONDS,
            "details": (
                f"Camera remained on {current['nvr']} CH-{current.get('channel')} for "
                f"{MOVEMENT_CONFIRMATION_SECONDS} seconds. Previous assignment: {previous.get('nvr')} CH-{previous.get('channel')}."
            ),
        }
        history = _load_json(MOVEMENT_FILE, [])
        history.append(event)
        _save_json(MOVEMENT_FILE, history[-2000:])

    add_alert(
        "CAMERA NVR MOVEMENT",
        "CRITICAL",
        f"Camera moved NVR - {current['camera']}",
        event["details"],
    )
    print("\n" + "=" * 72)
    print(f"🚨 CAMERA NVR/CHANNEL MOVEMENT CONFIRMED AFTER {MOVEMENT_CONFIRMATION_SECONDS} SECONDS")
    print("Camera   :", current["camera"])
    print("Previous :", previous.get("nvr"), "CH", previous.get("channel"))
    print("Current  :", current["nvr"], "CH", current.get("channel"))
    print("IP       :", current["ip"])
    print("Time     :", current["last_seen"])
    print("=" * 72)
    try:
        send_camera_migration_email(
            camera=current["camera"],
            ip=current["ip"],
            old_nvr=previous.get("nvr", "-"),
            old_channel=previous.get("channel", "-"),
            new_nvr=current["nvr"],
            new_channel=current.get("channel", "-"),
            event_time=current["last_seen"],
        )
    except Exception as exc:
        print("[ENTERPRISE] Migration email error:", exc)
    return event


def get_camera_movement_history(limit: int = 500):
    history = _load_json(MOVEMENT_FILE, [])
    return list(reversed(history[-limit:]))


def camera_movement_summary():
    history = _load_json(MOVEMENT_FILE, [])
    pending = _load_json(MOVEMENT_PENDING_FILE, {})
    by_camera = {}
    for item in history:
        by_camera[item.get("camera", "Unknown")] = by_camera.get(item.get("camera", "Unknown"), 0) + 1
    pending_items = []
    now_dt = datetime.now()
    for key, item in pending.items():
        try:
            elapsed = max(0, int((now_dt - datetime.fromisoformat(item.get("started_at"))).total_seconds()))
        except Exception:
            elapsed = 0
        pending_items.append({
            "identity": key,
            "camera": item.get("candidate", {}).get("camera", "Unknown"),
            "nvr": item.get("candidate", {}).get("nvr", "Unknown"),
            "channel": item.get("candidate", {}).get("channel"),
            "elapsed_seconds": elapsed,
            "remaining_seconds": max(0, MOVEMENT_CONFIRMATION_SECONDS - elapsed),
            "confirmation_seconds": MOVEMENT_CONFIRMATION_SECONDS,
        })
    return {
        "total_movements": len(history),
        "unique_cameras": len(by_camera),
        "by_camera": by_camera,
        "pending_movements": len(pending_items),
        "pending": pending_items,
        "confirmation_seconds": MOVEMENT_CONFIRMATION_SECONDS,
    }


def _find_nvr(name: str):
    for nvr in NVRS:
        if nvr["name"].lower() == str(name).lower():
            return nvr
    return None


def _find_channel_xml(nvr: dict, channel_id: int):
    """Read the exact NVR InputProxyChannel XML.

    Some Hikvision NVR firmwares are strict about the XML structure used by
    PUT /ISAPI/ContentMgmt/InputProxy/channels/<ID>.  Returning the original
    response verbatim lets name-only updates preserve namespaces, optional
    elements and the XML declaration instead of rebuilding the object with
    ElementTree.
    """
    r = _nvr_request(
        nvr,
        "GET",
        f"/ISAPI/ContentMgmt/InputProxy/channels/{int(channel_id)}",
    )
    if r.ok and r.text.strip():
        return r.text

    r = _nvr_request(nvr, "GET", "/ISAPI/ContentMgmt/InputProxy/channels")
    if not r.ok:
        raise RuntimeError(
            f"Unable to read channel configuration: HTTP {r.status_code} {r.text[:500]}"
        )

    root = ET.fromstring(r.text)
    for node in root.findall(".//{*}InputProxyChannel"):
        id_node = node.find("{*}id")
        if id_node is not None and id_node.text:
            try:
                if int(id_node.text.strip()) == int(channel_id):
                    return ET.tostring(node, encoding="unicode")
            except ValueError:
                pass

    raise RuntimeError(f"Channel {channel_id} not found")


def _xml_escape(value: Any) -> str:
    return html.escape(str(value).strip(), quote=False)


def _replace_xml_element(xml: str, tag: str, value: Any) -> tuple[str, bool]:
    """Replace the text of an XML element while preserving the original XML."""
    safe = _xml_escape(value)
    pattern = re.compile(
        rf"(<(?:[A-Za-z_][\w.\-]*:)?{re.escape(tag)}\b[^>]*>).*?"
        rf"(</(?:[A-Za-z_][\w.\-]*:)?{re.escape(tag)}>)",
        re.IGNORECASE | re.DOTALL,
    )
    updated, count = pattern.subn(rf"\g<1>{safe}\g<2>", xml, count=1)
    return updated, bool(count)


def _insert_xml_element(xml: str, tag: str, value: Any) -> tuple[str, bool]:
    """Insert a simple child element after <id> using the existing namespace style."""
    safe = _xml_escape(value)

    # Prefer the existing <id> closing tag so the element stays inside
    # InputProxyChannel and does not disturb the remaining channel structure.
    pattern = re.compile(
        rf"(</(?:[A-Za-z_][\w.\-]*:)?id>)",
        re.IGNORECASE,
    )
    updated, count = pattern.subn(rf"\g<1><{tag}>{safe}</{tag}>", xml, count=1)
    return updated, bool(count)


def _patch_channel_xml(xml: str, changes: Dict[str, Any]) -> str:
    """Patch only requested fields without reconstructing Hikvision XML."""
    updated = xml

    if changes.get("name") is not None:
        updated, found = _replace_xml_element(updated, "name", changes["name"])
        if not found:
            updated, inserted = _insert_xml_element(updated, "name", changes["name"])
            if not inserted:
                raise RuntimeError("Unable to add <name> to the NVR channel XML")

    if changes.get("ip") is not None:
        updated, found = _replace_xml_element(updated, "ipAddress", changes["ip"])
        if not found:
            # IP editing is less firmware-universal than a name edit.  Use
            # ElementTree only for this fallback so the existing name-only path
            # remains byte-for-byte conservative.
            root = ET.fromstring(updated)
            descriptor = root.find(".//{*}sourceInputPortDescriptor")
            if descriptor is None:
                descriptor = ET.SubElement(root, "sourceInputPortDescriptor")
            ip_node = descriptor.find("{*}ipAddress")
            if ip_node is None:
                ip_node = ET.SubElement(descriptor, "ipAddress")
            ip_node.text = str(changes["ip"]).strip()
            updated = ET.tostring(root, encoding="unicode")

    if changes.get("enabled") is not None:
        value = "true" if bool(changes["enabled"]) else "false"
        updated, found = _replace_xml_element(updated, "enabled", value)
        if not found:
            updated, found = _replace_xml_element(updated, "enable", value)
        if not found:
            # Only add enabled when explicitly requested.  The previous code
            # always sent enabled=true from the UI, which caused unnecessary
            # full channel rewrites on name-only edits.
            root = ET.fromstring(updated)
            node = root.find("{*}enabled")
            if node is None:
                node = ET.SubElement(root, "enabled")
            node.text = value
            updated = ET.tostring(root, encoding="unicode")

    return updated


def _refresh_local_camera_cache(nvr_name: str, channel_id: int, changes: Dict[str, Any]):
    """Immediately update VisionGuard's in-memory camera inventory after NVR save."""
    try:
        from . import crud
        key_fn = getattr(crud, "_key", None)
        cache = getattr(crud, "_CAMERA_CACHE", None)
        lock = getattr(crud, "_CACHE_LOCK", None)
        if key_fn is None or cache is None:
            return

        key = key_fn(nvr_name, int(channel_id))
        if lock:
            with lock:
                item = cache.get(key)
                if item:
                    if changes.get("name") is not None:
                        item["name"] = str(changes["name"]).strip()
                    if changes.get("ip") is not None:
                        item["ip"] = str(changes["ip"]).strip()
                    if changes.get("enabled") is not None:
                        item["enabled"] = bool(changes["enabled"])
        else:
            item = cache.get(key)
            if item:
                if changes.get("name") is not None:
                    item["name"] = str(changes["name"]).strip()
                if changes.get("ip") is not None:
                    item["ip"] = str(changes["ip"]).strip()
                if changes.get("enabled") is not None:
                    item["enabled"] = bool(changes["enabled"])
    except Exception as exc:
        print("[ENTERPRISE] Local camera cache refresh skipped:", exc)


def update_camera(nvr_name: str, channel_id: int, changes: Dict[str, Any]):
    nvr = _find_nvr(nvr_name)
    if not nvr:
        raise ValueError(f"NVR not found: {nvr_name}")

    # Reject empty/unknown fields so a simple name edit cannot accidentally
    # rewrite unrelated NVR configuration.
    allowed = {"name", "ip", "enabled"}
    changes = {k: v for k, v in (changes or {}).items() if k in allowed and v is not None}
    if not changes:
        raise ValueError("No supported camera changes supplied")

    # Name-only updates use the exact XML returned by the NVR.  This is the
    # safest path for Hikvision firmwares that reject rebuilt InputProxy XML.
    original = _find_channel_xml(nvr, channel_id)
    body = _patch_channel_xml(original, changes)

    headers = {
        "Accept": "application/xml",
        "Content-Type": "application/xml; charset=UTF-8",
    }
    url = f"http://{nvr['ip']}:{nvr['port']}/ISAPI/ContentMgmt/InputProxy/channels/{int(channel_id)}"

    r = requests.put(
        url,
        auth=HTTPDigestAuth(nvr["username"], nvr["password"]),
        data=body.encode("utf-8"),
        headers=headers,
        timeout=12,
    )

    if not r.ok:
        detail = r.text.strip()
        # Keep the useful Hikvision response in the UI instead of hiding it.
        raise RuntimeError(
            f"NVR rejected camera update: HTTP {r.status_code} {detail[:800]}"
        )

    _refresh_local_camera_cache(nvr_name, channel_id, changes)

    add_alert(
        "CAMERA SETTINGS",
        "INFO",
        f"Camera settings changed - {changes.get('name') or channel_id}",
        f"{nvr_name} CH-{channel_id}: {', '.join(changes.keys())}",
    )

    return {
        "success": True,
        "nvr": nvr_name,
        "channel": channel_id,
        "changes": changes,
        "status": r.status_code,
        "message": "NVR camera configuration updated successfully",
    }


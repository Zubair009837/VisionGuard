import threading
import time
import os
import re
import json
from datetime import datetime
from xml.sax.saxutils import escape
import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPDigestAuth
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .config import (
    NVRS,
    NVR_TIME_CHANGE_EMAIL_ENABLED,
    NVR_TIME_DRIFT_ALERT_SECONDS,
    NVR_TIME_AUTO_SYNC_ENABLED,
    NVR_TIME_CHANGE_CONFIRM_SECONDS,
    NVR_TIME_MONITOR_INTERVAL_SECONDS,
    NVR_TIME_CHANGE_MIN_SECONDS,
)
from .email_service import send_nvr_health_email

router = APIRouter(prefix="/nvr-control", tags=["NVR Control Center"])
STATE_FILE = os.path.join(os.path.dirname(__file__), "nvr_time_guard.json")
_lock = threading.Lock()
_last_state = {}
_monitor_started = False
_candidate_changes = {}


def _load():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f) or {"events": []}
    except Exception:
        pass
    return {"events": []}


def _save(data):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def _client(nvr):
    return requests.Session()


def _request(nvr, endpoint, method="GET", body=None, timeout=10, content_type="application/xml"):
    url = f"http://{nvr['ip']}:{nvr.get('port',80)}{endpoint}"
    s = _client(nvr)
    s.auth = HTTPDigestAuth(nvr["username"], nvr["password"])
    headers = {"Accept": "application/xml"}
    if body is not None:
        headers["Content-Type"] = content_type
    r = s.request(method, url, data=body, headers=headers, timeout=timeout)
    # Keep the response body available to callers. Hikvision frequently puts
    # the useful badXmlContent/statusString in the XML response even on HTTP 400.
    if r.status_code >= 400:
        detail = (r.text or "").strip().replace("\n", " ")
        if len(detail) > 900:
            detail = detail[:900] + "..."
        raise requests.HTTPError(f"HTTP {r.status_code} {r.reason}; response={detail}", response=r)
    return r


def _local_text(root, name):
    for el in root.iter():
        if el.tag.split("}")[-1] == name and el.text:
            return el.text.strip()
    return ""


def _parse_xml_response(text):
    try:
        return ET.fromstring(text)
    except Exception:
        return None


def _time_fields(text):
    root = _parse_xml_response(text or "")
    if root is None:
        return "", "", ""
    return (
        _local_text(root, "localTime"),
        _local_text(root, "timeZone"),
        _local_text(root, "timeMode"),
    )


def read_time_details(nvr):
    # Primary endpoint.
    try:
        r = _request(nvr, "/ISAPI/System/time")
        local, zone, mode = _time_fields(r.text)
        if local:
            return {"local_time": local, "time_zone": zone, "time_mode": mode, "source": "System/time"}
    except Exception:
        pass

    # Hikvision also exposes the local time as a plain ISO-8601 resource.
    r = _request(nvr, "/ISAPI/System/time/localTime", timeout=8)
    local = (r.text or "").strip().strip('"')
    if local.startswith("<"):
        local, zone, mode = _time_fields(local)
    else:
        zone = ""
        mode = ""
    return {"local_time": local, "time_zone": zone, "time_mode": mode, "source": "System/time/localTime"}


def read_time(nvr):
    return read_time_details(nvr).get("local_time", "")


def read_device_info(nvr):
    r = _request(nvr, "/ISAPI/System/deviceInfo")
    root = ET.fromstring(r.text)
    return {k: _local_text(root, k) for k in ["deviceName","model","serialNumber","firmwareVersion","firmwareReleasedDate","hardwareVersion"]}


def read_network(nvr):
    r = _request(nvr, "/ISAPI/System/Network/interfaces/1")
    root = ET.fromstring(r.text)
    return {"ip": _local_text(root,"ipAddress"), "mask": _local_text(root,"subnetMask"), "gateway": _local_text(root,"DefaultGateway") or _local_text(root,"gateway"), "dns": _local_text(root,"primaryDNS")}


def parse_nvr_datetime(value):
    """
    Parse Hikvision NVR time values from the common ISAPI formats.

    Firmware versions may return:
      - 2026-08-19T12:44:30
      - 2026-08-19T12:44:30+05:30
      - 2026-08-19T12:44:30.000+05:30
      - 2026-08-19 12:44:30
      - quoted values / XML text with surrounding whitespace
      - ISO timestamps containing a timezone name or trailing text

    The daily report must never classify an NVR as offline merely because
    the clock value could not be parsed.
    """
    raw = str(value or "").strip()

    if not raw:
        return None

    # Remove common wrapping quotes.
    raw = raw.strip('"').strip("'").strip()

    # Normalize UTC suffix.
    normalized = raw.replace("Z", "+00:00")

    # First: native ISO parser.
    candidates = [
        normalized,
        normalized.split(" ")[0] if " " in normalized and "T" not in normalized else normalized,
    ]

    for candidate in candidates:
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo:
                # VisionGuard runs the site in local time. Convert an
                # offset-aware NVR value to the machine's local timezone
                # before removing tzinfo.
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
        except (ValueError, TypeError):
            pass

    # Second: remove milliseconds / timezone text and parse the leading
    # date-time portion. This handles firmware strings such as:
    # 2026-08-19T12:44:30+05:30 (IST)
    match = re.search(
        r"(\d{4}-\d{2}-\d{2})[T\s]"
        r"(\d{2}:\d{2}:\d{2})"
        r"(?:\.\d+)?"
        r"(?:Z|[+-]\d{2}:?\d{2})?",
        raw,
    )

    if match:
        value2 = f"{match.group(1)}T{match.group(2)}"
        try:
            return datetime.strptime(
                value2,
                "%Y-%m-%dT%H:%M:%S",
            )
        except ValueError:
            pass

    # Third: common Hikvision legacy formats.
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(
                raw,
                fmt,
            )
        except ValueError:
            continue

    return None


def audit_event(event_type, nvr, details):
    with _lock:
        data = _load()
        data.setdefault("events", []).append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": event_type,
            "nvr": nvr.get("name"),
            "ip": nvr.get("ip"),
            "details": details,
        })
        data["events"] = data["events"][-1000:]
        _save(data)


def _server_now():
    return datetime.now()


def _mark_time_state_synced(nvr, after):
    key = str(nvr.get("id", nvr.get("ip")))
    _last_state[key] = {
        "nvr": nvr.get("name"), "ip": nvr.get("ip"), "nvr_time": after,
        "difference_seconds": 0.0, "threshold_seconds": NVR_TIME_DRIFT_ALERT_SECONDS,
        "time_drift": False, "checked_at": _server_now().strftime("%Y-%m-%d %H:%M:%S")
    }
    _candidate_changes.pop(key, None)


def _send_time_change_email(nvr, details):
    if not NVR_TIME_CHANGE_EMAIL_ENABLED:
        return
    old = str(details.get("old_time") or "").strip()
    new = str(details.get("new_time") or details.get("target_time") or "").strip()
    if old and new and old == new:
        print(f"[TIME-GUARD] Suppressed false time-change email for {nvr.get('name')}: old == new")
        return
    try:
        old_time = details.get("old_time") or "Unknown"
        new_time = details.get("new_time") or details.get("target_time") or "Unknown"
        send_nvr_health_email(
            nvr=nvr.get("name"), ip=nvr.get("ip"), severity="WARNING",
            title="NVR TIME CHANGE DETECTED - AUTO SYNC",
            description=(
                f"{nvr.get('name')} clock changed/drifted. Previous NVR time: {old_time}. "
                f"VisionGuard confirmed the change for {NVR_TIME_CHANGE_CONFIRM_SECONDS} seconds "
                f"and automatically synchronized the clock."
            ),
            metric=f"Old={old_time}; New={new_time}; Method={details.get('method','')}",
            threshold=f"Any clock change confirmed for {NVR_TIME_CHANGE_CONFIRM_SECONDS} seconds",
            event_time=details.get("server_time") or _server_now().strftime("%Y-%m-%dT%H:%M:%S"),
        )
    except Exception as exc:
        print(f"[TIME-GUARD] time-change email error for {nvr.get('name')}: {exc}")


def _auto_sync_nvr_clock(nvr):
    """Set NVR to the VisionGuard server clock and verify it."""
    target = _server_now()
    local_time = target.strftime("%Y-%m-%dT%H:%M:%S")
    before = ""
    try:
        before = read_time(nvr)
    except Exception:
        pass
    errors = []
    for method_name, setter in (
        ("System/time/localTime", lambda: _try_set_local_time_endpoint(nvr, local_time)),
        ("System/time XML", lambda: _try_set_time_xml(nvr, local_time, read_time_details(nvr).get("time_zone", ""))),
    ):
        try:
            response = setter()
            status = _response_status(response.text)
            after = read_time(nvr)
            details = {
                "old_time": before,
                "new_time": after or local_time,
                "method": method_name,
                "response": status or {},
                "server_time": target.strftime("%Y-%m-%dT%H:%M:%S"),
                "reason": "AUTO_CONFIRMED_CLOCK_CHANGE",
            }
            audit_event("NVR_TIME_AUTO_SYNCED", nvr, details)
            _mark_time_state_synced(nvr, after or local_time)
            _send_time_change_email(nvr, details)
            return {"ok": True, **details}
        except Exception as exc:
            errors.append(f"{method_name}: {exc}")
    details = {"ok": False, "old_time": before, "target_time": local_time, "error": " | ".join(errors)}
    audit_event("NVR_TIME_AUTO_SYNC_FAILED", nvr, details)
    if NVR_TIME_CHANGE_EMAIL_ENABLED:
        try:
            send_nvr_health_email(
                nvr=nvr.get("name"), ip=nvr.get("ip"), severity="CRITICAL",
                title="NVR TIME AUTO-SYNC FAILED",
                description=f"VisionGuard detected a clock change on {nvr.get('name')} but could not automatically correct it.",
                metric=details["error"], threshold="Automatic time sync must succeed",
                event_time=target.strftime("%Y-%m-%dT%H:%M:%S"),
            )
        except Exception as exc:
            print(f"[TIME-GUARD] auto-sync failure email error: {exc}")
    return details


def check_one(nvr, tolerance_seconds=NVR_TIME_DRIFT_ALERT_SECONDS, send_alert=True):
    nvr_time = read_time(nvr)
    nvr_dt = parse_nvr_datetime(nvr_time)
    if nvr_dt is None:
        return {
            "nvr": nvr.get("name"), "ip": nvr.get("ip"), "nvr_time": nvr_time or "",
            "difference_seconds": None, "threshold_seconds": tolerance_seconds, "time_drift": None,
            "checked_at": _server_now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": "NVR returned an empty or unsupported time value",
        }

    now = _server_now()
    signed_diff = (now - nvr_dt).total_seconds()
    diff = abs(signed_diff)
    drift = diff > tolerance_seconds
    key = str(nvr.get("id", nvr.get("ip")))
    old = _last_state.get(key)
    result = {
        "nvr": nvr.get("name"), "ip": nvr.get("ip"), "nvr_time": nvr_time,
        "difference_seconds": round(diff, 1), "signed_difference_seconds": round(signed_diff, 1),
        "threshold_seconds": tolerance_seconds, "time_drift": drift,
        "checked_at": now.strftime("%Y-%m-%d %H:%M:%S")
    }

    # Large drift alert/recovery remains available for the existing health view.
    if drift and (not old or not old.get("time_drift")):
        audit_event("NVR_TIME_DRIFT", nvr, result)
        # Do not send an immediate drift email. The confirmed clock-change
        # guard below is responsible for email + auto-remediation after 30s.
        # This prevents duplicate/false alerts from the drift sampler.
    if not drift and old and old.get("time_drift"):
        audit_event("NVR_TIME_DRIFT_RECOVERED", nvr, result)
        # Recovery is recorded silently here; the confirmed-change guard
        # controls notification to avoid duplicate emails.

    # Detect an actual CLOCK OFFSET change, not the normal second-by-second
    # progression of the NVR clock. The offset is compared with the previous
    # sample, so ordinary ticking does not create false alarms.
    previous_offset = old.get("signed_difference_seconds") if old else None
    offset_change = (
        abs(signed_diff - float(previous_offset))
        if previous_offset is not None else 0.0
    )
    if (
        previous_offset is not None
        and offset_change >= float(NVR_TIME_CHANGE_MIN_SECONDS)
        and abs(signed_diff) >= float(NVR_TIME_CHANGE_MIN_SECONDS)
    ):
        candidate = _candidate_changes.get(key)
        if not candidate:
            _candidate_changes[key] = {
                "started": time.time(),
                "previous_time": old.get("nvr_time"),
                "first_changed_time": nvr_time,
                "offset_before": round(float(previous_offset), 1),
                "offset_after": round(signed_diff, 1),
                "last_offset_change": round(offset_change, 1),
            }
            audit_event("NVR_TIME_CHANGE_CANDIDATE", nvr, {
                "old_time": old.get("nvr_time"),
                "new_time": nvr_time,
                "offset_before_seconds": round(float(previous_offset), 1),
                "offset_after_seconds": round(signed_diff, 1),
                "offset_change_seconds": round(offset_change, 1),
                "confirm_after_seconds": NVR_TIME_CHANGE_CONFIRM_SECONDS,
                "detected_at": result["checked_at"],
            })
        else:
            candidate["last_offset_change"] = round(offset_change, 1)
            elapsed = time.time() - float(candidate.get("started", time.time()))
            if elapsed >= NVR_TIME_CHANGE_CONFIRM_SECONDS:
                if NVR_TIME_AUTO_SYNC_ENABLED:
                    sync_result = _auto_sync_nvr_clock(nvr)
                    result["auto_sync"] = sync_result
                    # _auto_sync_nvr_clock updates _last_state and clears candidate.
                    if sync_result.get("ok"):
                        return result
                else:
                    _send_time_change_email(nvr, {
                        "old_time": candidate["previous_time"],
                        "new_time": nvr_time,
                        "server_time": result["checked_at"],
                        "method": "Detection only",
                    })
                    _candidate_changes.pop(key, None)

    _last_state[key] = result
    return result


def monitor_loop():
    global _monitor_started
    if _monitor_started:
        return
    _monitor_started = True
    print(
        f"[TIME-GUARD] Monitoring {len(NVRS)} NVRs every "
        f"{NVR_TIME_MONITOR_INTERVAL_SECONDS}s | any clock change | "
        f"confirm={NVR_TIME_CHANGE_CONFIRM_SECONDS}s | auto-sync={NVR_TIME_AUTO_SYNC_ENABLED}"
    )
    while True:
        for nvr in NVRS:
            try:
                check_one(nvr, NVR_TIME_DRIFT_ALERT_SECONDS, True)
            except Exception as exc:
                print(f"[TIME-GUARD] {nvr.get('name')} check failed: {exc}")
        time.sleep(NVR_TIME_MONITOR_INTERVAL_SECONDS)


def start_time_monitor():
    t = threading.Thread(target=monitor_loop, name="NVR-Time-Guard", daemon=True)
    t.start()


class TimePayload(BaseModel):
    localTime: str | None = None


@router.get("/nvrs")
def list_nvrs():
    return [{"id": n.get("id"), "name": n.get("name"), "ip": n.get("ip"), "port": n.get("port")} for n in NVRS]


def find_nvr(nvr_id):
    for n in NVRS:
        if str(n.get("id")) == str(nvr_id):
            return n
    raise HTTPException(404, "NVR not found")


@router.get("/{nvr_id}/overview")
def overview(nvr_id: int):
    nvr = find_nvr(nvr_id)
    try:
        td = read_time_details(nvr)
        return {"ok": True, "nvr": nvr.get("name"), "time": td.get("local_time"), "time_zone": td.get("time_zone"), "time_mode": td.get("time_mode"), "device": read_device_info(nvr)}
    except Exception as exc:
        raise HTTPException(502, f"NVR API error: {exc}")


@router.get("/{nvr_id}/time")
def current_time(nvr_id: int):
    nvr = find_nvr(nvr_id)
    try:
        td = read_time_details(nvr)
        return {"nvr": nvr.get("name"), "time": td.get("local_time"), "time_zone": td.get("time_zone"), "time_mode": td.get("time_mode"), "source": td.get("source"), "server_time": datetime.now().isoformat(timespec="seconds")}
    except Exception as exc:
        raise HTTPException(502, f"Unable to read NVR time: {exc}")


def _response_status(text):
    root = _parse_xml_response(text or "")
    if root is None:
        return None
    return {
        "status_code": _local_text(root, "statusCode"),
        "status_string": _local_text(root, "statusString"),
        "sub_status_code": _local_text(root, "subStatusCode"),
    }


def _try_set_local_time_endpoint(nvr, local_time):
    # Hikvision documents this endpoint as accepting a plain ISO-8601 string.
    # It avoids firmware differences around the Time XML block.
    body = local_time.encode("utf-8")
    return _request(nvr, "/ISAPI/System/time/localTime", "PUT", body, timeout=10, content_type="text/plain")


def _try_set_time_xml(nvr, local_time, time_zone=""):
    # Hikvision ISAPI Time XML requires localTime and, on many firmware
    # versions, timeZone. Use the documented ISAPI namespace/version.
    tz = time_zone or "CST-5:30:00"
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Time xmlns="http://www.isapi.org/ver20/XMLSchema" version="2.0">'
        '<timeMode>manual</timeMode>'
        f'<localTime>{escape(local_time)}</localTime>'
        f'<timeZone>{escape(tz)}</timeZone>'
        '</Time>'
    )
    return _request(nvr, "/ISAPI/System/time", "PUT", xml, timeout=10, content_type="application/xml")


@router.post("/{nvr_id}/time")
def set_time(nvr_id: int, payload: TimePayload):
    nvr = find_nvr(nvr_id)
    # IMPORTANT: browser toISOString() is UTC. If the payload is omitted or
    # invalid, always use the VisionGuard server's local clock instead.
    local_time = (payload.localTime or "").strip()
    if not local_time:
        local_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    else:
        parsed = parse_nvr_datetime(local_time)
        if parsed is None:
            raise HTTPException(400, f"Invalid localTime: {local_time}")
        local_time = parsed.strftime("%Y-%m-%dT%H:%M:%S")

    before = ""
    try:
        before = read_time(nvr)
    except Exception:
        pass

    errors = []
    # Method 1: direct localTime endpoint.
    try:
        r = _try_set_local_time_endpoint(nvr, local_time)
        status = _response_status(r.text)
        # Some firmware returns an empty body on success.
        after = read_time(nvr)
        details = {"old_time": before, "new_time": after or local_time, "method": "System/time/localTime", "response": status or {}, "server_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")}
        audit_event("NVR_TIME_CHANGED", nvr, details)
        # Keep the time guard state aligned with the newly synced clock so the
        # next 60-second check does not generate a duplicate drift alert.
        key = str(nvr.get("id", nvr.get("ip")))
        _last_state[key] = {"nvr": nvr.get("name"), "ip": nvr.get("ip"), "nvr_time": after or local_time,
                            "difference_seconds": 0.0, "threshold_seconds": NVR_TIME_DRIFT_ALERT_SECONDS,
                            "time_drift": False, "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        if NVR_TIME_CHANGE_EMAIL_ENABLED:
            try:
                changed_by = before or "Unknown"
                send_nvr_health_email(
                    nvr=nvr.get("name"), ip=nvr.get("ip"), severity="WARNING",
                    title="NVR TIME CHANGED",
                    description=(f"VisionGuard changed the NVR clock. Previous time: {changed_by}. "
                                 f"New time: {after or local_time}. The change was verified successfully."),
                    metric=f"Old={changed_by}; New={after or local_time}",
                    threshold=f"Drift alert threshold={NVR_TIME_DRIFT_ALERT_SECONDS} seconds",
                    event_time=details["server_time"],
                )
            except Exception as exc:
                print(f"[TIME-GUARD] time-change email error for {nvr.get('name')}: {exc}")
        return {"ok": True, "nvr": nvr.get("name"), "old_time": before, "new_time": after or local_time, "method": "System/time/localTime", "response": status or {}}
    except Exception as exc:
        errors.append(f"localTime endpoint: {exc}")

    # Method 2: full Time XML with namespace + timezone.
    try:
        zone = ""
        try:
            zone = read_time_details(nvr).get("time_zone", "")
        except Exception:
            pass
        r = _try_set_time_xml(nvr, local_time, zone)
        status = _response_status(r.text)
        after = read_time(nvr)
        details = {"old_time": before, "new_time": after or local_time, "method": "System/time XML", "response": status or {}, "server_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z")}
        audit_event("NVR_TIME_CHANGED", nvr, details)
        key = str(nvr.get("id", nvr.get("ip")))
        _last_state[key] = {"nvr": nvr.get("name"), "ip": nvr.get("ip"), "nvr_time": after or local_time,
                            "difference_seconds": 0.0, "threshold_seconds": NVR_TIME_DRIFT_ALERT_SECONDS,
                            "time_drift": False, "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        if NVR_TIME_CHANGE_EMAIL_ENABLED:
            try:
                changed_by = before or "Unknown"
                send_nvr_health_email(
                    nvr=nvr.get("name"), ip=nvr.get("ip"), severity="WARNING",
                    title="NVR TIME CHANGED",
                    description=(f"VisionGuard changed the NVR clock. Previous time: {changed_by}. "
                                 f"New time: {after or local_time}. The change was verified successfully."),
                    metric=f"Old={changed_by}; New={after or local_time}",
                    threshold=f"Drift alert threshold={NVR_TIME_DRIFT_ALERT_SECONDS} seconds",
                    event_time=details["server_time"],
                )
            except Exception as exc:
                print(f"[TIME-GUARD] time-change email error for {nvr.get('name')}: {exc}")
        return {"ok": True, "nvr": nvr.get("name"), "old_time": before, "new_time": after or local_time, "method": "System/time XML", "response": status or {}}
    except Exception as exc:
        errors.append(f"System/time XML: {exc}")

    # Return a structured failure instead of an opaque 500/502 so the UI can
    # show the actual Hikvision response and continue operating.
    return {
        "ok": False,
        "nvr": nvr.get("name"),
        "old_time": before,
        "new_time": None,
        "error": "Unable to set NVR time. " + " | ".join(errors),
    }


@router.post("/time/sync-selected")
def sync_selected_times(payload: dict = None):
    """One-click time synchronization for selected NVRs (or all NVRs).
    The operation uses the same verified Hikvision time-sync logic as the
    individual Sync Time button and returns per-NVR results.
    """
    payload = payload or {}
    ids = payload.get("nvr_ids")
    selected = NVRS if not ids else [n for n in NVRS if str(n.get("id")) in {str(x) for x in ids}]
    if not selected:
        raise HTTPException(400, "No NVRs selected")
    results = []
    for nvr in selected:
        result = _auto_sync_nvr_clock(nvr)
        results.append({"nvr_id": nvr.get("id"), "nvr": nvr.get("name"), **result})
    ok = sum(1 for x in results if x.get("ok"))
    return {"success": ok == len(results), "total": len(results), "succeeded": ok, "failed": len(results)-ok, "results": results}


@router.get("/{nvr_id}/network")
def network(nvr_id: int):
    nvr = find_nvr(nvr_id)
    try:
        return {"ok": True, **read_network(nvr)}
    except Exception as exc:
        raise HTTPException(502, f"Unable to read network settings: {exc}")


@router.get("/time/events")
def time_events():
    return list(reversed(_load().get("events", [])))


@router.post("/time/check-all")
def check_all():
    results = []
    for n in NVRS:
        try:
            results.append(check_one(n, NVR_TIME_DRIFT_ALERT_SECONDS, True))
        except Exception as exc:
            results.append({"nvr": n.get("name"), "ip": n.get("ip"), "time_drift": None, "error": str(exc)})
    return results

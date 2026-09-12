# ==========================================================
# VisionGuard AI - Authorized Hikvision Password Recovery
# ==========================================================
# Uses Hikvision's documented recovery workflow. VisionGuard does
# not bypass authentication or manufacture a device reset code.

import secrets
import time
from typing import Dict, Any

RECOVERY_EMAIL = "Zubair.khan@1mg.com"
HIKVISION_RECOVERY_EMAIL = "pw_recovery@hikvision.com"
SESSION_TTL_SECONDS = 30 * 60

_SESSIONS: Dict[str, Dict[str, Any]] = {}

def _cleanup():
    now=time.time()
    for k,v in list(_SESSIONS.items()):
        if now-float(v.get("created_at",now)) > SESSION_TTL_SECONDS:
            _SESSIONS.pop(k,None)

def create_recovery_session(nvr: dict) -> dict:
    _cleanup()
    sid=secrets.token_urlsafe(24)
    session={
        "nvr_name": nvr.get("name") or nvr.get("nvr_name"),
        "ip": nvr.get("ip"),
        "port": nvr.get("port",80),
        "model": nvr.get("model") or "Unknown",
        "firmware": nvr.get("firmware") or "Unknown",
        "serial": nvr.get("serial") or nvr.get("serial_number"),
        "recovery_email": RECOVERY_EMAIL,
        "hikvision_recovery_email": HIKVISION_RECOVERY_EMAIL,
        "created_at": time.time(),
        "qr_submitted": False,
        "otp_entered": False,
    }
    _SESSIONS[sid]=session
    return {"session_id":sid,"nvr":_public(session),"status":"RECOVERY_REQUEST_READY","expires_in":SESSION_TTL_SECONDS}

def mark_qr_submitted(session_id:str)->dict:
    _cleanup(); s=_SESSIONS.get(session_id)
    if not s: raise ValueError("Recovery session expired or not found.")
    s["qr_submitted"]=True; s["qr_submitted_at"]=time.time()
    return {"session_id":session_id,"status":"HIKVISION_RECOVERY_REQUEST_SENT","nvr":_public(s)}

def record_hikvision_code(session_id:str, code:str)->dict:
    _cleanup(); s=_SESSIONS.get(session_id)
    if not s: raise ValueError("Recovery session expired or not found.")
    code=str(code or '').strip()
    if not code: raise ValueError("Verification code is required.")
    # Do not locally validate the code: only the NVR/Hikvision recovery flow can validate it.
    s["otp_entered"]=True
    return {"session_id":session_id,"status":"VERIFICATION_CODE_CAPTURED","nvr":_public(s)}

def get_session(session_id:str)->dict:
    _cleanup(); s=_SESSIONS.get(session_id)
    if not s: raise ValueError("Recovery session expired or not found.")
    return _public(s)

def _public(s):
    return {k:v for k,v in s.items() if k not in {"created_at"}}

def supported_recovery_workflow(nvr_name):
    return {
        "nvr":nvr_name,
        "status":"OFFICIAL_HIKVISION_RECOVERY",
        "recovery_email":RECOVERY_EMAIL,
        "hikvision_recovery_email":HIKVISION_RECOVERY_EMAIL,
        "steps":[
            "Select NVR and review device details",
            "Open the NVR login page and click Forgot Password",
            "Select Verify by Reserved Email when offered",
            "Export the recovery QR code",
            "Send the QR code to pw_recovery@hikvision.com",
            "Receive the verification code at the NVR's configured Reserved Email",
            "Enter the verification code in the official NVR recovery page",
            "Set and confirm the new NVR password",
            "Test the new NVR connection and update VisionGuard credentials",
        ],
        "note":"The NVR must support and have configured Reserved Email recovery. VisionGuard does not bypass Hikvision authentication.",
    }

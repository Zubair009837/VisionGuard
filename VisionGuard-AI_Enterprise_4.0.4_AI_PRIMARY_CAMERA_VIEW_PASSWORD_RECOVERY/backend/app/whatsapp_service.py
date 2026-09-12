# ==========================================================
# VisionGuard AI - WhatsApp Alert Service
# ==========================================================
"""Meta WhatsApp Cloud API integration with dashboard-managed settings."""
import json
import os
from pathlib import Path
import requests

CONFIG_FILE = Path(__file__).parent / "whatsapp_config.json"
DEFAULT_TO = "919548749677"


def _read():
    default = {
        "enabled": False,
        "to": DEFAULT_TO,
        "phone_number_id": "",
        "token": "",
    }
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                default.update(data)
    except Exception as exc:
        print(f"⚠️ WhatsApp config read error: {exc}")

    # Environment variables remain supported for server deployments.
    if os.getenv("VISIONGUARD_WHATSAPP_ENABLED") is not None:
        default["enabled"] = os.getenv("VISIONGUARD_WHATSAPP_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    default["token"] = os.getenv("VISIONGUARD_WHATSAPP_TOKEN", default.get("token", "")).strip()
    default["phone_number_id"] = os.getenv("VISIONGUARD_WHATSAPP_PHONE_NUMBER_ID", default.get("phone_number_id", "")).strip()
    default["to"] = os.getenv("VISIONGUARD_WHATSAPP_TO", default.get("to", DEFAULT_TO)).strip() or DEFAULT_TO
    return default


def get_whatsapp_config(mask_secrets=True):
    cfg = _read()
    if mask_secrets:
        return {
            "enabled": bool(cfg.get("enabled")),
            "to": cfg.get("to", DEFAULT_TO),
            "phone_number_id": cfg.get("phone_number_id", ""),
            "has_token": bool(cfg.get("token")),
            "configured": bool(cfg.get("token") and cfg.get("phone_number_id") and cfg.get("to")),
        }
    return cfg


def save_whatsapp_config(payload):
    current = _read()
    if "enabled" in payload:
        current["enabled"] = bool(payload.get("enabled"))
    if payload.get("to") is not None:
        value = str(payload.get("to", "")).strip().replace("+", "")
        current["to"] = value or DEFAULT_TO
    if payload.get("phone_number_id") is not None:
        current["phone_number_id"] = str(payload.get("phone_number_id", "")).strip()
    # Empty token means "keep existing" so the UI can safely edit other fields.
    if str(payload.get("token", "")).strip():
        current["token"] = str(payload.get("token")).strip()

    CONFIG_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def whatsapp_configured():
    cfg = _read()
    return bool(cfg.get("enabled") and cfg.get("token") and cfg.get("phone_number_id") and cfg.get("to"))


def send_whatsapp_alert(message: str):
    if not whatsapp_configured():
        return False
    cfg = _read()
    try:
        url = f"https://graph.facebook.com/v23.0/{cfg['phone_number_id']}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": cfg["to"],
            "type": "text",
            "text": {"preview_url": False, "body": str(message)[:4000]},
        }
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {cfg['token']}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if r.ok:
            print(f"📱 WHATSAPP ALERT SENT -> {cfg['to']}")
            return True
        print(f"⚠️ WHATSAPP ALERT FAILED | HTTP {r.status_code} | {r.text[:500]}")
    except Exception as exc:
        print(f"⚠️ WHATSAPP ALERT ERROR | {exc}")
    return False


def send_whatsapp_event(title, details="", severity="ALERT"):
    msg = f"VisionGuard AI\n{severity}: {title}\n{details}".strip()
    return send_whatsapp_alert(msg)

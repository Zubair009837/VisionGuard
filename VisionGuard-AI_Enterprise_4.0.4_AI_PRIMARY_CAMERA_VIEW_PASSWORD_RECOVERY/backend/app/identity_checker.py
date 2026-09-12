import json
from pathlib import Path
from datetime import datetime

from .email_service import send_identity_email

REGISTRY_FILE = Path(__file__).parent / "device_registry.json"


def check_identity(camera):
    """
    Checks whether the current device identity
    matches the one stored in registry.
    """

    if not REGISTRY_FILE.exists():
        return

    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except Exception:
        return

    key = f"{camera['nvr']}_{camera['id']}"

    if key not in registry:
        return

    saved = registry[key]

    alerts = []

    # Serial Number Check
    if saved.get("serial") != camera.get("serial"):
        alerts.append(
            f"Serial Changed : {saved.get('serial')} -> {camera.get('serial')}"
        )

    # MAC Address Check
    if saved.get("mac") != camera.get("mac"):
        alerts.append(
            f"MAC Changed : {saved.get('mac')} -> {camera.get('mac')}"
        )

    # Model Check
    if saved.get("model") != camera.get("model"):
        alerts.append(
            f"Model Changed : {saved.get('model')} -> {camera.get('model')}"
        )

    # Firmware Check
    if saved.get("firmware") != camera.get("firmware"):
        alerts.append(
            f"Firmware Changed : {saved.get('firmware')} -> {camera.get('firmware')}"
        )

    if alerts:

        print("\n" + "=" * 70)
        print("🚨 DEVICE IDENTITY ALERT")
        print("=" * 70)
        print(f"NVR    : {camera['nvr']}")
        print(f"Camera : {camera['name']}")
        print(f"IP     : {camera['ip']}")
        print("-" * 70)

        for alert in alerts:
            print("❌", alert)

        print("=" * 70)

        event_time = datetime.now().strftime("%d %b %Y %I:%M:%S %p")

        send_identity_email(
            camera=camera["name"],
            nvr=camera["nvr"],
            ip=camera["ip"],
            issues="<br>".join(alerts),
            event_time=event_time
        )
import json
from pathlib import Path
from datetime import datetime

REGISTRY_FILE = Path(__file__).parent / "device_registry.json"


def load_registry():
    if not REGISTRY_FILE.exists():
        return {}

    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_registry(data):
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def register_device(camera):
    """
    Register camera if not already present.
    """

    registry = load_registry()

    key = f"{camera['nvr']}_{camera['id']}"

    now = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

    if key not in registry:

        registry[key] = {
            "camera": camera["name"],
            "nvr": camera["nvr"],
            "ip": camera["ip"],
            "serial": camera.get("serial", ""),
            "mac": camera.get("mac", ""),
            "model": camera.get("model", ""),
            "firmware": camera.get("firmware", ""),
            "first_seen": now,
            "last_seen": now
        }

        print(f"✅ Registered : {camera['name']}")

    else:

        registry[key]["last_seen"] = now

    save_registry(registry)


def get_device(camera):

    registry = load_registry()

    key = f"{camera['nvr']}_{camera['id']}"

    return registry.get(key)


def update_device(camera):

    registry = load_registry()

    key = f"{camera['nvr']}_{camera['id']}"

    if key not in registry:
        return

    registry[key]["ip"] = camera["ip"]
    registry[key]["serial"] = camera.get("serial", "")
    registry[key]["mac"] = camera.get("mac", "")
    registry[key]["model"] = camera.get("model", "")
    registry[key]["firmware"] = camera.get("firmware", "")
    registry[key]["last_seen"] = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

    save_registry(registry)
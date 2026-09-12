from collections import defaultdict
from datetime import datetime

from .alert_manager import add_alert

from .email_service import (
    send_ip_conflict_email,
    send_ip_conflict_resolved_email,
)

# ==========================================================
# Runtime Storage
# ==========================================================

sent_conflicts = set()
active_conflicts = set()

# ==========================================================
# Detect Duplicate IPs
# ==========================================================

def check_ip_conflicts(cameras):
    ip_map = defaultdict(list)
    for camera in cameras:
        ip = camera.get("ip","").strip()
        if ip:
            ip_map[ip].append(camera)
    conflicts=[]
    for ip,devices in ip_map.items():
        if len(devices)>1:
            conflicts.append({"ip":ip,"devices":devices})
    return conflicts

# ==========================================================
# Print & Email Duplicate IPs
# ==========================================================

def print_conflicts(conflicts):
    global sent_conflicts, active_conflicts
    current_conflicts=set()

    if not conflicts:
        if active_conflicts:
            event_time=datetime.now().strftime("%d %b %Y %I:%M:%S %p")
            send_ip_conflict_resolved_email(event_time=event_time)
            print("\n"+"="*70)
            print("✅ ALL IP CONFLICTS RESOLVED")
            print("="*70)
            print("📧 Recovery Email Sent")
        active_conflicts.clear()
        sent_conflicts.clear()
        return

    print("\n"+"="*70)
    print("🚨 IP CONFLICT DETECTED")
    print("="*70)

    for conflict in conflicts:
        conflict_key=conflict["ip"]
        current_conflicts.add(conflict_key)
        print(f"\nDuplicate IP : {conflict_key}")
        print("-"*70)
        for camera in conflict["devices"]:
            print(f"{camera['nvr']} | {camera['name']} | {camera['status']}")
        if conflict_key not in sent_conflicts:
            event_time=datetime.now().strftime("%d %b %Y %I:%M:%S %p")
            send_ip_conflict_email(
                camera=", ".join(c["name"] for c in conflict["devices"]),
                nvr=", ".join(sorted(set(c["nvr"] for c in conflict["devices"]))),
                ip=conflict_key,
                event_time=event_time
            )
            add_alert(
                "IP CONFLICT",
                "CRITICAL",
                f"Duplicate IP - {conflict_key}",
                " | ".join(
                    f"{c.get('nvr')} / {c.get('name')} / {c.get('ip')}"
                    for c in conflict["devices"]
                )
            )
            sent_conflicts.add(conflict_key)
            print(f"\n📧 Alert Email Sent ({conflict_key})")
        else:
            print(f"\n⏳ Email Already Sent ({conflict_key})")

    resolved=active_conflicts-current_conflicts
    if resolved:
        event_time=datetime.now().strftime("%d %b %Y %I:%M:%S %p")
        send_ip_conflict_resolved_email(event_time=event_time)
        for ip in sorted(resolved):
            print(f"✅ IP Conflict Resolved ({ip})")
        print("📧 Recovery Email Sent")

    active_conflicts=current_conflicts.copy()
    sent_conflicts.intersection_update(current_conflicts)
    print("="*70)

def has_ip_conflicts():
    return len(active_conflicts)>0

def get_conflict_count():
    return len(active_conflicts)

def get_conflict_ips():
    return sorted(active_conflicts)

def reset_ip_conflict_state():
    global sent_conflicts, active_conflicts
    sent_conflicts.clear()
    active_conflicts.clear()

__version__="2.0"
print("[VisionGuard AI] Enterprise IP Conflict Engine Loaded")

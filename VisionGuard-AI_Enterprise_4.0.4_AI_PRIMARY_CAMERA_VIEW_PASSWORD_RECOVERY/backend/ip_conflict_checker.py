from collections import defaultdict
from datetime import datetime

from .email_service import (
    send_ip_conflict_email,
    send_ip_conflict_resolved_email,
)

# ==========================================================
# Runtime Storage
# ==========================================================

# Stores conflicts for current scan
ip_map = {}

# Conflicts that have already generated an email
sent_conflicts = set()

# Active conflicts currently detected
active_conflicts = set()

# ==========================================================
# Build Conflict List
# ==========================================================

def check_ip_conflicts(cameras):
    """
    Detect duplicate IP addresses.

    Returns:
        [
            {
                "ip": "...",
                "devices": [...]
            }
        ]
    """

    global ip_map

    ip_map = defaultdict(list)

    for camera in cameras:

        ip = camera.get("ip", "").strip()

        if not ip:
            continue

        ip_map[ip].append(camera)

    conflicts = []

    for ip, devices in ip_map.items():

        if len(devices) > 1:

            conflicts.append(
                {
                    "ip": ip,
                    "devices": devices
                }
            )

    return conflicts
# ==========================================================
# Print Conflicts
# ==========================================================

def print_conflicts(conflicts):

    global sent_conflicts
    global active_conflicts

    current_conflicts = set()

    # ---------------------------------------------
    # No Conflict
    # ---------------------------------------------
    if not conflicts:

        # Send Recovery Mail
        if active_conflicts:

            event_time = datetime.now().strftime(
                "%d %b %Y %I:%M:%S %p"
            )

            send_ip_conflict_resolved_email(
                event_time=event_time
            )

            print("\n" + "=" * 70)
            print("✅ ALL IP CONFLICTS RESOLVED")
            print("=" * 70)

        active_conflicts.clear()
        sent_conflicts.clear()

        return

    # ---------------------------------------------
    # Conflict Found
    # ---------------------------------------------

    print("\n" + "=" * 70)
    print("🚨 IP CONFLICT DETECTED")
    print("=" * 70)

    for conflict in conflicts:

        ip = conflict["ip"]

        devices = conflict["devices"]

        current_conflicts.add(ip)

        print(f"\nDuplicate IP : {ip}")

        print("-" * 70)

        for camera in devices:

            print(
                f"{camera['nvr']} | "
                f"{camera['name']} | "
                f"{camera['status']}"
            )
        # =====================================================
        # Send Email Only Once
        # =====================================================

        if ip not in sent_conflicts:

            event_time = datetime.now().strftime(
                "%d %b %Y %I:%M:%S %p"
            )

            camera_names = []

            nvr_names = []

            for device in devices:

                camera_names.append(device["name"])

                if device["nvr"] not in nvr_names:

                    nvr_names.append(device["nvr"])

            send_ip_conflict_email(

                camera=", ".join(camera_names),

                nvr=", ".join(nvr_names),

                ip=ip,

                event_time=event_time

            )

            sent_conflicts.add(ip)

            print(
                f"\n📧 Alert Email Sent ({ip})"
            )

        else:

            print(
                f"\n⏳ Email Already Sent ({ip})"
            )

        active_conflicts.add(ip)
    # =====================================================
    # Remove Resolved Conflicts
    # =====================================================

    resolved_conflicts = active_conflicts - current_conflicts

    if resolved_conflicts:

        event_time = datetime.now().strftime(
            "%d %b %Y %I:%M:%S %p"
        )

        for resolved_ip in resolved_conflicts:

            print("\n" + "-" * 70)
            print(f"✅ IP Conflict Resolved : {resolved_ip}")
            print("-" * 70)

        # ---------------------------------------------
        # Send Recovery Email (Only Once)
        # ---------------------------------------------

        send_ip_conflict_resolved_email(
            event_time=event_time
        )

        print("📧 Recovery Email Sent")

    # ---------------------------------------------
    # Keep Only Active Conflicts
    # ---------------------------------------------

    active_conflicts.clear()

    active_conflicts.update(current_conflicts)

    # ---------------------------------------------
    # Allow Future Alerts
    # ---------------------------------------------

    sent_conflicts.intersection_update(current_conflicts)

    print("=" * 70)
# ==========================================================
# Utility Functions
# ==========================================================

def has_active_conflicts():
    """
    Returns True if any duplicate IP conflicts
    are currently active.
    """
    return len(active_conflicts) > 0


def get_active_conflicts():
    """
    Returns active conflict IP list.
    """
    return sorted(active_conflicts)


def reset_ip_conflict_state():
    """
    Clears all runtime conflict information.

    Useful for:
        - Restart
        - Manual Reset
        - Testing
    """

    global ip_map
    global sent_conflicts
    global active_conflicts

    ip_map = {}

    sent_conflicts.clear()

    active_conflicts.clear()


# ==========================================================
# Debug Helper
# ==========================================================

def print_runtime_status():

    print("\n" + "=" * 70)
    print("IP CONFLICT RUNTIME STATUS")
    print("=" * 70)

    print("Active Conflicts :", len(active_conflicts))
    print("Sent Alerts      :", len(sent_conflicts))

    if active_conflicts:

        print("\nCurrent Duplicate IPs")

        for ip in sorted(active_conflicts):

            print(f" • {ip}")

    else:

        print("\nNo Active Duplicate IP")

    print("=" * 70)
# ==========================================================
# Conflict Summary
# ==========================================================

def get_conflict_summary():

    summary = []

    for ip, devices in ip_map.items():

        if len(devices) < 2:
            continue

        summary.append(
            {
                "ip": ip,
                "camera_count": len(devices),
                "cameras": [
                    {
                        "camera": d.get("name", ""),
                        "nvr": d.get("nvr", ""),
                        "status": d.get("status", ""),
                    }
                    for d in devices
                ]
            }
        )

    return summary


# ==========================================================
# Dashboard Helper
# ==========================================================

def has_ip_conflicts():

    return len(active_conflicts) > 0


def get_conflict_count():

    return len(active_conflicts)


def get_conflict_ips():

    return sorted(active_conflicts)
# ==========================================================
# Alert History
# ==========================================================

def get_alert_statistics():
    """
    Statistics used by Dashboard Analytics.
    """

    return {
        "active_conflicts": len(active_conflicts),
        "emails_sent": len(sent_conflicts),
        "duplicate_ips": len(ip_map),
    }


# ==========================================================
# Future Enterprise Hooks
# ==========================================================

def export_conflicts():
    """
    Reserved for future PDF / Excel reports.
    """

    return get_conflict_summary()


def get_dashboard_badge():

    if has_ip_conflicts():

        return {
            "status": "warning",
            "title": "Duplicate IP Detected",
            "count": get_conflict_count(),
            "color": "#EF4444"
        }

    return {
        "status": "healthy",
        "title": "No Duplicate IP",
        "count": 0,
        "color": "#22C55E"
    }


# ==========================================================
# Future Alert History Integration
# ==========================================================

def save_conflict_history(conflicts):
    """
    Placeholder.

    Next Version:
        identity_history.json
        ip_conflict_history.json
        analytics.db

    """

    return True
# ==========================================================
# Module Information
# ==========================================================

__version__ = "2.0.0 Enterprise"

__author__ = "VisionGuard AI"

__module__ = "IP Conflict Detection Engine"


# ==========================================================
# Startup Message
# ==========================================================

print(
    "[VisionGuard AI] "
    "Enterprise IP Conflict Engine Loaded"
)


# ==========================================================
# Self Test
# ==========================================================

if __name__ == "__main__":

    print("\n" + "=" * 70)
    print("VisionGuard AI")
    print("Enterprise IP Conflict Detection")
    print("=" * 70)

    print("Version :", __version__)

    print("Active Conflicts :", get_conflict_count())

    print("Conflict IPs :", get_conflict_ips())

    print("\nDashboard Badge")

    print(get_dashboard_badge())

    print("\nStatistics")

    print(get_alert_statistics())

    print("\nConflict Summary")

    print(export_conflicts())

    print("=" * 70)
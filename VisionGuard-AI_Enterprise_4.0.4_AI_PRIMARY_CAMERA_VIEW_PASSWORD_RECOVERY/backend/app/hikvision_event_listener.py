import threading
import time
import xml.etree.ElementTree as ET

import requests
from requests.auth import HTTPDigestAuth

from app.alert_manager import add_alert
from app.config import NVRS
from app.email_service import (
    send_video_loss_email,
    send_video_restored_email,
)

# ==========================================================
# Hikvision Event Listener
# ==========================================================

NAMESPACE = {
    "hik": "http://www.hikvision.com/ver20/XMLSchema"
}

running = False
listener_thread = None

# Cameras currently in Video Loss state
active_video_loss = set()

# Default NVR
NVR = NVRS[1]


# ==========================================================
# Process Event
# ==========================================================

def process_event(xml_data):

    try:

        root = ET.fromstring(xml_data)

        print("\n========== RAW XML START ==========")
        print(xml_data)
        print("========== RAW XML END ==========")

        event_type = root.findtext(
            "hik:eventType",
            "",
            NAMESPACE
        ).lower()

        event_state = root.findtext(
            "hik:eventState",
            "",
            NAMESPACE
        ).lower()

        channel = root.findtext(
            "hik:channelID",
            "0",
            NAMESPACE
        )

        # Some Hikvision models use dynChannelID
        if channel == "0":

            dyn_channel = root.findtext(
                "hik:dynChannelID",
                "",
                NAMESPACE
            )

            if dyn_channel:
                channel = dyn_channel.strip()

        event_time = root.findtext(
            "hik:dateTime",
            "",
            NAMESPACE
        )

        print("\n" + "=" * 60)
        print("EVENT TYPE :", event_type)
        print("EVENT STATE:", event_state)
        print("CHANNEL    :", channel)
        print("TIME       :", event_time)
        print("=" * 60)

        # Ignore all events except Video Loss
        if event_type != "videoloss":
            return

        # Ignore invalid channels
        try:
            channel_no = int(channel)
        except (ValueError, TypeError):
            return

        if channel_no <= 0:
            return

        # ==================================================
        # VIDEO LOSS
        # ==================================================

        if event_state == "active":

            if channel in active_video_loss:
                return

            active_video_loss.add(channel)

            message = (
                f"Camera : {channel}\n"
                f"Status : VIDEO LOSS\n"
                f"Time : {event_time}"
            )

            add_alert(
                alert_type="VIDEO LOSS",
                severity="CRITICAL",
                title=f"Video Loss - Camera {channel}",
                description=message,
            )

            send_video_loss_email(
                camera=f"Camera {channel}",
                nvr=NVR["name"],
                ip=NVR["ip"],
                event_time=event_time,
            )

            print(f"[VIDEO LOSS] Camera {channel}")

        # ==================================================
        # VIDEO RESTORED
        # ==================================================

        elif event_state == "inactive":

            # Restore mail only if video loss was active
            if channel not in active_video_loss:
                return

            active_video_loss.remove(channel)

            send_video_restored_email(
                camera=f"Camera {channel}",
                nvr=NVR["name"],
                ip=NVR["ip"],
                event_time=event_time,
            )

            print(f"[VIDEO RESTORED] Camera {channel}")

    except Exception as e:

        print("=" * 60)
        print("PROCESS EVENT ERROR")
        print("=" * 60)
        print(e)
        print("=" * 60)
        # ==========================================================
# Listen Events
# ==========================================================

def listen_events():

    global running

    print("=" * 60)
    print("Starting Hikvision Event Listener...")
    print(f"NVR : {NVR['name']}")
    print(f"IP  : {NVR['ip']}:{NVR['port']}")
    print("=" * 60)

    url = (
        f"http://{NVR['ip']}:{NVR['port']}"
        "/ISAPI/Event/notification/alertStream"
    )

    while running:

        try:

            response = requests.get(
                url,
                auth=HTTPDigestAuth(
                    NVR["username"],
                    NVR["password"]
                ),
                stream=True,
                timeout=60,
            )

            if response.status_code != 200:

                print(
                    f"Connection Failed : {response.status_code}"
                )

                time.sleep(5)
                continue

            print("Connected to Hikvision Event Stream")

            xml_buffer = ""

            for line in response.iter_lines():

                if not running:
                    break

                if not line:
                    continue

                text = line.decode(
                    "utf-8",
                    errors="ignore"
                )

                xml_buffer += text

                while (
                    "<EventNotificationAlert" in xml_buffer
                    and "</EventNotificationAlert>" in xml_buffer
                ):

                    try:

                        start = xml_buffer.find(
                            "<EventNotificationAlert"
                        )

                        end = (
                            xml_buffer.find(
                                "</EventNotificationAlert>"
                            )
                            + len("</EventNotificationAlert>")
                        )

                        event_xml = xml_buffer[start:end]

                        process_event(event_xml)

                        xml_buffer = xml_buffer[end:]

                    except Exception as ex:

                        print(
                            "XML Parse Error:",
                            ex
                        )

                        xml_buffer = ""

                        break

        except requests.exceptions.RequestException as ex:

            print(
                "Connection Error:",
                ex
            )

            time.sleep(5)

        except Exception as ex:

            print(
                "Listener Error:",
                ex
            )

            time.sleep(5)

    print("Event Listener Stopped")
    # ==========================================================
# Stop Listener
# ==========================================================

def stop_listener():

    global running
    global listener_thread

    running = False

    print("=" * 60)
    print("Stopping Hikvision Event Listener...")
    print("=" * 60)

    if listener_thread is not None:

        listener_thread.join(timeout=5)

        listener_thread = None

    print("Listener Stopped Successfully")


# ==========================================================
# Start Listener
# ==========================================================

def start_listener():

    global running
    global listener_thread

    if running:

        print("Listener Already Running")
        return

    running = True

    listener_thread = threading.Thread(
        target=listen_events,
        daemon=True
    )

    listener_thread.start()

    print("=" * 70)
    print("VisionGuard AI Enterprise Video Monitor Loaded")
    print("=" * 70)


# ==========================================================
# Standalone Test
# ==========================================================

if __name__ == "__main__":

    try:

        start_listener()

        while True:
            time.sleep(1)

    except KeyboardInterrupt:

        print("\nKeyboard Interrupt Received")

        stop_listener()

    except Exception as e:

        print("Fatal Error :", e)

        stop_listener()
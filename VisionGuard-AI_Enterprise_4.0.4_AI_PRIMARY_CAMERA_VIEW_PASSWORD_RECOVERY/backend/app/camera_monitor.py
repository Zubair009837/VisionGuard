# ==========================================================
# VisionGuard AI - Camera Monitoring Engine
# ==========================================================

from datetime import datetime
import time
import requests
import xml.etree.ElementTree as ET

from requests.auth import HTTPDigestAuth

from .config import NVRS

from .email_service import (
    send_offline_email,
    send_recovery_email,
)


# ==========================================================
# CAMERA MONITOR
# ==========================================================

class CameraMonitor:

    def __init__(self):

        # --------------------------------------------------
        # Current camera status
        # --------------------------------------------------

        self.camera_status = {}

        # --------------------------------------------------
        # Last email status
        # --------------------------------------------------

        self.email_sent = {}

        # --------------------------------------------------
        # Recovery tracking
        # --------------------------------------------------

        self.recovery_sent = {}

        # --------------------------------------------------
        # Last check time
        # --------------------------------------------------

        self.last_seen = {}


    # ======================================================
    # GET NVR CHANNELS
    # ======================================================

    def get_nvr_channels(
        self,
        nvr
    ):

        """
        Read camera channels from Hikvision ISAPI.
        """

        url = (
            f"http://{nvr['ip']}:{nvr['port']}"
            "/ISAPI/ContentMgmt/InputProxy/channels/status"
        )

        try:

            response = requests.get(
                url,
                auth=HTTPDigestAuth(
                    nvr["username"],
                    nvr["password"]
                ),
                timeout=10
            )

            if response.status_code == 200:

                return response.text

            print(
                f"[{nvr['name']}] "
                f"HTTP {response.status_code}"
            )

        except Exception as e:

            print(
                f"[{nvr['name']}] {e}"
            )

        return None


    # ======================================================
    # XML PARSER
    # ======================================================

    def parse_channels(
        self,
        xml_data
    ):

        """
        Parse Hikvision channel status XML.
        """

        cameras = []

        if not xml_data:

            return cameras

        try:

            root = ET.fromstring(
                xml_data
            )

            for channel in root.iter():

                tag_name = (
                    channel.tag
                    .split("}")[-1]
                )

                if (
                    tag_name
                    != "InputProxyChannelStatus"
                ):

                    continue

                camera = {

                    "id":
                        "",

                    "name":
                        "",

                    "ip":
                        "",

                    "status":
                        "Offline"

                }

                for child in channel:

                    tag = (
                        child.tag
                        .split("}")[-1]
                    )

                    value = (
                        child.text.strip()
                        if child.text
                        else ""
                    )

                    if tag == "id":

                        camera[
                            "id"
                        ] = value

                    elif tag == "name":

                        camera[
                            "name"
                        ] = value

                    elif tag == "ipAddress":

                        camera[
                            "ip"
                        ] = value

                    elif tag == "online":

                        camera[
                            "status"
                        ] = (
                            "Online"
                            if value.lower()
                            == "true"
                            else "Offline"
                        )

                cameras.append(
                    camera
                )

        except Exception as e:

            print(
                "XML Parse Error :",
                e
            )

        return cameras


    # ======================================================
    # CAMERA SCANNER
    # ======================================================

    def scan_nvr(
        self,
        nvr
    ):

        xml = self.get_nvr_channels(
            nvr
        )

        cameras = self.parse_channels(
            xml
        )

        return cameras


    # ======================================================
    # OFFLINE / RECOVERY DETECTION
    # ======================================================

    def process_cameras(
        self,
        cameras,
        nvr_name
    ):

        """
        Process all cameras from one NVR.
        """

        for camera in cameras:

            key = (
                f"{nvr_name}_"
                f"{camera['id']}"
            )

            current_status = (
                camera["status"]
            )

            previous_status = (
                self.camera_status.get(
                    key,
                    "Unknown"
                )
            )

            # --------------------------------------------------
            # Save latest status
            # --------------------------------------------------

            self.camera_status[
                key
            ] = current_status

            # --------------------------------------------------
            # Save last seen time
            # --------------------------------------------------

            self.last_seen[
                key
            ] = datetime.now()


            # ==================================================
            # CAMERA OFFLINE
            # ==================================================

            if (
                current_status == "Offline"
                and
                previous_status != "Offline"
            ):

                print(
                    f"[OFFLINE] "
                    f"{camera['name']} "
                    f"({camera['ip']})"
                )

                try:

                    send_offline_email(

                        camera=
                            camera["name"],

                        nvr=
                            nvr_name,

                        ip=
                            camera["ip"],

                        event_time=
                            datetime.now().strftime(
                                "%d-%b-%Y %H:%M:%S"
                            )

                    )

                    self.email_sent[
                        key
                    ] = True

                except Exception as e:

                    print(
                        f"[EMAIL ERROR] "
                        f"Offline alert | "
                        f"{camera['name']} | "
                        f"{e}"
                    )

                self.recovery_sent[
                    key
                ] = False


            # ==================================================
            # CAMERA RECOVERY
            # ==================================================

            elif (
                current_status == "Online"
                and
                previous_status == "Offline"
            ):

                print(
                    f"[RECOVERY] "
                    f"{camera['name']}"
                )

                try:

                    send_recovery_email(

                        camera=
                            camera["name"],

                        nvr=
                            nvr_name,

                        ip=
                            camera["ip"],

                        event_time=
                            datetime.now().strftime(
                                "%d-%b-%Y %H:%M:%S"
                            )

                    )

                    self.email_sent[
                        key
                    ] = False

                except Exception as e:

                    print(
                        f"[EMAIL ERROR] "
                        f"Recovery alert | "
                        f"{camera['name']} | "
                        f"{e}"
                    )

                self.recovery_sent[
                    key
                ] = True


    # ======================================================
    # MONITOR ALL NVRS
    # ======================================================

    def scan_all_nvrs(self):

        """
        Scan every configured NVR once.
        """

        for nvr in NVRS:

            try:

                cameras = self.scan_nvr(
                    nvr
                )

                if cameras:

                    self.process_cameras(
                        cameras,
                        nvr["name"]
                    )

            except Exception as e:

                print(
                    f"[{nvr['name']}] "
                    f"Monitor Error : {e}"
                )


    # ======================================================
    # CONTINUOUS MONITORING LOOP
    # ======================================================

    def start(self):

        """
        Start VisionGuard AI Monitoring Engine.
        """

        print("=" * 60)
        print("VISIONGUARD AI ENTERPRISE")
        print("Camera Monitoring Engine Started")
        print("=" * 60)

        while True:

            try:

                self.scan_all_nvrs()

            except Exception as e:

                print(
                    "Monitoring Error :",
                    e
                )

            time.sleep(
                5
            )


# ==========================================================
# SINGLETON MONITOR INSTANCE
# ==========================================================

monitor = CameraMonitor()
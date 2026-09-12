# ==========================================================
# VisionGuard AI Enterprise
# Hikvision API Engine
# Part 1 / 3
# ==========================================================

import logging
import time
import requests
import xml.etree.ElementTree as ET

from requests.auth import HTTPDigestAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================================
# Configuration
# ==========================================================

DEFAULT_TIMEOUT = 15

MAX_RETRIES = 3

LOG = logging.getLogger("VisionGuard.Hikvision")

# ==========================================================
# Hikvision API
# ==========================================================

class HikvisionAPI:

    def __init__(
        self,
        ip,
        username,
        password,
        port=80,
        timeout=DEFAULT_TIMEOUT,
    ):

        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout

        self.base_url = f"http://{ip}:{port}"

        self.session = requests.Session()

        retries = Retry(

            total=MAX_RETRIES,

            backoff_factor=1,

            status_forcelist=[
                500,
                502,
                503,
                504
            ],

            allowed_methods=[
                "GET",
                "POST",
                "PUT",
                "DELETE"
            ]

        )

        adapter = HTTPAdapter(
            max_retries=retries
        )

        self.session.mount(
            "http://",
            adapter
        )

        self.session.auth = HTTPDigestAuth(
            username,
            password
        )

        self.session.headers.update({

            "Content-Type":
                "application/xml",

            "Accept":
                "application/xml"

        })

    # ======================================================
    # Logger
    # ======================================================

    def log(
        self,
        message,
        level="info"
    ):

        text = f"[{self.ip}] {message}"

        if level == "error":

            LOG.error(text)

        elif level == "warning":

            LOG.warning(text)

        else:

            LOG.info(text)

    # ======================================================
    # Generic Request
    # ======================================================

    def request(
        self,
        endpoint,
        method="GET",
        body=None,
        timeout=None,
    ):

        if timeout is None:

            timeout = self.timeout

        url = self.base_url + endpoint

        try:

            response = self.session.request(

                method,

                url,

                data=body,

                timeout=timeout

            )

        except requests.exceptions.Timeout:

            self.log(

                "Connection Timeout",

                "error"

            )

            return None

        except requests.exceptions.ConnectionError:

            self.log(

                "Connection Failed",

                "error"

            )

            return None

        except Exception as exc:

            self.log(

                str(exc),

                "error"

            )

            return None

        if response.status_code not in (200, 201):

            self.log(

                f"HTTP {response.status_code}",

                "warning"

            )

            return None

        return response.text

    # ======================================================
    # XML Parser
    # ======================================================

    def xml(self, xml_text):

        if not xml_text:

            return None

        try:

            return ET.fromstring(xml_text)

        except Exception as exc:

            self.log(

                f"XML Parse Error : {exc}",

                "error"

            )

            return None

    # ======================================================
    # Ping Device
    # ======================================================

    def ping(self):

        xml = self.request(

            "/ISAPI/System/deviceInfo"

        )

        return xml is not None

    # ======================================================
    # Device Information
    # ======================================================

    def get_device_info(self):

        xml = self.request(

            "/ISAPI/System/deviceInfo"

        )

        root = self.xml(xml)

        if root is None:

            return None

        result = {}

        fields = [

            "deviceName",

            "deviceID",

            "model",

            "serialNumber",

            "firmwareVersion",

            "firmwareReleasedDate",

            "macAddress"

        ]

        for field in fields:

            node = root.find(f".//{{*}}{field}")

            if node is not None and node.text:

                result[field] = node.text.strip()

            else:

                result[field] = ""

        return result


print("=" * 70)
print("VisionGuard Hikvision API Loaded")
print("Enterprise Session Ready")
print("Digest Authentication Enabled")
print("Retry Engine Enabled")
print("=" * 70)
# ==========================================================
# XML Helpers
# ==========================================================

def parse_xml(xml_text):

    if not xml_text:
        return None

    try:
        return ET.fromstring(xml_text)
    except Exception as exc:
        log_error(f"XML Parse Error : {exc}")
        return None


def xml_text(node, tag, default=""):

    if node is None:
        return default

    item = node.find(f".//{{*}}{tag}")

    if item is None:
        return default

    if item.text is None:
        return default

    return item.text.strip()


# ==========================================================
# Device Information
# ==========================================================

def get_device_info(nvr):

    xml = hik_request(
        nvr,
        "/ISAPI/System/deviceInfo"
    )

    root = parse_xml(xml)

    if root is None:
        return None

    return {

        "manufacturer":
            xml_text(root, "manufacturer"),

        "model":
            xml_text(root, "model"),

        "firmware":
            xml_text(root, "firmwareVersion"),

        "firmware_build":
            xml_text(root, "firmwareReleasedDate"),

        "serial":
            xml_text(root, "serialNumber"),

        "mac":
            xml_text(root, "macAddress"),

        "device_name":
            xml_text(root, "deviceName"),

        "device_id":
            xml_text(root, "deviceID"),

        "boot_time":
            xml_text(root, "bootTime"),

        "supports_https":
            xml_text(root, "supportHttps"),

    }


# ==========================================================
# Get Camera List
# ==========================================================

def get_camera_list(nvr):

    xml = hik_request(
        nvr,
        "/ISAPI/ContentMgmt/InputProxy/channels"
    )

    root = parse_xml(xml)

    if root is None:
        return []

    cameras = []

    for node in root.findall(".//{*}InputProxyChannel"):

        try:

            camera = {

                "id":
                    int(xml_text(node, "id", "0")),

                "name":
                    xml_text(node, "name"),

                "ip":
                    xml_text(node, "ipAddress"),

                "port":
                    xml_text(node, "managePort"),

                "protocol":
                    xml_text(node, "proxyProtocol"),

                "manufacturer":
                    xml_text(node, "sourceInputPortDescriptor"),

                "online":
                    xml_text(node, "online"),

            }

            cameras.append(camera)

        except Exception:
            pass

    return cameras


# ==========================================================
# Get Single Camera
# ==========================================================

def get_camera(nvr, channel):

    cameras = get_camera_list(nvr)

    for cam in cameras:

        if cam["id"] == channel:
            return cam

    return None


# ==========================================================
# Camera Exists
# ==========================================================

def camera_exists(nvr, channel):

    return get_camera(nvr, channel) is not None


# ==========================================================
# Get Camera Name
# ==========================================================

def get_camera_name(nvr, channel):

    cam = get_camera(nvr, channel)

    if cam is None:
        return None

    return cam["name"]


# ==========================================================
# Get Camera IP
# ==========================================================

def get_camera_ip(nvr, channel):

    cam = get_camera(nvr, channel)

    if cam is None:
        return None

    return cam["ip"]


# ==========================================================
# Get Online Cameras
# ==========================================================

def get_online_cameras(nvr):

    result = []

    for cam in get_camera_list(nvr):

        if str(cam["online"]).lower() == "true":

            result.append(cam)

    return result


# ==========================================================
# Get Offline Cameras
# ==========================================================

def get_offline_cameras(nvr):

    result = []

    for cam in get_camera_list(nvr):

        if str(cam["online"]).lower() != "true":

            result.append(cam)

    return result


# ==========================================================
# Statistics
# ==========================================================

def get_camera_statistics(nvr):

    cams = get_camera_list(nvr)

    online = len(get_online_cameras(nvr))

    offline = len(get_offline_cameras(nvr))

    return {

        "total": len(cams),

        "online": online,

        "offline": offline

    }


print("Device Information APIs Loaded")
print("Camera Information APIs Loaded")
# ==========================================================
# Camera Rename
# ==========================================================

def rename_camera(
    self,
    channel_id: int,
    new_name: str
):

    try:

        endpoint = (
            f"/ISAPI/ContentMgmt/InputProxy/channels/{channel_id}"
        )

        xml = self.get(endpoint)

        if not xml:
            return False

        root = ET.fromstring(xml)

        name_node = root.find(".//{*}name")

        if name_node is None:

            return False

        name_node.text = new_name

        body = ET.tostring(
            root,
            encoding="utf-8"
        )

        response = self.put(
            endpoint,
            body
        )

        return response is not None

    except Exception as exc:

        self.log(
            "Rename Camera",
            exc
        )

        return False


# ==========================================================
# Camera Live Status
# ==========================================================

def get_camera_status(self):

    try:

        xml = self.get(
            "/ISAPI/System/Video/inputs/channels"
        )

        if not xml:
            return []

        root = ET.fromstring(xml)

        result = []

        for channel in root.findall(".//{*}VideoInputChannel"):

            item = {}

            id_node = channel.find("{*}id")
            name_node = channel.find("{*}name")
            enable_node = channel.find("{*}enabled")

            item["id"] = (
                id_node.text
                if id_node is not None
                else ""
            )

            item["name"] = (
                name_node.text
                if name_node is not None
                else ""
            )

            item["enabled"] = (
                enable_node.text == "true"
                if enable_node is not None
                else False
            )

            result.append(item)

        return result

    except Exception as exc:

        self.log(
            "Camera Status",
            exc
        )

        return []


# ==========================================================
# Recording Status
# ==========================================================

def get_recording_status(self):

    try:

        xml = self.get(
            "/ISAPI/ContentMgmt/record/tracks"
        )

        if not xml:

            return []

        root = ET.fromstring(xml)

        tracks = []

        for track in root.findall(".//{*}Track"):

            item = {}

            id_node = track.find("{*}id")
            desc_node = track.find("{*}description")
            enable_node = track.find("{*}enable")

            item["track"] = (
                id_node.text
                if id_node is not None
                else ""
            )

            item["description"] = (
                desc_node.text
                if desc_node is not None
                else ""
            )

            item["enabled"] = (
                enable_node.text == "true"
                if enable_node is not None
                else False
            )

            tracks.append(item)

        return tracks

    except Exception as exc:

        self.log(
            "Recording Status",
            exc
        )

        return []


# ==========================================================
# Update XML Node
# ==========================================================

def update_xml_value(
    self,
    root,
    tag,
    value
):

    node = root.find(
        f".//{{*}}{tag}"
    )

    if node is None:

        return False

    node.text = str(value)

    return True


# ==========================================================
# XML Pretty Print
# ==========================================================

def xml_string(
    self,
    root
):

    return ET.tostring(

        root,

        encoding="utf-8"

    )


# ==========================================================
# Check Camera Exists
# ==========================================================

def camera_exists(
    self,
    channel_id
):

    cameras = self.get_camera_status()

    for camera in cameras:

        if int(camera["id"]) == int(channel_id):

            return True

    return False


# ==========================================================
# Get Camera Name
# ==========================================================

def get_camera_name(
    self,
    channel_id
):

    cameras = self.get_camera_status()

    for camera in cameras:

        if int(camera["id"]) == int(channel_id):

            return camera["name"]

    return None


# ==========================================================
# Enable Camera
# ==========================================================

def enable_camera(
    self,
    channel_id
):

    return self.set_camera_enable(
        channel_id,
        True
    )


# ==========================================================
# Disable Camera
# ==========================================================

def disable_camera(
    self,
    channel_id
):

    return self.set_camera_enable(
        channel_id,
        False
    )


# ==========================================================
# Set Camera Enable
# ==========================================================

def set_camera_enable(
    self,
    channel_id,
    enabled
):

    try:

        endpoint = (
            f"/ISAPI/System/Video/inputs/channels/{channel_id}"
        )

        xml = self.get(endpoint)

        if not xml:
            return False

        root = ET.fromstring(xml)

        self.update_xml_value(
            root,
            "enabled",
            "true" if enabled else "false"
        )

        body = self.xml_string(root)

        return self.put(
            endpoint,
            body
        ) is not None

    except Exception as exc:

        self.log(
            "Enable Camera",
            exc
        )

        return False
    # ==========================================================
# Device Information
# ==========================================================

def get_device_information(self):

    try:

        xml = self.get("/ISAPI/System/deviceInfo")

        if not xml:
            return {}

        root = ET.fromstring(xml)

        data = {}

        fields = [

            "deviceName",
            "deviceID",
            "deviceDescription",
            "deviceLocation",
            "model",
            "serialNumber",
            "firmwareVersion",
            "firmwareReleasedDate",
            "encoderVersion",
            "bootVersion",
            "hardwareVersion"

        ]

        for field in fields:

            node = root.find(f".//{{*}}{field}")

            if node is not None and node.text:

                data[field] = node.text

        return data

    except Exception as exc:

        self.log("Device Information", exc)

        return {}


# ==========================================================
# HDD Information
# ==========================================================

def get_storage_information(self):

    try:

        xml = self.get("/ISAPI/ContentMgmt/Storage")

        if not xml:
            return []

        root = ET.fromstring(xml)

        disks = []

        for disk in root.findall(".//{*}hdd"):

            item = {}

            for tag in [

                "id",
                "capacity",
                "freeSpace",
                "status"

            ]:

                node = disk.find(f"{{*}}{tag}")

                if node is not None:

                    item[tag] = node.text

            disks.append(item)

        return disks

    except Exception as exc:

        self.log("Storage", exc)

        return []


# ==========================================================
# Camera List
# ==========================================================

def get_camera_list(self):

    cameras = self.get_camera_status()

    result = []

    for camera in cameras:

        result.append({

            "id": camera["id"],

            "name": camera["name"],

            "enabled": camera["enabled"]

        })

    return result


# ==========================================================
# Find Camera
# ==========================================================

def find_camera(self, keyword):

    keyword = keyword.lower()

    for camera in self.get_camera_list():

        if keyword in camera["name"].lower():

            return camera

    return None


# ==========================================================
# Total Cameras
# ==========================================================

def total_cameras(self):

    return len(

        self.get_camera_list()

    )


# ==========================================================
# Online Cameras
# ==========================================================

def online_cameras(self):

    count = 0

    for cam in self.get_camera_list():

        if cam["enabled"]:

            count += 1

    return count


# ==========================================================
# Offline Cameras
# ==========================================================

def offline_cameras(self):

    return (

        self.total_cameras()

        -

        self.online_cameras()

    )


# ==========================================================
# Ping Device
# ==========================================================

def ping(self):

    try:

        xml = self.get("/ISAPI/System/status")

        return xml is not None

    except Exception:

        return False


# ==========================================================
# Connection Test
# ==========================================================

def connection_test(self):

    result = {

        "reachable": False,

        "device": None,

        "camera_count": 0

    }

    if not self.ping():

        return result

    result["reachable"] = True

    info = self.get_device_information()

    result["device"] = info.get("model")

    result["camera_count"] = self.total_cameras()

    return result


# ==========================================================
# API Information
# ==========================================================

def version(self):

    return {

        "library":

            "VisionGuard Hikvision API",

        "version":

            "Enterprise v1.0"

    }


# ==========================================================
# Utility
# ==========================================================

def pretty(self, data):

    import json

    return json.dumps(

        data,

        indent=4,

        ensure_ascii=False

    )


# ==========================================================
# Module Ready
# ==========================================================

print("=" * 70)
print("VisionGuard Hikvision Enterprise API Loaded")
print("✓ Digest Authentication")
print("✓ Automatic Retry")
print("✓ Camera Rename")
print("✓ Camera Enable / Disable")
print("✓ Camera Status")
print("✓ Recording Status")
print("✓ Device Information")
print("✓ HDD Information")
print("✓ Camera List")
print("✓ Connection Test")
print("=" * 70)
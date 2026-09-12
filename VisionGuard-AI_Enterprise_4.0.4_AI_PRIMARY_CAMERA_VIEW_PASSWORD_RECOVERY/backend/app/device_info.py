import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPDigestAuth


def fetch_device_info(ip, port, username, password):
    """
    Fetch NVR Device Information
    """

    url = f"http://{ip}:{port}/ISAPI/System/deviceInfo"

    try:

        response = requests.get(
            url,
            auth=HTTPDigestAuth(username, password),
            timeout=10
        )

        response.raise_for_status()

        root = ET.fromstring(response.text)

        def value(tag):
            node = root.find(f".//{{*}}{tag}")
            return node.text.strip() if node is not None and node.text else ""

        return {
            "serial": value("serialNumber"),
            "model": value("model"),
            "firmware": value("firmwareVersion"),
            "device_name": value("deviceName"),
            "mac": value("macAddress")
        }

    except Exception as e:

        print("Device Info Error :", e)

        return {
            "serial": "",
            "model": "",
            "firmware": "",
            "device_name": "",
            "mac": ""
        }
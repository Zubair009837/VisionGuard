# ==========================================================
# VisionGuard AI Enterprise Email Service
# ==========================================================

import os
import html
import smtplib

from pathlib import Path

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.application import MIMEApplication
from email import encoders

from .config import (
    EMAIL_BRAND,
    SMTP_USERNAME as CONFIG_SMTP_USERNAME,
    SMTP_PASSWORD as CONFIG_SMTP_PASSWORD,
    RECEIVER_EMAIL as CONFIG_RECEIVER_EMAIL,
)
from .whatsapp_service import send_whatsapp_event



# ==========================================================
# SMTP CONFIGURATION
# ==========================================================

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


# ==========================================================
# ENVIRONMENT VARIABLES
#
# Windows:
#
# setx VISIONGUARD_SENDER_EMAIL "your@email.com"
# setx VISIONGUARD_APP_PASSWORD "YOUR_APP_PASSWORD"
# setx VISIONGUARD_RECEIVER_EMAIL "receiver@email.com"
#
# IMPORTANT:
# Restart CMD after setx.
# ==========================================================

SENDER_EMAIL = os.getenv(
    "VISIONGUARD_SENDER_EMAIL",
    CONFIG_SMTP_USERNAME
).strip()

APP_PASSWORD = os.getenv(
    "VISIONGUARD_APP_PASSWORD",
    CONFIG_SMTP_PASSWORD
).strip()

RECEIVER_EMAIL = os.getenv(
    "VISIONGUARD_RECEIVER_EMAIL",
    CONFIG_RECEIVER_EMAIL
).strip()


# ==========================================================
# TEMPLATE DIRECTORY
# ==========================================================

TEMPLATE_DIR = (
    Path(__file__).parent /
    "templates"
)


# ==========================================================
# TEMPLATE RENDERER
# ==========================================================

def render_template(
    template_name: str,
    data: dict
):

    template_path = (
        TEMPLATE_DIR /
        template_name
    )

    if not template_path.exists():

        raise FileNotFoundError(
            f"Email template not found: "
            f"{template_path}"
        )

    with open(
        template_path,
        "r",
        encoding="utf-8"
    ) as f:

        html_content = f.read()

    for key, value in data.items():

        html_content = html_content.replace(
            "{{" + key + "}}",
            str(value)
        )

    return html_content


# ==========================================================
# EMAIL LOGGER
# ==========================================================

def log_email_success(subject):

    print()
    print("=" * 70)
    print("✅ EMAIL SENT")
    print("=" * 70)
    print("Subject :", subject)
    print("=" * 70)
    print()


def log_email_failure(
    subject,
    error
):

    print()
    print("=" * 70)
    print("❌ EMAIL FAILED")
    print("=" * 70)
    print("Subject :", subject)
    print("Error   :", error)
    print("=" * 70)
    print()


# ==========================================================
# SMTP VALIDATION
# ==========================================================

def validate_smtp_config():

    valid = True

    if not SENDER_EMAIL:

        print(
            "❌ VISIONGUARD_SENDER_EMAIL "
            "is not configured"
        )

        valid = False

    if not APP_PASSWORD:

        print(
            "❌ VISIONGUARD_APP_PASSWORD "
            "is not configured"
        )

        valid = False

    if not RECEIVER_EMAIL:

        print(
            "❌ VISIONGUARD_RECEIVER_EMAIL "
            "is not configured"
        )

        valid = False

    return valid


# ==========================================================
# GENERIC HTML EMAIL SENDER
# ==========================================================

def send_html_email(
    *,
    subject: str,
    template_name: str,
    camera: str,
    nvr: str,
    ip: str,
    status: str,
    event_time: str,
    attachment_path: str = "",
):

    try:

        if not validate_smtp_config():

            return False

        html_content = render_template(

            template_name,

            {

                "brand":
                    html.escape(
                        str(EMAIL_BRAND)
                    ),

                "camera":
                    html.escape(
                        str(camera)
                    ),

                "nvr":
                    html.escape(
                        str(nvr)
                    ),

                "ip":
                    html.escape(
                        str(ip)
                    ),

                "status":
                    html.escape(
                        str(status)
                    ),

                "issues":
                    html.escape(
                        str(status)
                    ),

                "message":
                    html.escape(
                        str(status)
                    ),

                "time":
                    html.escape(
                        str(event_time)
                    ),

                "event_time":
                    html.escape(
                        str(event_time)
                    )

            }

        )

        msg = MIMEMultipart(
            "alternative"
        )

        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject

        msg.attach(

            MIMEText(
                html_content,
                "html",
                "utf-8"
            )

        )

        # --------------------------------------------------
        # OPTIONAL CAMERA ANGLE EVIDENCE ATTACHMENT
        # --------------------------------------------------
        if attachment_path:
            evidence = Path(str(attachment_path))
            if evidence.exists() and evidence.is_file():
                with open(evidence, "rb") as image_file:
                    part = MIMEBase("image", "jpeg")
                    part.set_payload(image_file.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f'attachment; filename="{evidence.name}"',
                )
                msg.attach(part)
                print("📷 Angle evidence attached:", evidence)

        # --------------------------------------------------
        # DEBUG
        # --------------------------------------------------

        print()
        print(
            "========== EMAIL DEBUG =========="
        )

        print(
            "Subject :",
            subject
        )

        print(
            "Template:",
            template_name
        )

        print(
            "From    :",
            SENDER_EMAIL
        )

        print(
            "To      :",
            RECEIVER_EMAIL
        )

        print(
            "SMTP    :",
            f"{SMTP_SERVER}:{SMTP_PORT}"
        )

        print(
            "================================="
        )

        # --------------------------------------------------
        # SMTP CONNECTION
        # --------------------------------------------------

        with smtplib.SMTP(
            SMTP_SERVER,
            SMTP_PORT,
            timeout=20
        ) as server:

            server.ehlo()

            server.starttls()

            server.ehlo()

            print(
                "✅ TLS OK"
            )

            server.login(
                SENDER_EMAIL,
                APP_PASSWORD
            )

            print(
                "✅ LOGIN SUCCESS"
            )

            server.sendmail(

                SENDER_EMAIL,

                RECEIVER_EMAIL,

                msg.as_string()

            )

            print(
                "✅ MAIL SENT SUCCESSFULLY"
            )

        log_email_success(
            subject
        )

        return True

    except Exception as e:

        log_email_failure(
            subject,
            e
        )

        return False


# ==========================================================
# GENERIC WARNING EMAIL
# ==========================================================

def send_warning_email(
    *,
    subject,
    template_name,
    camera,
    nvr,
    ip,
    message,
    event_time,
    attachment_path="",
):

    send_whatsapp_event(
        subject,
        f"Camera: {camera}\nNVR: {nvr}\nIP: {ip}\nStatus: {message}\nTime: {event_time}",
        "ALERT" if "recover" not in str(subject).lower() else "RECOVERY",
    )

    return send_html_email(

        subject=subject,

        template_name=template_name,

        camera=camera,

        nvr=nvr,

        ip=ip,

        status=message,

        event_time=event_time,

        attachment_path=attachment_path,

    )


# ==========================================================
# CAMERA OFFLINE
# ==========================================================

def send_offline_email(
    camera,
    nvr,
    ip,
    event_time
):

    return send_warning_email(

        subject=(
            f"🔴 [{nvr}] "
            f"Camera Offline - {camera}"
        ),

        template_name="offline.html",

        camera=camera,

        nvr=nvr,

        ip=ip,

        message="Camera is Offline",

        event_time=event_time

    )


# ==========================================================
# CAMERA RECOVERY
# ==========================================================

def send_recovery_email(
    camera,
    nvr,
    ip,
    event_time
):

    return send_warning_email(

        subject=(
            f"🟢 [{nvr}] "
            f"Camera Recovered - {camera}"
        ),

        template_name="recovery.html",

        camera=camera,

        nvr=nvr,

        ip=ip,

        message="Camera Restored Successfully",

        event_time=event_time

    )


# ==========================================================
# NVR OFFLINE EMAIL
# ==========================================================

def send_nvr_offline_email(
    *,
    nvr,
    cameras,
    event_time
):

    try:

        if not validate_smtp_config():

            return False

        cameras = cameras or []

        safe_nvr = html.escape(
            str(nvr)
        )

        safe_time = html.escape(
            str(event_time)
        )

        rows = ""

        for index, camera in enumerate(
            cameras,
            start=1
        ):

            name = html.escape(
                str(
                    camera.get(
                        "name",
                        "-"
                    )
                )
            )

            ip = html.escape(
                str(
                    camera.get(
                        "ip",
                        "-"
                    )
                )
            )

            camera_id = html.escape(
                str(
                    camera.get(
                        "id",
                        "-"
                    )
                )
            )

            rows += f"""
            <tr>
                <td>{index}</td>
                <td>{name}</td>
                <td>{camera_id}</td>
                <td>{ip}</td>
                <td class="offline">
                    OFFLINE
                </td>
            </tr>
            """

        if not rows:

            rows = """
            <tr>
                <td colspan="5">
                    No camera inventory available
                </td>
            </tr>
            """

        subject = (
            f"🚨 [{nvr}] NVR OFFLINE "
            f"- {len(cameras)} Cameras Affected"
        )
        send_whatsapp_event(
            f"{nvr} NVR OFFLINE",
            f"Cameras affected: {len(cameras)}\nEvent time: {event_time}",
            "CRITICAL",
        )

        body = f"""
        <!DOCTYPE html>

        <html>

        <head>

            <meta charset="UTF-8">

            <style>

                body {{
                    font-family:
                        Arial,
                        Helvetica,
                        sans-serif;

                    background:
                        #f4f6f8;

                    padding:
                        20px;
                }}

                .container {{
                    max-width:
                        900px;

                    margin:
                        auto;

                    background:
                        white;

                    border-radius:
                        10px;

                    overflow:
                        hidden;

                    box-shadow:
                        0 2px 10px
                        rgba(0,0,0,0.08);
                }}

                .header {{
                    padding:
                        24px;

                    background:
                        #b91c1c;

                    color:
                        white;
                }}

                .content {{
                    padding:
                        24px;
                }}

                .box {{
                    padding:
                        15px;

                    background:
                        #f8fafc;

                    border:
                        1px solid
                        #e2e8f0;

                    border-radius:
                        8px;

                    margin-bottom:
                        10px;
                }}

                table {{
                    width:
                        100%;

                    border-collapse:
                        collapse;
                }}

                th {{
                    background:
                        #f1f5f9;

                    text-align:
                        left;
                }}

                th,
                td {{
                    padding:
                        10px;

                    border-bottom:
                        1px solid
                        #e5e7eb;

                    font-size:
                        13px;
                }}

                .offline {{
                    color:
                        #b91c1c;

                    font-weight:
                        bold;
                }}

                .footer {{
                    padding:
                        18px 24px;

                    background:
                        #f8fafc;

                    color:
                        #64748b;

                    font-size:
                        12px;
                }}

            </style>

        </head>

        <body>

            <div class="container">

                <div class="header">

                    <h1>
                        🚨 NVR OFFLINE
                    </h1>

                    <p>
                        {html.escape(str(EMAIL_BRAND))}
                    </p>

                </div>

                <div class="content">

                    <div class="box">

                        <strong>
                            NVR:
                        </strong>

                        {safe_nvr}

                    </div>

                    <div class="box">

                        <strong>
                            Status:
                        </strong>

                        <span class="offline">
                            OFFLINE
                        </span>

                    </div>

                    <div class="box">

                        <strong>
                            Affected Cameras:
                        </strong>

                        {len(cameras)}

                    </div>

                    <div class="box">

                        <strong>
                            Detected At:
                        </strong>

                        {safe_time}

                    </div>

                    <h2>
                        Affected Cameras
                    </h2>

                    <table>

                        <thead>

                            <tr>

                                <th>#</th>

                                <th>
                                    Camera
                                </th>

                                <th>
                                    ID
                                </th>

                                <th>
                                    IP
                                </th>

                                <th>
                                    Status
                                </th>

                            </tr>

                        </thead>

                        <tbody>

                            {rows}

                        </tbody>

                    </table>

                </div>

                <div class="footer">

                    VisionGuard AI -
                    Automated NVR Monitoring Alert

                </div>

            </div>

        </body>

        </html>
        """

        msg = MIMEMultipart(
            "alternative"
        )

        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject

        msg.attach(
            MIMEText(
                body,
                "html",
                "utf-8"
            )
        )

        with smtplib.SMTP(
            SMTP_SERVER,
            SMTP_PORT,
            timeout=20
        ) as server:

            server.ehlo()
            server.starttls()
            server.ehlo()

            print("✅ NVR OFFLINE TLS OK")

            server.login(
                SENDER_EMAIL,
                APP_PASSWORD
            )

            print(
                "✅ NVR OFFLINE LOGIN SUCCESS"
            )

            server.sendmail(
                SENDER_EMAIL,
                RECEIVER_EMAIL,
                msg.as_string()
            )

            print(
                "✅ NVR OFFLINE MAIL SENT"
            )

        log_email_success(
            subject
        )

        return True

    except Exception as e:

        log_email_failure(
            "NVR OFFLINE EMAIL",
            e
        )

        return False


# ==========================================================
# NVR RECOVERY EMAIL
# ==========================================================

def send_nvr_recovery_email(
    *,
    nvr,
    cameras,
    event_time
):

    try:

        if not validate_smtp_config():

            return False

        cameras = cameras or []

        safe_nvr = html.escape(
            str(nvr)
        )

        safe_time = html.escape(
            str(event_time)
        )

        rows = ""

        for index, camera in enumerate(
            cameras,
            start=1
        ):

            name = html.escape(
                str(
                    camera.get(
                        "name",
                        "-"
                    )
                )
            )

            ip = html.escape(
                str(
                    camera.get(
                        "ip",
                        "-"
                    )
                )
            )

            rows += f"""
            <tr>
                <td>{index}</td>
                <td>{name}</td>
                <td>{ip}</td>
                <td class="online">
                    ONLINE
                </td>
            </tr>
            """

        if not rows:

            rows = """
            <tr>
                <td colspan="4">
                    No camera inventory available
                </td>
            </tr>
            """

        subject = (
            f"✅ [{nvr}] NVR RECOVERED "
            f"- {len(cameras)} Cameras Restored"
        )
        send_whatsapp_event(
            f"{nvr} NVR RECOVERED",
            f"Cameras restored: {len(cameras)}\nEvent time: {event_time}",
            "RECOVERY",
        )

        body = f"""
        <!DOCTYPE html>

        <html>

        <head>

            <meta charset="UTF-8">

            <style>

                body {{
                    font-family:
                        Arial,
                        Helvetica,
                        sans-serif;

                    background:
                        #f4f6f8;

                    padding:
                        20px;
                }}

                .container {{
                    max-width:
                        900px;

                    margin:
                        auto;

                    background:
                        white;

                    border-radius:
                        10px;

                    overflow:
                        hidden;

                    box-shadow:
                        0 2px 10px
                        rgba(0,0,0,0.08);
                }}

                .header {{
                    padding:
                        24px;

                    background:
                        #15803d;

                    color:
                        white;
                }}

                .content {{
                    padding:
                        24px;
                }}

                .box {{
                    padding:
                        15px;

                    background:
                        #f8fafc;

                    border:
                        1px solid
                        #e2e8f0;

                    border-radius:
                        8px;

                    margin-bottom:
                        10px;
                }}

                table {{
                    width:
                        100%;

                    border-collapse:
                        collapse;
                }}

                th {{
                    background:
                        #f1f5f9;

                    text-align:
                        left;
                }}

                th,
                td {{
                    padding:
                        10px;

                    border-bottom:
                        1px solid
                        #e5e7eb;

                    font-size:
                        13px;
                }}

                .online {{
                    color:
                        #15803d;

                    font-weight:
                        bold;
                }}

                .footer {{
                    padding:
                        18px 24px;

                    background:
                        #f8fafc;

                    color:
                        #64748b;

                    font-size:
                        12px;
                }}

            </style>

        </head>

        <body>

            <div class="container">

                <div class="header">

                    <h1>
                        ✅ NVR RECOVERED
                    </h1>

                    <p>
                        {html.escape(str(EMAIL_BRAND))}
                    </p>

                </div>

                <div class="content">

                    <div class="box">

                        <strong>
                            NVR:
                        </strong>

                        {safe_nvr}

                    </div>

                    <div class="box">

                        <strong>
                            Status:
                        </strong>

                        <span class="online">
                            ONLINE
                        </span>

                    </div>

                    <div class="box">

                        <strong>
                            Cameras Restored:
                        </strong>

                        {len(cameras)}

                    </div>

                    <div class="box">

                        <strong>
                            Recovery Time:
                        </strong>

                        {safe_time}

                    </div>

                    <h2>
                        Restored Cameras
                    </h2>

                    <table>

                        <thead>

                            <tr>

                                <th>#</th>

                                <th>
                                    Camera
                                </th>

                                <th>
                                    IP
                                </th>

                                <th>
                                    Status
                                </th>

                            </tr>

                        </thead>

                        <tbody>

                            {rows}

                        </tbody>

                    </table>

                </div>

                <div class="footer">

                    VisionGuard AI -
                    Automated NVR Monitoring Recovery

                </div>

            </div>

        </body>

        </html>
        """

        msg = MIMEMultipart(
            "alternative"
        )

        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject

        msg.attach(
            MIMEText(
                body,
                "html",
                "utf-8"
            )
        )

        with smtplib.SMTP(
            SMTP_SERVER,
            SMTP_PORT,
            timeout=20
        ) as server:

            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(
                SENDER_EMAIL,
                APP_PASSWORD
            )

            server.sendmail(
                SENDER_EMAIL,
                RECEIVER_EMAIL,
                msg.as_string()
            )

        log_email_success(
            subject
        )

        return True

    except Exception as e:

        log_email_failure(
            "NVR RECOVERY EMAIL",
            e
        )

        return False


# ==========================================================
# DEVICE IDENTITY EMAIL
# ==========================================================

def send_identity_email(
    camera,
    nvr,
    ip,
    issues,
    event_time
):

    return send_warning_email(

        subject=(
            f"🚨 [{nvr}] "
            f"Device Identity Changed - {camera}"
        ),

        template_name="identity.html",

        camera=camera,

        nvr=nvr,

        ip=ip,

        message=issues,

        event_time=event_time

    )


# ==========================================================
# IP CONFLICT EMAIL
# ==========================================================

def send_ip_conflict_email(
    camera,
    nvr,
    ip,
    event_time
):

    return send_warning_email(

        subject=(
            f"⚠️ [{nvr}] "
            f"Duplicate IP Detected"
        ),

        template_name="ip_conflict.html",

        camera=camera,

        nvr=nvr,

        ip=ip,

        message="Duplicate IP Detected",

        event_time=event_time

    )


# ==========================================================
# IP CONFLICT RESOLVED
# ==========================================================

def send_ip_conflict_resolved_email(
    event_time
):

    return send_warning_email(

        subject=(
            "✅ IP Conflict Resolved"
        ),

        template_name=(
            "ip_conflict_resolved.html"
        ),

        camera=(
            "All Monitored Cameras"
        ),

        nvr=(
            "All Connected NVRs"
        ),

        ip="-",

        message=(
            "No Duplicate IP Detected"
        ),

        event_time=event_time

    )


# ==========================================================
# VIDEO LOSS
# ==========================================================

def send_video_loss_email(
    camera,
    nvr,
    ip,
    event_time
):

    return send_warning_email(

        subject=(
            f"🎥 [{nvr}] "
            f"Video Loss - {camera}"
        ),

        template_name="video_loss.html",

        camera=camera,

        nvr=nvr,

        ip=ip,

        message="Video Stream Lost",

        event_time=event_time

    )


# ==========================================================
# VIDEO RESTORED
# ==========================================================

def send_video_restored_email(
    camera,
    nvr,
    ip,
    event_time
):

    return send_warning_email(

        subject=(
            f"🟢 [{nvr}] "
            f"Video Restored - {camera}"
        ),

        template_name="video_restored.html",

        camera=camera,

        nvr=nvr,

        ip=ip,

        message="Video Stream Restored",

        event_time=event_time

    )


# ==========================================================
# RECORDING LOSS
# ==========================================================

def send_recording_loss_email(
    camera,
    nvr,
    ip,
    loss_from,
    loss_to,
    duration,
    reason="Recording gap verified by Hikvision search."
):

    print(
        "######## "
        "send_recording_loss_email "
        "CALLED ########"
    )

    return send_warning_email(

        subject=(
            f"⛔ [{nvr}] "
            f"Recording Loss - {camera}"
        ),

        template_name="video_loss.html",

        camera=camera,

        nvr=nvr,

        ip=ip,

        message=(

            f"Recording Interrupted\n\n"

            f"Missing From : {loss_from}\n"

            f"Missing To   : {loss_to}\n"

            f"Duration     : {duration}\n\n"
            f"Reason       : {reason}"

        ),

        event_time=loss_from

    )


# ==========================================================
# RECORDING RECOVERY
# ==========================================================

def send_recording_recovery_email(
    camera,
    nvr,
    ip,
    loss_from,
    loss_to,
    restored_at,
    duration
):

    return send_warning_email(

        subject=(
            f"✅ [{nvr}] "
            f"Recording Restored - {camera}"
        ),

        template_name="video_restored.html",

        camera=camera,

        nvr=nvr,

        ip=ip,

        message=(

            f"Recording Restored\n\n"

            f"Loss From : {loss_from}\n"

            f"Loss To   : {loss_to}\n"

            f"Recovered : {restored_at}\n"

            f"Duration  : {duration}"

        ),

        event_time=restored_at

    )


# ==========================================================
# PTZ POSITION CHANGE
# ==========================================================

def send_ptz_position_changed_email(
    camera,
    nvr,
    ip,
    channel,
    change,
    event_time,
):

    return send_warning_email(

        subject=(
            f"🚨 [{nvr}] "
            f"PTZ Camera Position Changed - {camera}"
        ),

        template_name=(
            "ptz_position_changed.html"
        ),

        camera=camera,

        nvr=nvr,

        ip=ip,

        message=(
            f"Channel {channel}: {change}"
        ),

        event_time=event_time,

    )


# ==========================================================
# CAMERA ANGLE / VIEWPOINT CHANGE
# ==========================================================

def send_camera_angle_changed_email(
    camera,
    nvr,
    ip,
    channel,
    score,
    details,
    event_time,
):

    print()
    print("=" * 70)
    print("🚨 CAMERA ANGLE CHANGE EMAIL TRIGGERED")
    print("=" * 70)

    print("Camera  :", camera)
    print("NVR     :", nvr)
    print("IP      :", ip)
    print("Channel :", channel)
    print("Score   :", score)
    print("Details :", details)
    print("Time    :", event_time)

    print("=" * 70)

    evidence_path = ""
    marker = "EVIDENCE_FILE="
    if marker in str(details):
        evidence_path = str(details).split(marker, 1)[1].split(" | ", 1)[0].strip()

    return send_warning_email(

        subject=(
            f"🚨 [{nvr}] "
            f"Camera Angle Changed - {camera}"
        ),

        template_name=(
            "camera_angle_changed.html"
        ),

        camera=camera,

        nvr=nvr,

        ip=ip,

        message=(
            f"Channel {channel}: "
            f"Visual viewpoint changed | "
            f"Score {score} | "
            f"{details}"
        ),

        event_time=event_time,

        attachment_path=evidence_path,

    )


# ==========================================================
# CAMERA ANGLE RESTORED
# ==========================================================

def send_camera_angle_restored_email(
    camera,
    nvr,
    ip,
    channel,
    event_time,
):

    print()
    print("=" * 70)
    print("🟢 CAMERA ANGLE RESTORED EMAIL TRIGGERED")
    print("=" * 70)

    print("Camera  :", camera)
    print("NVR     :", nvr)
    print("IP      :", ip)
    print("Channel :", channel)
    print("Time    :", event_time)

    print("=" * 70)

    return send_warning_email(

        subject=(
            f"🟢 [{nvr}] "
            f"Camera Angle Restored - {camera}"
        ),

        template_name=(
            "camera_angle_restored.html"
        ),

        camera=camera,

        nvr=nvr,

        ip=ip,

        message=(
            f"Channel {channel}: "
            f"Camera viewpoint returned "
            f"to the stored baseline."
        ),

        event_time=event_time,

    )


# ==========================================================
# MODULE LOAD
# ==========================================================

print(
    "✅ VisionGuard AI Enterprise Email Service Loaded"
)

print(
    "📧 SMTP Server :",
    f"{SMTP_SERVER}:{SMTP_PORT}"
)

print(
    "📧 Sender      :",
    SENDER_EMAIL if SENDER_EMAIL else "NOT CONFIGURED"
)

print(
    "📧 Receiver    :",
    RECEIVER_EMAIL if RECEIVER_EMAIL else "NOT CONFIGURED"
)

print(
    "📧 App Password:",
    "CONFIGURED" if APP_PASSWORD else "NOT CONFIGURED"
)

# ==========================================================
# CAMERA NVR MIGRATION
# ==========================================================

def send_camera_migration_email(
    camera, ip, old_nvr, old_channel, new_nvr, new_channel, event_time
):
    return send_warning_email(
        subject=f"🚨 Camera NVR Movement - {camera}",
        template_name="camera_migration.html",
        camera=camera,
        nvr=f"{old_nvr} → {new_nvr}",
        ip=ip,
        message=(
            f"Previous: {old_nvr} CH-{old_channel}\n"
            f"Current: {new_nvr} CH-{new_channel}"
        ),
        event_time=event_time,
    )

# ==========================================================
# NVR HEALTH / SYSTEM HEALTH EMAIL
# ==========================================================

def send_nvr_health_email(
    *,
    nvr,
    ip,
    severity,
    title,
    description,
    metric="",
    threshold="",
    event_time="",
):
    """Send a professional email for CPU, memory, temperature,
    storage, HDD, NVR reachability and recovery events."""
    try:
        if not validate_smtp_config():
            return False

        severity_safe = html.escape(str(severity))
        title_safe = html.escape(str(title))
        nvr_safe = html.escape(str(nvr))
        ip_safe = html.escape(str(ip))
        desc_safe = html.escape(str(description)).replace("\n", "<br>")
        metric_safe = html.escape(str(metric))
        threshold_safe = html.escape(str(threshold))
        time_safe = html.escape(str(event_time))
        brand_safe = html.escape(str(EMAIL_BRAND))

        subject_prefix = "🚨" if str(severity).upper() in {"CRITICAL", "WARNING"} else "✅"
        subject = f"{subject_prefix} [{nvr}] {title}"

        body = f"""
<!doctype html>
<html>
<head><meta charset="UTF-8">
<style>
body{{margin:0;padding:24px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#0f172a}}
.card{{max-width:760px;margin:auto;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 4px 18px rgba(15,23,42,.10)}}
.head{{padding:24px;background:#b91c1c;color:#fff}}
.head.info{{background:#15803d}}
.head h1{{margin:0 0 7px;font-size:23px}}
.head p{{margin:0;opacity:.92}}
.content{{padding:24px}}
.badge{{display:inline-block;padding:7px 12px;border-radius:999px;background:#fee2e2;color:#991b1b;font-weight:700;font-size:12px}}
.info .badge{{background:#dcfce7;color:#166534}}
table{{width:100%;border-collapse:collapse;margin-top:18px}}
th,td{{padding:12px;border-bottom:1px solid #e5e7eb;text-align:left;font-size:14px;vertical-align:top}}
th{{width:28%;background:#f8fafc}}
.reason{{margin-top:20px;padding:16px;background:#fff7ed;border-left:4px solid #f97316;border-radius:8px}}
.footer{{padding:18px 24px;background:#f8fafc;color:#64748b;font-size:12px}}
</style></head>
<body>
<div class="card">
<div class="head {'info' if str(severity).upper() == 'INFO' else ''}">
<h1>{subject_prefix} {title_safe}</h1>
<p>{brand_safe}</p>
</div>
<div class="content">
<span class="badge">{severity_safe}</span>
<table>
<tr><th>NVR</th><td>{nvr_safe}</td></tr>
<tr><th>IP Address</th><td>{ip_safe}</td></tr>
<tr><th>Detection Time</th><td>{time_safe}</td></tr>
<tr><th>Metric</th><td>{metric_safe or '—'}</td></tr>
<tr><th>Threshold</th><td>{threshold_safe or '—'}</td></tr>
</table>
<div class="reason"><strong>Reason / Details</strong><br><br>{desc_safe}</div>
</div>
<div class="footer">This is an automated alert generated by VisionGuard AI Enterprise Monitoring Platform.</div>
</div>
</body></html>
"""

        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

        log_email_success(subject)
        return True
    except Exception as exc:
        log_email_failure(subject if 'subject' in locals() else title, exc)
        return False


# ==========================================================
# DAILY 10:00 AM CCTV HEALTH REPORT
# ==========================================================


def send_daily_health_report_email(
    *,
    all_normal: bool,
    cameras_online: int,
    cameras_total: int,
    nvrs_online: int,
    nvrs_total: int,
    recording_ok: bool,
    storage_ok: bool,
    ip_conflict_count: int = 0,
    ip_conflict_ips=None,
    recording_loss_count: int = 0,
    recording_losses=None,
    time_results=None,
    time_drift_count: int = 0,
    time_check_failed_count: int = 0,
    angle_enabled: bool = False,
    angle_changed: int = 0,
    issues=None,
    report_time: str = "",
):
    """Professional daily 10:00 AM CCTV verification email."""

    try:
        if not validate_smtp_config():
            return False

        ip_conflict_ips = ip_conflict_ips or []
        recording_losses = recording_losses or []
        time_results = time_results or []
        issues = [
            str(x).strip()
            for x in (issues or [])
            if str(x).strip()
        ]

        cameras_offline = max(
            0,
            int(cameras_total) - int(cameras_online),
        )
        nvrs_offline = max(
            0,
            int(nvrs_total) - int(nvrs_online),
        )

        # ----------------------------------------------------------
        # STATUS HELPERS
        # ----------------------------------------------------------
        def esc(value):
            return html.escape(str(value or ""))

        def status_text(ok, good="NORMAL", bad="ATTENTION REQUIRED"):
            return good if ok else bad

        overall_title = (
            "🟢 ALL SYSTEMS NORMAL"
            if all_normal
            else "🟠 ATTENTION REQUIRED"
        )

        overall_bg = "#ecfdf5" if all_normal else "#fff7ed"
        overall_border = "#bbf7d0" if all_normal else "#fed7aa"
        overall_color = "#166534" if all_normal else "#b45309"

        # ----------------------------------------------------------
        # NVR TIME TABLE
        # ----------------------------------------------------------
        time_rows = ""

        for item in time_results:
            nvr_name = esc(
                item.get("nvr", "Unknown NVR")
            )
            ip = esc(item.get("ip", ""))
            port = esc(
                item.get(
                    "port",
                    item.get("http_port", ""),
                )
            )

            error = str(
                item.get("error", "") or ""
            ).strip()

            drift = item.get("time_drift")
            difference = item.get(
                "difference_seconds"
            )

            nvr_time = str(
                item.get("nvr_time", "") or ""
            ).strip()

            if error or drift is None:
                status = "CHECK FAILED"
                status_color = "#b45309"
                diff_text = "—"

                if error:
                    detail = error
                elif nvr_time:
                    detail = (
                        "NVR time was returned but could not be "
                        "validated."
                    )
                else:
                    detail = (
                        "NVR clock could not be read from the "
                        "configured HTTP port."
                    )

            elif drift:
                status = "TIME DRIFT"
                status_color = "#b91c1c"
                diff_text = (
                    f"{float(difference):+.1f} sec"
                    if difference is not None
                    else "—"
                )
                detail = (
                    f"NVR time: {nvr_time}"
                    if nvr_time
                    else "Clock difference exceeds the configured tolerance."
                )

            else:
                status = "NORMAL"
                status_color = "#166534"
                diff_text = (
                    f"{float(difference):.1f} sec"
                    if difference is not None
                    else "0 sec"
                )
                detail = (
                    f"NVR time: {nvr_time}"
                    if nvr_time
                    else "Clock is within the configured tolerance."
                )

            time_rows += f"""
            <tr>
                <td style="padding:10px 8px;border-bottom:1px solid #eef2f7;">
                    {nvr_name}
                </td>
                <td style="padding:10px 8px;border-bottom:1px solid #eef2f7;">
                    {ip}
                </td>
                <td style="padding:10px 8px;border-bottom:1px solid #eef2f7;text-align:center;">
                    {port}
                </td>
                <td style="padding:10px 8px;border-bottom:1px solid #eef2f7;font-weight:800;color:{status_color};">
                    {status}
                </td>
                <td style="padding:10px 8px;border-bottom:1px solid #eef2f7;text-align:center;">
                    {esc(diff_text)}
                </td>
                <td style="padding:10px 8px;border-bottom:1px solid #eef2f7;color:#475569;">
                    {esc(detail)}
                </td>
            </tr>
            """

        # ----------------------------------------------------------
        # RECORDING DETAILS
        # ----------------------------------------------------------
        recording_details = ""

        if recording_losses:
            names = []

            for item in recording_losses[:50]:
                if isinstance(item, dict):
                    names.append(
                        str(
                            item.get("camera")
                            or item.get("camera_name")
                            or item.get("name")
                            or "Unknown Camera"
                        )
                    )
                else:
                    names.append(str(item))

            recording_details = f"""
            <div style="margin-top:10px;color:#991b1b;font-size:12px;">
                <strong>Affected camera(s):</strong>
                {esc(", ".join(names))}
            </div>
            """

        # ----------------------------------------------------------
        # IP DETAILS
        # ----------------------------------------------------------
        ip_details = ""

        if ip_conflict_ips:
            ip_details = f"""
            <div style="margin-top:10px;color:#991b1b;font-size:12px;">
                <strong>Affected IP(s):</strong>
                {esc(", ".join(map(str, ip_conflict_ips)))}
            </div>
            """

        # ----------------------------------------------------------
        # ISSUE BLOCK
        # ----------------------------------------------------------
        issue_block = ""

        if issues:
            issue_items = "".join(
                f"""
                <li style="margin:6px 0;color:#7f1d1d;">
                    {esc(item)}
                </li>
                """
                for item in issues
            )

            issue_block = f"""
            <div style="
                background:#fff7ed;
                border:1px solid #fed7aa;
                border-radius:12px;
                padding:16px 18px;
                margin-bottom:20px;
            ">
                <div style="
                    font-size:14px;
                    font-weight:800;
                    color:#9a3412;
                    margin-bottom:7px;
                ">
                    Issues Detected
                </div>
                <ul style="
                    margin:0;
                    padding-left:20px;
                ">
                    {issue_items}
                </ul>
            </div>
            """

        # ----------------------------------------------------------
        # INDIVIDUAL STATUS VALUES
        # ----------------------------------------------------------
        camera_status = (
            "NORMAL"
            if cameras_offline == 0
            else f"{cameras_offline} Offline"
        )

        nvr_status = (
            "NORMAL"
            if nvrs_offline == 0
            else f"{nvrs_offline} Offline"
        )

        ip_status = (
            "NORMAL - 0 Conflicts"
            if ip_conflict_count == 0
            else f"ATTENTION - {ip_conflict_count} Conflict(s)"
        )

        recording_status = (
            "NORMAL - No Recording Loss"
            if recording_ok
            else f"ATTENTION - {recording_loss_count} Loss(es)"
        )

        storage_status = (
            "NORMAL"
            if storage_ok
            else "ATTENTION REQUIRED"
        )

        if time_drift_count == 0 and time_check_failed_count == 0:
            time_status = "NORMAL - All NVR clocks verified"
        else:
            time_status = (
                f"{time_drift_count} Time Drift + "
                f"{time_check_failed_count} Check Failed"
            )

        if not angle_enabled:
            angle_status = "Monitor Disabled"
        elif angle_changed == 0:
            angle_status = "NORMAL - No Angle Change"
        else:
            angle_status = (
                f"ATTENTION - {angle_changed} angle change(s)"
            )

        # ----------------------------------------------------------
        # HTML EMAIL
        # ----------------------------------------------------------
        html_content = f"""
        <!doctype html>
        <html>
        <body style="
            margin:0;
            padding:28px;
            background:#f4f7fb;
            font-family:Segoe UI,Arial,sans-serif;
            color:#0f172a;
        ">

        <div style="
            max-width:900px;
            margin:auto;
            background:#ffffff;
            border:1px solid #e2e8f0;
            border-radius:16px;
            overflow:hidden;
        ">

            <!-- HEADER -->
            <div style="
                background:linear-gradient(135deg,#0f3b92,#2563eb);
                color:#ffffff;
                padding:24px 26px;
            ">
                <div style="
                    font-size:23px;
                    font-weight:800;
                ">
                    VisionGuard AI
                </div>

                <div style="
                    margin-top:5px;
                    color:#dbeafe;
                    font-size:13px;
                ">
                    TATA 1MG Security Operations Center
                </div>

                <div style="
                    margin-top:4px;
                    color:#dbeafe;
                    font-size:12px;
                ">
                    Daily CCTV Health Verification Report
                </div>
            </div>

            <div style="padding:25px 26px;">

                <!-- OVERALL -->
                <div style="
                    background:{overall_bg};
                    border:1px solid {overall_border};
                    border-radius:12px;
                    padding:17px 19px;
                    margin-bottom:20px;
                ">
                    <div style="
                        font-size:19px;
                        font-weight:800;
                        color:{overall_color};
                    ">
                        {overall_title}
                    </div>

                    <div style="
                        margin-top:6px;
                        color:#475569;
                        font-size:13px;
                    ">
                        {
                            "All configured CCTV health checks were successfully verified."
                            if all_normal
                            else
                            "One or more CCTV health checks require attention."
                        }
                    </div>
                </div>

                {issue_block}

                <!-- SUMMARY -->
                <div style="
                    font-size:16px;
                    font-weight:800;
                    margin-bottom:10px;
                ">
                    Complete System Summary
                </div>

                <table style="
                    width:100%;
                    border-collapse:collapse;
                    font-size:13px;
                    margin-bottom:22px;
                ">

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            Total Cameras
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;">
                            {cameras_total}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            Cameras Online
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;color:#166534;">
                            {cameras_online}/{cameras_total}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            Cameras Offline
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;">
                            {cameras_offline}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            NVRs Online
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;color:{'#166534' if nvrs_online == nvrs_total else '#b45309'};">
                            {nvrs_online}/{nvrs_total}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            NVRs Offline
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;">
                            {nvrs_offline}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            IP Conflict Check
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;">
                            {esc(ip_status)}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            Recording Check
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;">
                            {esc(recording_status)}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            Storage / HDD
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;">
                            {esc(storage_status)}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;color:#64748b;">
                            NVR Clock / Time
                        </td>
                        <td style="padding:9px 8px;border-bottom:1px solid #eef2f7;text-align:right;font-weight:800;">
                            {esc(time_status)}
                        </td>
                    </tr>

                    <tr>
                        <td style="padding:9px 8px;color:#64748b;">
                            Camera Angle
                        </td>
                        <td style="padding:9px 8px;text-align:right;font-weight:800;">
                            {esc(angle_status)}
                        </td>
                    </tr>

                </table>

                {ip_details}

                {recording_details}

                <!-- CLOCK TABLE -->
                <div style="
                    font-size:16px;
                    font-weight:800;
                    margin:24px 0 10px;
                ">
                    NVR Clock / Time Verification
                </div>

                <div style="
                    overflow-x:auto;
                    border:1px solid #e2e8f0;
                    border-radius:10px;
                ">
                    <table style="
                        width:100%;
                        border-collapse:collapse;
                        font-size:12px;
                    ">
                        <thead>
                            <tr style="background:#f8fafc;">
                                <th style="padding:10px 8px;text-align:left;">NVR</th>
                                <th style="padding:10px 8px;text-align:left;">IP</th>
                                <th style="padding:10px 8px;text-align:center;">HTTP Port</th>
                                <th style="padding:10px 8px;text-align:left;">Status</th>
                                <th style="padding:10px 8px;text-align:center;">Difference</th>
                                <th style="padding:10px 8px;text-align:left;">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {time_rows}
                        </tbody>
                    </table>
                </div>

                <!-- FOOTER -->
                <div style="
                    margin-top:22px;
                    padding-top:14px;
                    border-top:1px solid #eef2f7;
                    font-size:11px;
                    color:#94a3b8;
                    line-height:1.6;
                ">
                    Automated VisionGuard AI report generated at
                    {esc(report_time)}.<br>
                    NVR clock verification is independent of NVR
                    connectivity status. A clock-check failure does not
                    automatically classify the NVR as offline.
                </div>

            </div>
        </div>
        </body>
        </html>
        """

        subject = (
            "VisionGuard – Daily CCTV Health Report – All Systems Normal"
            if all_normal
            else
            "VisionGuard – Daily CCTV Health Report – Attention Required"
        )

        msg = MIMEMultipart("alternative")
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject

        msg.attach(
            MIMEText(
                html_content,
                "html",
                "utf-8",
            )
        )

        with smtplib.SMTP(
            SMTP_SERVER,
            SMTP_PORT,
            timeout=20,
        ) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(
                SENDER_EMAIL,
                APP_PASSWORD,
            )
            server.sendmail(
                SENDER_EMAIL,
                RECEIVER_EMAIL,
                msg.as_string(),
            )

        log_email_success(subject)
        return True

    except Exception as exc:
        log_email_failure(
            "VisionGuard – Daily CCTV Health Report",
            exc,
        )
        print(
            f"[DAILY REPORT EMAIL ERROR] {exc}"
        )
        return False


# ==========================================================
# APPLICATION PASSWORD RESET EMAIL
# ==========================================================

def send_app_password_reset_email(
    *,
    recipient: str,
    username: str,
    reset_url: str,
    expires_minutes: int = 15,
):
    """Send a one-time application password reset link."""
    if not SENDER_EMAIL or not APP_PASSWORD:
        raise RuntimeError(
            "VisionGuard SMTP is not configured. Set "
            "VISIONGUARD_SENDER_EMAIL and VISIONGUARD_APP_PASSWORD."
        )

    safe_user = html.escape(str(username))
    safe_url = html.escape(str(reset_url), quote=True)

    message = MIMEMultipart("alternative")
    message["Subject"] = "VisionGuard AI - Administrator Password Reset"
    message["From"] = SENDER_EMAIL
    message["To"] = recipient

    html_content = f"""
    <html>
      <body style="margin:0;background:#071426;font-family:Arial,sans-serif;color:#dbeafe;padding:28px;">
        <div style="max-width:620px;margin:auto;background:#0b1d34;border:1px solid #1e4770;border-radius:12px;padding:28px;">
          <div style="color:#45e6a6;font-size:12px;font-weight:700;letter-spacing:2px;">VISIONGUARD AI</div>
          <h2 style="color:#ffffff;margin:10px 0 8px;">Administrator Password Reset</h2>
          <p style="color:#9fb6d1;line-height:1.6;">
            A password reset was requested for the VisionGuard application account
            <b style="color:#ffffff;">{safe_user}</b>.
          </p>
          <p style="margin:24px 0;">
            <a href="{safe_url}" style="display:inline-block;padding:12px 18px;background:#1769e0;color:#ffffff;text-decoration:none;border-radius:7px;font-weight:700;">
              RESET PASSWORD
            </a>
          </p>
          <p style="color:#7f96b0;font-size:12px;line-height:1.6;">
            This link is valid for {expires_minutes} minutes and can be used only once.
            If you did not request this reset, no action is required.
          </p>
          <div style="margin-top:24px;padding-top:16px;border-top:1px solid #1c3653;color:#647d9a;font-size:11px;">
            VisionGuard AI Enterprise Monitoring Platform
          </div>
        </div>
      </body>
    </html>
    """
    message.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, [recipient], message.as_string())

# ==========================================================
# PASSWORD RECOVERY OTP
# ==========================================================

def send_password_recovery_otp(
    *,
    recipient: str,
    nvr_name: str,
    otp: str,
    expires_minutes: int = 10,
):
    """Send a VisionGuard recovery authorization code.

    This is an application-level authorization code. It is not a
    Hikvision reset code and must never be represented as one.
    """
    if not SENDER_EMAIL or not APP_PASSWORD:
        raise RuntimeError(
            "VisionGuard SMTP is not configured. Set "
            "VISIONGUARD_SENDER_EMAIL and VISIONGUARD_APP_PASSWORD."
        )

    message = MIMEMultipart("alternative")
    message["Subject"] = f"VisionGuard NVR Password Recovery OTP - {nvr_name}"
    message["From"] = SENDER_EMAIL
    message["To"] = recipient

    html_content = f"""
    <html>
      <body style="font-family:Arial,sans-serif;">
        <h2>VisionGuard AI - NVR Password Recovery</h2>
        <p><b>NVR:</b> {html.escape(nvr_name)}</p>
        <p>Your VisionGuard recovery verification code is:</p>
        <h1 style="letter-spacing:6px;">{html.escape(otp)}</h1>
        <p>This code expires in {expires_minutes} minutes.</p>
        <p>
          This is an application authorization code. It does not bypass
          Hikvision authentication or replace an official Hikvision
          recovery code.
        </p>
      </body>
    </html>
    """
    message.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, [recipient], message.as_string())

# ==========================================================
# HIKVISION OFFICIAL RECOVERY QR RELAY
# ==========================================================

def send_hikvision_recovery_qr(*, attachment_path: str, nvr_name: str, nvr_ip: str):
    """Relay the exact user-exported Hikvision recovery QR without modifying it.

    Hikvision's recovery service must be able to recognize the attachment as the
    original QR export. Preserve the original bytes and filename and send the
    correct MIME type instead of a generic application/octet-stream image.
    """
    recipient = "pw_recovery@hikvision.com"
    if not SENDER_EMAIL or not APP_PASSWORD:
        raise RuntimeError("VisionGuard SMTP is not configured.")

    path = Path(attachment_path)
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("Recovery QR attachment is empty or missing.")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise RuntimeError("Recovery QR attachment exceeds the 10 MB limit.")

    suffix = path.suffix.lower()
    allowed = {".png", ".jpg", ".jpeg", ".bmp", ".zip"}
    if suffix not in allowed:
        raise RuntimeError("Unsupported recovery file. Use the original Hikvision PNG/JPG/BMP or device export ZIP.")

    raw = path.read_bytes()
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Password Recovery QR - {nvr_name} - {nvr_ip}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = recipient

    msg.attach(MIMEText(
        f"Authorized password recovery request for {nvr_name} ({nvr_ip}).\n"
        "The attachment is the original recovery export from the NVR's official "
        "Forgot Password -> Verify by Reserved Email workflow.\n"
        "Do not use a screenshot of the QR; use the NVR-exported recovery file.",
        "plain", "utf-8"))

    if suffix == ".png":
        part = MIMEImage(raw, _subtype="png")
    elif suffix in {".jpg", ".jpeg"}:
        part = MIMEImage(raw, _subtype="jpeg")
    elif suffix == ".bmp":
        part = MIMEImage(raw, _subtype="bmp")
    else:
        part = MIMEApplication(raw, _subtype="zip")

    part.add_header("Content-Disposition", "attachment", filename=path.name)
    msg.attach(part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, [recipient], msg.as_string())

    print(f"[HIKVISION RECOVERY] Sent original attachment: {path.name} ({len(raw)} bytes, {part.get_content_type()})")
    return True

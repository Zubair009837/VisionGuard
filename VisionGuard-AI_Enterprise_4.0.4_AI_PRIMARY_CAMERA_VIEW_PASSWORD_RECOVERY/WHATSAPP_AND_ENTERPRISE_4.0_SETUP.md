# VisionGuard AI Enterprise 4.0 additions

## Added
- Optional WhatsApp Cloud API alerts for camera/NVR alerts and recovery.
- Dedicated NVR-wide outage monitor. Offline alert includes NVR name, IP, and last-known affected camera count.
- NVR recovery alert.
- Physical camera viewpoint detection tightened to require stronger scene-wide movement evidence; this is a CV-based viewpoint-change detector, not a guarantee that a human hand caused the movement.
- Nine-NVR angle monitoring remains enabled through the shared NVRS configuration.
- Persistent NVR display names from the NVR Control Center.
- Camera-to-NVR/channel movement remains discovery based and is confirmed through the existing stable-move engine.
- Dashboard administrator password change.
- Bulk video-resolution readback verification with additional Hikvision resolution compatibility.
- Existing features/files were retained.

## WhatsApp setup
Set these environment variables on the backend host:
- `VISIONGUARD_WHATSAPP_ENABLED=true`
- `VISIONGUARD_WHATSAPP_TOKEN=<Meta WhatsApp Cloud API access token>`
- `VISIONGUARD_WHATSAPP_PHONE_NUMBER_ID=<Meta phone number ID>`
- `VISIONGUARD_WHATSAPP_TO=<recipient international number>`

If WhatsApp is not configured, the application continues using email alerts.

## Important
The camera-angle engine can detect a physical viewpoint change using global image geometry, but software cannot prove from a single image that a person physically touched the camera. The implementation therefore labels it as a physical/viewpoint movement only when strong global-motion evidence and confirmation readings are met.

For a camera that is physically rewired from NVR-1 to NVR-2, allow the discovery engine to see the camera on the new NVR/channel. The existing migration tracker confirms stable movement and records old/new NVR assignment.

## Enterprise 4.0.1 hotfixes

- Live camera inventory is now canonicalized against the 9 configured NVRs. Legacy aliases such as `NVR 1` and unrelated stale cache labels are excluded from counters.
- Duplicate `(NVR, channel)` camera records are suppressed in the API response.
- `/nvr/status` now includes the stable NVR ID.
- Bulk NVR user creation uses the documented Hikvision ISAPI `<User>` schema and reports per-NVR errors.
- WhatsApp settings are available from the admin sidebar at **WhatsApp Alerts**. Default recipient: `+91 9548749677`.
- WhatsApp delivery requires Meta Cloud API credentials; the recipient number alone is not sufficient.

# VisionGuard AI Enterprise 4.0.1 — Hotfix

## Fixed
1. Camera/NVR inventory now accepts only the 9 configured NVRs and canonicalizes labels such as `NVR 1` → `NVR-1`.
2. Stale camera records such as unrelated `Zubair Khan` labels no longer inflate the dashboard count.
3. Duplicate `(NVR, channel)` records are suppressed.
4. NVR status API now returns stable NVR IDs.
5. Bulk NVR user creation now uses the Hikvision ISAPI user XML schema and returns per-NVR error details.
6. Added admin-only **WhatsApp Alerts** page in the left sidebar.
7. Default WhatsApp recipient is `+91 9548749677`.
8. WhatsApp settings can be saved from the dashboard; Meta Cloud API token and Phone Number ID are required for actual delivery.
9. Existing email/NVR outage/camera-angle alert engines remain enabled.

## Expected inventory with the current configuration
- NVRs: 9
- Camera counts from the current dashboard screenshot: 16 + 16 + 8 + 23 + 29 + 15 + 15 + 15 + 15 = **152 cameras**.

The old screenshot total of 184 included 32 stale/foreign camera entries.

## WhatsApp setup
Open **WhatsApp Alerts** from the admin sidebar and enter:
- Recipient: `919548749677`
- Meta WhatsApp Phone Number ID
- Meta Cloud API access token

Then enable alerts, save, and use **SEND TEST**.

The phone number itself is not an authentication credential; Meta Cloud API credentials are required.

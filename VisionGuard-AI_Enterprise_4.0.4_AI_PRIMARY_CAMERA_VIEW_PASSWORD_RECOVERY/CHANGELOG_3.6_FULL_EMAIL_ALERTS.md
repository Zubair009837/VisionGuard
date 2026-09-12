# VisionGuard AI 3.6 - Full Email Alert Upgrade

## Included
- Camera NVR movement confirmation window set to **20 seconds** for current testing.
- Old `camera_assignment_pending.json` candidates reset to `{}`.
- Movement UI displays the live confirmation window and countdown in seconds.
- NVR CPU warning/critical email alerts with metric, threshold and reason.
- NVR memory warning/critical email alerts.
- NVR temperature warning/critical email alerts.
- NVR storage high/critical email alerts.
- HDD health failure email alerts.
- Storage telemetry unavailable email alerts.
- Existing NVR offline/recovery email flow preserved without creating duplicate NVR-offline emails.
- Recording-loss detection now also catches the case where **no recording clips are returned** in the search window.
- Recording-loss email now includes an evidence-based reason, such as NVR unreachable, channel disabled, recording disabled, no Hikvision indexed clips, or a verified gap with the NVR reachable.
- Existing camera offline/recovery, video loss/recovery, identity, IP conflict, camera angle, PTZ, camera migration and other email flows are preserved.
- SMTP configuration continues to use the existing project configuration.

## Current test values
- Camera movement confirmation: **20 seconds**.
- Recording loss threshold: **5 minutes** (existing project setting).
- NVR health polling: **5 seconds**.

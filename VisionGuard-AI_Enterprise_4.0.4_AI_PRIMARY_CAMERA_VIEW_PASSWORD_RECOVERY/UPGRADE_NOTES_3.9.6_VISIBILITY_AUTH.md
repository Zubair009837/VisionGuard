# VisionGuard AI 3.9.6 — Visibility, NVR Health & Application Access

- Dashboard now exposes a prominent NVR Health Center section.
- NVR cards show CPU, memory, temperature, latency, HDD and uptime telemetry.
- Temperature polling now tries the normal ISAPI status response and Hikvision hardware/temperature fallback endpoints when the main status response does not contain a sensor.
- Temperature is never fabricated: unavailable sensors are explicitly shown as SENSOR N/A.
- Health Center has larger typography and a live refresh action.
- NVR Command Center typography has been increased for readability.
- Application login added with role-aware access.
- Default application administrator: `admin` with the password supplied during this upgrade.
- Application Users page now includes application account management separately from NVR user management.
- Administrator-only access is applied to Settings, Users and Audit Log in the frontend.
- Existing NVR/camera/recording/alerts/analytics/floor-map/storage/PTZ functionality is retained.

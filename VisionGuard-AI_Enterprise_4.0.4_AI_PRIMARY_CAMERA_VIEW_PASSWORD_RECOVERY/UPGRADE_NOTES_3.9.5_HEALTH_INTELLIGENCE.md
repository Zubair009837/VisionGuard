# VisionGuard AI 3.9.5 — Health Intelligence Upgrade

This package is an additive upgrade. Existing files and monitoring/settings features are retained.

## Added

- **NVR Health Center**: live CPU, memory, temperature, uptime, HDD count/status and NVR API latency.
- **Historical telemetry**: bounded rolling health history for trend charts (15m / 1h / 6h / 24h).
- **Health thresholds & insights**: CPU, memory, temperature and latency warnings/critical states.
- **Diagnostics Center**: backend, health engine, recording monitor, camera monitor, storage monitor and alert engine status plus NVR latency.
- **Alert acknowledgement**: operators can acknowledge alert events; acknowledgement is persisted.
- **Audit Log**: configuration changes, NVR reboot requests, camera updates and alert acknowledgements are recorded.
- **Reports upgrade**: NVR health snapshot, temperature/latency fields and Print/PDF browser output alongside CSV export.
- **NVR health telemetry**: network/API response latency is captured during every health poll.

## Existing functionality retained

Live View, Cameras, NVR settings, Alerts, Camera Movement, Analytics, Floor Map, Storage, Users, Reports, Settings, recording-loss monitoring, IP-conflict detection, camera-angle monitoring, PTZ monitoring and existing enterprise email/alert functionality remain in the project.

## Runtime files

`backend/app/nvr_health_history.json` is created automatically by the background health monitor and keeps a bounded rolling history. `backend/app/audit_log.json` is created when the first auditable action occurs.

## Important device limitation

Temperature and other telemetry are displayed from the NVR's ISAPI health response. If a specific NVR firmware does not expose a sensor/value, the UI correctly shows `—` rather than inventing a reading.

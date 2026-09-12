# VisionGuard AI - Recording Retention V11 Update

## Added
- NVR-wise actual recording retention based on Hikvision recording search evidence.
- Camera/channel-wise actual retention.
- Oldest and newest recording evidence per camera.
- NVR status: HEALTHY (>=30 days), WARNING (20-29.9 days), CRITICAL (<20 days), RECORDING FAILURE when no recording evidence exists.
- Dashboard retention section with NVR and camera/channel details.
- Cached retention telemetry for 15 minutes to avoid repeatedly hammering NVRs.
- Historical recording search remains unchanged and uses movement/assignment history.
- NVR Control Center Sync Time now returns a structured failure instead of an opaque server error when a Hikvision firmware rejects the time write. The UI displays the backend error.

## Important
Retention is not inferred from HDD capacity. It is calculated from actual recording search results over a 45-day lookback window.

The first retention calculation can take time because VisionGuard queries real NVR recording indexes. Subsequent dashboard reads use the 15-minute cache.

Backend Python files were syntax-checked successfully. Frontend build could not be executed in this environment because the uploaded project does not include installed `node_modules`/Vite.

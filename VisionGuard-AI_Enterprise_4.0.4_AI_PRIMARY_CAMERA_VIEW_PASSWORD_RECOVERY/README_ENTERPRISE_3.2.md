# VisionGuard AI Enterprise 3.2

This build keeps the existing VisionGuard AI NVR health, camera monitoring, camera-angle monitoring, IP-conflict engine, email alerts, recording monitor, NVR settings, storage and dashboard code and adds the requested enterprise controls.

## Added
- All configured NVRs (NVR-1 through NVR-9) remain monitored.
- NVR user discovery: `/nvr/users` and `/nvr/users/summary`.
- Users page showing each NVR, user count, usernames, roles and enabled state.
- Individual camera settings: rename, IP and enable/disable.
- Bulk camera settings: select cameras from one NVR, all NVRs or search results and apply a common change.
- Floor Map page: upload a floor plan and place cameras by clicking the map. Browser persistence is used so the layout survives refresh.
- Camera NVR movement audit: remembers camera assignment and detects when the same camera name/IP appears under another NVR/channel. Events are written to `backend/app/camera_movement_history.json`, added to alert history and emailed.
- IP conflict alerts continue across the complete configured NVR fleet; conflict events are also added to alert history.
- Recording-loss threshold is exactly 5 minutes (`RECORDING_LOSS_THRESHOLD_SECONDS = 300`). Recovery is also monitored.
- SMTP now falls back to the existing values in `config.py` when environment variables are not set, so the existing configured email setup is not silently ignored.
- Camera Movement page and CSV Reports page.
- Live View route is wired to the existing MJPEG stream endpoint.

## Important
Camera bulk IP/name changes are sent to the Hikvision InputProxy channel API. Exact writable fields can vary by Hikvision firmware/model; failed NVR writes are reported per camera instead of being silently marked successful.

## Start
Backend:
```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

The existing NVR configuration remains in `backend/app/config.py`.

## 3.2.1 Professional Configuration UI Update

This package now includes a professional dark-mode configuration experience:

- Multi-select NVR Settings: choose one, multiple, or all 9 NVRs.
- Select All 9 / Clear selection controls and visible online/offline status.
- Device Info is presented as readable fields instead of raw XML.
- Network settings are presented in an editable per-NVR grid while preserving unique NVR IPs.
- Date & Time settings are presented in an editable per-NVR grid.
- Apply to Selected NVRs sends each NVR its own prepared ISAPI payload and returns per-NVR success/failure results.
- Advanced ISAPI remains available for expert XML operations.
- NVR Users page has been restyled with a dark professional table, search, status filters and per-NVR user cards.
- Camera Management has been restyled with dark professional inventory, single-camera edit and multi-camera bulk configuration.
- Bootstrap white table/card styling is overridden for these management screens so the UI remains consistent with the VisionGuard dark SOC theme.

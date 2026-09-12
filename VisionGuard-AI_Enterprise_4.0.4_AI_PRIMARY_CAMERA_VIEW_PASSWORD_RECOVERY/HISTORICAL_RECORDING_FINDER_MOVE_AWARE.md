# Historical Recording Finder — Move-Aware Search

## What changed

The Historical Recording Finder no longer assumes that a camera's current NVR/channel is valid for every historical date.

For a selected date/time window it now builds recording-search candidates from:

1. Persistent camera NVR movement history (`backend/app/camera_movement_history.json`).
2. Persistent device registry (`backend/app/device_registry.json`) when available.
3. Current NVR channel discovery as a safety net.

If a camera moved from one NVR/channel to another, the finder can search the historical assignment for the selected period and can return multiple recording locations when the selected period spans more than one assignment.

## Important limitation

Historical movement search depends on historical movement/registry evidence that actually exists on the backend. The application cannot reconstruct an old NVR/channel that was never recorded anywhere. In that case it safely falls back to current NVR discovery rather than labeling an unrelated channel as the camera.

## UI

The finder now shows a Mapping column:

- Historical move — assignment came from camera movement history.
- Historical registry — assignment came from the persistent device registry.
- Current — assignment came from current NVR discovery.

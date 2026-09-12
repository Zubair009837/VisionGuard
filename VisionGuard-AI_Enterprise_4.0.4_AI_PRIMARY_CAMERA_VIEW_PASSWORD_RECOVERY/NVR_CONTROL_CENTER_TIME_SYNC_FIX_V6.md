# NVR Control Center Time Sync Fix V6

Fixed the Hikvision time synchronization path.

### What changed
- Uses `/ISAPI/System/time/localTime` first, which accepts a plain ISO-8601 local time.
- Falls back to `/ISAPI/System/time` with the documented Hikvision ISAPI namespace, version and `timeZone`.
- Reads and verifies NVR time after a successful PUT.
- Captures Hikvision response status/body when a request fails.
- Stops browser UTC conversion from accidentally sending UTC instead of India/server local time.
- Time Guard now uses the same robust time-reading logic and no longer throws `Invalid isoformat string: ''` for an empty field.

### Sync button
The frontend now lets the backend use the VisionGuard server clock. This avoids `Date.toISOString()` sending UTC.

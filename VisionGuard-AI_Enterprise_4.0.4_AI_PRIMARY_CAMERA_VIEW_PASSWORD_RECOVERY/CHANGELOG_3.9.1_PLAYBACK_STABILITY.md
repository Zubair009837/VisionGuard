# VisionGuard AI 3.9.1 - Live/Playback Stability Patch

## Fixed
- Hikvision recording search now sends the correct `searchResultPosition` element and XML namespace.
- Playback search retries multiple Hikvision track IDs and metadata variants instead of failing on the first HTTP 400.
- Live RTSP proxy now tries main/sub/common stream IDs and automatically reconnects after transient frame/RTSP failures.
- Live proxy uses low-latency TCP buffering and limits oversized frames before JPEG encoding to reduce CPU and browser latency.
- AI Diagnose forces a fresh NVR health/storage read so CPU, memory, temperature and HDD status are not stale.
- AI Diagnose explicitly reports when a firmware does not expose a telemetry field instead of silently showing UNKNOWN.
- Live View automatically retries a failed MJPEG connection.
- First playback search result is automatically selected for playback.

## Preserved
- Existing NVR configuration, email system, camera movement tracking, angle monitor, recording-loss monitor, storage monitor and alert history.

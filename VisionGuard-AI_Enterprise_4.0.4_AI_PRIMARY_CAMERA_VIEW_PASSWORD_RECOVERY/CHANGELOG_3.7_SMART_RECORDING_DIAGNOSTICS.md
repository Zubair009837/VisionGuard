# VisionGuard AI 3.7 - Smart Recording Diagnostics

## Recording-loss alert upgrade

The recording-loss engine no longer sends a generic list of possible causes when a verified recording gap is found.

At verification time it now checks, where supported by the NVR:

- NVR reachability
- Channel enabled/disabled state
- Recording-enabled state
- Live camera/input online state
- Camera/video detection state
- HDD health/status
- Storage usage / critical storage condition
- Live recording-status endpoints when exposed by the firmware

The email reports a detected reason only when the NVR exposes direct evidence. If no direct root cause is available, the email explicitly says that no hardware/configuration fault is currently proven and identifies the evidence observed instead of guessing.

This is intentionally evidence-based because current ISAPI state cannot always prove the historical root cause of a gap that ended minutes earlier.

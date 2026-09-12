# VisionGuard AI 3.5 Enterprise Professional Update

- Fixed the Analytics blank-page React hook-order crash.
- Added live Analytics aggregation for cameras, NVR health, recording loss, storage, camera movement, angle monitoring, IP conflicts and recent alerts.
- Camera NVR movement is now a 10-minute confirmation workflow: transient moves are ignored; only a stable move for 600 seconds creates history/alert/email.
- Analytics exposes pending movement verification and confirmed movement counts.
- NVR user management retains per-NVR inventory and bulk enable/disable/role controls; role values are normalized to Hikvision Administrator/Operator/Viewer values.
- NVR Settings retains single/multi/all-NVR selection, independent per-NVR network/time payloads, advanced ISAPI and reboot controls.
- Camera management retains single-camera edit plus multi-camera bulk name/IP/enable controls.
- Recording-loss threshold remains 300 seconds (5 minutes) with verification/recovery handling.
- IP conflict engine continues to scan all configured NVRs and uses the existing alert/email pipeline.
- Existing angle monitoring, floor-map, storage, reports, alert history and email templates are preserved.

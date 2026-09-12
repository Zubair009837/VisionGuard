# VisionGuard AI V9 – Bulk Camera Controls & Proactive Monitoring

## Added
- One-click bulk camera video configuration across selected NVRs: resolution, FPS, bitrate, H.264/H.265, I-frame/GOV, main/sub stream.
- Per-channel result reporting; one failed camera/channel does not hide other results.
- NVR-wide recording outage alert when at least 90% of discovered cameras have confirmed recording loss for >=5 minutes. Recovery alert when the condition clears.
- Camera angle baselines now prefer camera hardware identity (serial/MAC/device identity) and fall back to normalized camera name, so the same camera can retain a permanent visual baseline after IP/NVR/channel changes.
- Camera angle scan interval reduced to 15 seconds with two confirmations (~30 seconds nominal) and a slightly more sensitive change threshold. Existing physical-movement verification and email alerting remain in place.
- All-NVR audit endpoint and UI: device/status/time/storage/channel HTTP health evidence.
- Proactive risk score using measurable signals such as offline cameras, active recording losses and recent NVR time events. High risk sends an early-warning email once per day. This is an early-warning assessment, not a guaranteed future-failure prediction.
- Authorized Hikvision password-recovery workflow button. VisionGuard does not bypass Hikvision authentication or manufacture reset codes; device-specific recovery still requires the official authorized recovery process.
- Existing IP conflict/migration, NVR time auto-sync, drift email, recording loss, historical recording finder, and NVR controls retained.

## Safety
Video encoding settings are applied by reading each channel's existing ISAPI XML and patching only requested fields. Firmware/model support can differ; failed channels are reported individually. Reboot/IP/password operations are not silently performed.

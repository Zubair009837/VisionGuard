# VisionGuard AI V8 - NVR Time Auto-Remediation & One-Click Settings

## Time change behavior
- Polls every 5 seconds.
- Detects a real change in NVR clock offset of >= 1 second; normal ticking is ignored.
- Confirms the change for 30 seconds.
- After confirmation, automatically syncs the NVR to the VisionGuard server clock.
- Sends a NVR TIME CHANGE DETECTED - AUTO SYNC email.
- Verifies the NVR clock after the write.
- Logs candidate, auto-sync success, or auto-sync failure in the Time Guard audit.

## One-click NVR controls
- Settings Control supports selecting one, several, or all NVRs.
- One-click Sync Time Selected is available.
- Existing bulk settings apply Device/Network/Date & Time/Advanced ISAPI payloads independently per selected NVR.
- Reboot Selected remains available and requires the existing confirmation.

## Safety
- Destructive firmware/factory reset endpoints remain blocked.
- Network settings should be reviewed before bulk application because an incorrect IP can disconnect an NVR.

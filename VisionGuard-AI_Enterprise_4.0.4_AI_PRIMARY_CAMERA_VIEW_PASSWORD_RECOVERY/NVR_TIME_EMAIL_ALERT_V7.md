# NVR Time Email Alert – V7

VisionGuard now emails the configured receiver when:

1. A successful manual **Sync Time** changes an NVR clock.
2. An NVR crosses the configured time-drift threshold (default 90 seconds).
3. A previously drifted NVR returns to the allowed tolerance (recovery email).

The successful Sync Time path records old time, new time, method, server time and Hikvision response in Time Change / Drift Audit. The in-memory time-guard state is also reset after a successful manual sync to prevent a duplicate drift alert on the next 60-second check.

Configuration in `backend/app/config.py`:

- `NVR_TIME_CHANGE_EMAIL_ENABLED = True`
- `NVR_TIME_DRIFT_ALERT_SECONDS = 90`

Email uses the existing VisionGuard SMTP configuration and `send_nvr_health_email()`.


## V8 Time Change Auto-Remediation

- NVR clock monitor polls every 5 seconds.
- It detects an actual clock-offset change of at least 1 second; normal second-by-second clock ticking is ignored.
- A detected change must persist for 30 seconds before action.
- After 30 seconds, VisionGuard sends the NVR TIME CHANGE alert and automatically synchronizes the NVR clock to the VisionGuard server clock.
- The new time is read back and verified.
- Auto-sync success/failure is written to the Time Guard audit.
- Settings Control includes a one-click **Sync Time Selected** action for any selected NVRs, including all nine.
- Existing bulk Settings Control remains available for Device, Network, Date & Time and Advanced ISAPI changes. Network changes should be reviewed before applying because an incorrect IP can disconnect an NVR.

# NVR Control Center + Automatic Time Guard

Added to the original VisionGuard 3.9.6 project without replacing the existing dashboard/frontend.

## New
- Admin-only NVR Control Center.
- Select any configured NVR.
- Read device information, current NVR time and network information through Hikvision ISAPI.
- Sync NVR time from VisionGuard server time.
- Audit log for manual NVR time changes.
- Automatic time-drift monitoring for every configured NVR every 60 seconds.
- Default tolerance: 90 seconds.
- First drift event generates the existing NVR health email alert; repeated checks do not spam duplicate emails.
- Recovery email/audit event when the NVR returns within tolerance.

## Important
The automatic monitor uses the NVRs already configured in `backend/app/config.py`. It does not store new credentials in the frontend.

The control center intentionally exposes only settings that are implemented through known Hikvision ISAPI endpoints. More read/write settings can be added safely endpoint-by-endpoint.

# Hikvision QR Email Fix v2

The Hikvision service replied that the QR could not be found in the attachment or was invalid.

This patch changes only the recovery-mail relay:
- PNG/JPG/BMP attachments are sent with image MIME types.
- ZIP exports are sent as application/zip.
- Original attachment bytes and filename are preserved.
- The UI explicitly instructs users to upload the NVR-exported recovery file, not a screenshot.

Hikvision documentation says the QR should be exported from the NVR's official password-reset flow and emailed as an attachment; the verification code is then sent to the configured reserved email.

If the same rejection arrives after this patch, the uploaded file itself is not an acceptable Hikvision recovery export (for example a screenshot), or the NVR's current recovery method differs from the Reserved Email workflow.

# VisionGuard AI 3.9 - Live View & Playback Console Enhancements

## Added
- NVR-first Live View selector for all configured NVRs.
- Loads the complete discovered camera list for the selected NVR instead of limiting Live View to the first 24 cameras.
- Camera search by name, IP or channel.
- Live MJPEG viewer with camera/NVR metadata.
- Snapshot capture/download through Hikvision ISAPI.
- Recording search by channel and time range through Hikvision ContentMgmt search.
- Playback viewer using the discovered recording playback URI and the backend MJPEG proxy.
- Optional recording clip export through FFmpeg when FFmpeg is installed on the backend PC.
- Per-camera rule-based diagnostics showing NVR CPU, memory, temperature, HDD status and camera status.
- NVR health/storage context is surfaced directly beside the live viewer.
- Transparent audio status: the existing MJPEG proxy is video-only; the UI does not falsely claim audio is available.

## Preserved
- Existing NVR/camera discovery and monitoring engines.
- Existing camera movement confirmation window of 20 seconds.
- Existing recording index-delay protection and 5-minute verified-gap threshold.
- Existing alert, storage, NVR health, angle and identity monitoring modules.

## Notes
- Browser playback is implemented through the backend proxy because browsers cannot natively play RTSP streams.
- Clip export requires an `ffmpeg` executable available on the backend machine. Live view, snapshot and recording search do not require FFmpeg.
- Exact Hikvision playback/download support depends on NVR firmware and the recording-search response returned by the device.

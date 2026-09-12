# Historical Recording Finder — Move Aware

## What changed
- Durable `camera_assignment_timeline.json` records confirmed NVR/channel validity intervals.
- Historical search uses assignment timeline first, then legacy movement history, then device registry.
- Current discovery is used only when no historical evidence exists.
- Recording searches are clipped to the historical assignment interval, so a move inside a requested time range is handled correctly.
- New `/historical-recordings/timeline` API powers the Camera History movement timeline.
- UI shows Valid During, Movement, and a Camera Movement Timeline.

## Important historical limitation
The system cannot reconstruct an old NVR/channel that was never recorded in VisionGuard movement history or device registry. Once this version is running, every confirmed assignment is persisted automatically.

# VisionGuard AI V10

- Fixed false NVR time-change emails: normal ticking and zero-change samples no longer alert.
- Clock-change notification requires a real >=60-second offset change, confirmed for 30 seconds, then auto-syncs and verifies.
- Immediate duplicate NVR drift emails disabled; confirmed remediation flow owns notification.
- Camera angle monitor uses a permanent baseline and a separate last-movement anchor so later physical movements can trigger fresh emails without replacing the permanent baseline.
- Angle scan interval reduced to 10 seconds and geometric detection made more responsive while retaining multi-signal confirmation.
- Camera angle evidence is saved with each alert.

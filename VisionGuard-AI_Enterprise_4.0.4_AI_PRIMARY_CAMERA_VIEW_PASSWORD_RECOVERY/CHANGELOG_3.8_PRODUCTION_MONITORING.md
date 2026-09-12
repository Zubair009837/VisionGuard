# VisionGuard AI 3.8 – Production Monitoring Improvements

- Fixed NVR health HTTP 500 caused by the health-email `ip` argument mismatch.
- HDD parsing now retains status even when firmware omits capacity/free-space.
- HDD unhealthy/missing telemetry is alerted; normal overwrite/full storage is not treated as a fault.
- CPU/memory alerts require 3 consecutive abnormal readings; temperature requires 2.
- Recording loss remains a 5-minute confirmed gap, while a 10-minute finalized-recording/indexing grace prevents false tail-gap alarms.
- Recording diagnostics remain evidence-based and do not guess historical causes.
- Camera movement detection now covers both NVR changes and channel changes, with the existing 20-second confirmation.
- Camera angle monitoring has more tolerant physical-movement thresholds and can attach the exact triggering frame as email evidence; evidence is bounded to 200 images.
- Dashboard NVR health cards show detected HDD count/issues.

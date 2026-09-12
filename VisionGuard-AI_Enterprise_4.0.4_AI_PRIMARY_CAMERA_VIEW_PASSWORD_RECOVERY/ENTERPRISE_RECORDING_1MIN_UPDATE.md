# Recording Alert — 1 Minute Mode

- Recording-loss threshold: 60 seconds.
- Current recording window is checked immediately (`RECORDING_INDEX_DELAY_SECONDS = 0`).
- Verification delay: 0 seconds; the first confirmed 60-second gap alerts on the next monitor scan.
- Monitor scan interval remains 30 seconds, so expected alert time is about 60–90 seconds from the actual recording stop.
- Existing reason diagnostics, recovery alerts, email alerts, and dashboard history are retained.

## Important
Hikvision firmware can take time to expose very recent recording segments in search results. This fast mode intentionally trades that indexing grace period for faster alerting, so brief search/indexing delays can produce alerts.

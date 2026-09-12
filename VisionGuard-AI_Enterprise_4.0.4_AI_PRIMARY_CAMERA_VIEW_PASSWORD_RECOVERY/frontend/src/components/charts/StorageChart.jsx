import { useCallback, useEffect, useMemo, useState } from "react";

const API = "http://127.0.0.1:8010";

function formatBytes(bytes) {
  if (bytes == null) return "—";
  const n = Number(bytes);
  if (!Number.isFinite(n)) return "—";
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(0)} MB`;
  if (n < 1024 ** 4) return `${(n / 1024 ** 3).toFixed(1)} GB`;
  return `${(n / 1024 ** 4).toFixed(2)} TB`;
}

function percent(value) {
  return value == null ? "—" : `${Number(value).toFixed(1)}%`;
}

function StorageChart() {
  const [items, setItems] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (force = false) => {
    try {
      setError("");
      const endpoint = force ? "/storage/refresh" : "/storage";
      const response = await fetch(`${API}${endpoint}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`Storage API ${response.status}`);
      const data = await response.json();
      setItems(Array.isArray(data.data) ? data.data : []);
      setLastUpdate(data.last_update ? new Date(data.last_update * 1000) : null);
    } catch (err) {
      setError(err.message || "Unable to read storage telemetry");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => load(), 15000);
    return () => clearInterval(timer);
  }, [load]);

  const online = useMemo(() => items.filter((x) => x.status === "ONLINE").length, [items]);

  return (
    <div className="vg-storage-live">
      <div className="vg-storage-toolbar">
        <div>
          <h5>💽 NVR HDD STORAGE</h5>
          <span>{online}/9 NVRs reporting live storage telemetry</span>
        </div>
        <div className="vg-storage-actions">
          <span>{lastUpdate ? lastUpdate.toLocaleTimeString() : "—"}</span>
          <button type="button" onClick={() => load(true)} disabled={loading}>
            {loading ? "Reading…" : "↻ Refresh"}
          </button>
        </div>
      </div>

      {error && <div className="vg-storage-error">{error}</div>}

      <div className="vg-storage-grid">
        {items.map((nvr) => {
          const usedPct = nvr.used_percent;
          const hasFree = nvr.free_bytes != null;
          return (
            <div className="vg-storage-card" key={nvr.name}>
              <div className="vg-storage-card-head">
                <div>
                  <strong>{nvr.name}</strong>
                  <small>{nvr.ip}:{nvr.port}</small>
                </div>
                <span className={`vg-storage-status ${nvr.status === "ONLINE" ? "online" : "offline"}`}>
                  {nvr.status}
                </span>
              </div>

              {nvr.status !== "ONLINE" ? (
                <div className="vg-storage-unavailable">NVR storage unavailable</div>
              ) : (
                <>
                  <div className="vg-storage-percent">
                    <strong>{percent(usedPct)}</strong>
                    <span>used</span>
                  </div>
                  <div className="vg-storage-meter">
                    <span style={{ width: `${Math.min(Math.max(Number(usedPct ?? 0), 0), 100)}%` }} />
                  </div>
                  <div className="vg-storage-summary">
                    <div><small>Total</small><b>{formatBytes(nvr.total_bytes)}</b></div>
                    <div><small>Used</small><b>{formatBytes(nvr.used_bytes)}</b></div>
                    <div><small>Free</small><b>{hasFree ? formatBytes(nvr.free_bytes) : "—"}</b></div>
                  </div>

                  <div className="vg-storage-hdds">
                    <div className="vg-storage-hdds-title">HDDs ({nvr.hdds?.length || 0})</div>
                    {(nvr.hdds || []).map((disk) => (
                      <div className="vg-storage-hdd" key={`${nvr.name}-${disk.id}`}>
                        <span>Disk {disk.id}</span>
                        <span>{formatBytes(disk.capacity_bytes)}</span>
                        <span>
                          {disk.free_known && disk.used_mb != null
                            ? `${((disk.used_mb / disk.capacity_mb) * 100).toFixed(1)}% used`
                            : "free space unavailable"}
                        </span>
                        <em>{disk.status}</em>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default StorageChart;

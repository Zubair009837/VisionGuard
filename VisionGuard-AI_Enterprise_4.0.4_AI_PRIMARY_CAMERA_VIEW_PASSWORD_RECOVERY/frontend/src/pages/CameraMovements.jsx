import { useEffect, useState } from "react";
import api from "../services/api";
import "./CameraMovements.css";

const fmt = (v) => v || "—";

const formatRemaining = (seconds) => {
  const value = Math.max(0, Number(seconds) || 0);

  if (value >= 60) {
    const minutes = Math.floor(value / 60);
    const secs = value % 60;
    return secs === 0
      ? `${minutes} min remaining`
      : `${minutes} min ${secs} sec remaining`;
  }

  return `${Math.ceil(value)} sec remaining`;
};

const formatWindow = (seconds) => {
  const value = Math.max(0, Number(seconds) || 0);

  if (value >= 60) {
    const minutes = Math.floor(value / 60);
    const secs = value % 60;
    return secs === 0 ? `${minutes} min` : `${minutes} min ${secs} sec`;
  }

  return `${value} sec`;
};

export default function CameraMovements() {
  const [data, setData] = useState({ history: [], summary: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    try {
      setError("");
      const r = await api.get("/camera-movements");
      setData(r.data || { history: [], summary: {} });
    } catch (e) {
      setError(
        e.response?.data?.detail ||
          e.message ||
          "Unable to load movement history"
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const timer = setInterval(load, 1000);
    return () => clearInterval(timer);
  }, []);

  const summary = data.summary || {};
  const pending = summary.pending || [];
  const verificationSeconds = Number(
    summary.confirmation_seconds || summary.verification_seconds || 20
  );

  return (
    <div className="vg-movement-page">
      <header className="vg-movement-header">
        <div>
          <div className="vg-eyebrow">IDENTITY / ASSIGNMENT AUDIT</div>
          <h1>Camera NVR Movement</h1>
          <p>
            Enterprise tracking for cameras that appear under a different NVR or channel.
          </p>
        </div>
        <button className="vg-primary-btn" onClick={load} disabled={loading}>
          ↻ {loading ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error && <div className="vg-movement-error">⚠ {error}</div>}

      <section className="vg-movement-kpis">
        <div>
          <span>Confirmed Movements</span>
          <strong>{summary.total_movements || 0}</strong>
          <small>{formatWindow(verificationSeconds)} verified events</small>
        </div>

        <div>
          <span>Affected Cameras</span>
          <strong>{summary.unique_cameras || 0}</strong>
          <small>Unique camera identities</small>
        </div>

        <div>
          <span>Pending Verification</span>
          <strong className="orange">{summary.pending_movements || 0}</strong>
          <small>
            Must remain moved for {formatWindow(verificationSeconds)}
          </small>
        </div>

        <div>
          <span>Verification Window</span>
          <strong>{formatWindow(verificationSeconds)}</strong>
          <small>Transient moves are ignored</small>
        </div>
      </section>

      {pending.length > 0 && (
        <section className="vg-movement-panel">
          <div className="vg-movement-panel-head">
            <div>
              <h2>Pending Movement Verification</h2>
              <p>
                A candidate move has been detected but will not alert until the {formatWindow(verificationSeconds)} confirmation window completes.
              </p>
            </div>
            <b>{pending.length} pending</b>
          </div>

          <div className="vg-pending-grid">
            {pending.map((item) => {
              const confirmationSeconds = Number(
                item.confirmation_seconds || verificationSeconds || 20
              );
              const elapsedSeconds = Number(item.elapsed_seconds || 0);
              const remainingSeconds = Math.max(
                0,
                Number(item.remaining_seconds || 0)
              );
              const progress = Math.min(
                100,
                Math.round((elapsedSeconds / confirmationSeconds) * 100)
              );

              return (
                <div className="vg-pending-card" key={item.identity}>
                  <strong>{item.camera}</strong>
                  <span>
                    {item.nvr} · CH-{fmt(item.channel)}
                  </span>
                  <div className="vg-progress">
                    <i style={{ width: `${progress}%` }} />
                  </div>
                  <small>{formatRemaining(remainingSeconds)}</small>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="vg-movement-panel">
        <div className="vg-movement-panel-head">
          <div>
            <h2>Movement Audit History</h2>
            <p>
              Only confirmed {formatWindow(verificationSeconds)} movements are stored here.
            </p>
          </div>
          <b>{data.history?.length || 0} events</b>
        </div>

        <div className="vg-movement-table-wrap">
          <table className="vg-movement-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Camera</th>
                <th>IP</th>
                <th>Previous Assignment</th>
                <th>Confirmed Assignment</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {(data.history || []).map((e, i) => (
                <tr key={`${e.time}-${i}`}>
                  <td>{fmt(e.time)}</td>
                  <td><strong>{fmt(e.camera)}</strong></td>
                  <td className="mono">{fmt(e.ip)}</td>
                  <td>
                    <span className="vg-assignment old">
                      {fmt(e.previous_nvr)} · CH-{fmt(e.previous_channel)}
                    </span>
                  </td>
                  <td>
                    <span className="vg-assignment new">
                      {fmt(e.current_nvr)} · CH-{fmt(e.current_channel)}
                    </span>
                  </td>
                  <td>{fmt(e.details)}</td>
                </tr>
              ))}

              {!data.history?.length && (
                <tr>
                  <td colSpan="6" className="vg-empty">
                    No confirmed camera movement events recorded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

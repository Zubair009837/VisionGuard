import Loader from "../components/Loader";
import { useEffect, useState } from "react";
import api from "../services/api";

function Alerts() {
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState([]);
  const [ackBusy, setAckBusy] = useState(null);

  const loadAlerts = async () => {
    try {
      const response = await api.get("/alerts");
      const data = Array.isArray(response.data) ? response.data : [];
      setAlerts([...data].reverse().slice(0, 500));
    } catch (error) {
      console.error("Alert history load failed", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAlerts();
    const timer = setInterval(loadAlerts, 5000);
    return () => clearInterval(timer);
  }, []);

  const acknowledge = async (alert) => {
    if (alert?._index == null) return;
    try {
      setAckBusy(alert._index);
      await api.post(`/alerts/${alert._index}/acknowledge`, { actor: "Operator" });
      await loadAlerts();
    } catch (error) { console.error("Alert acknowledgement failed", error); }
    finally { setAckBusy(null); }
  };

  if (loading) return <Loader text="Loading Alerts..." />;

  return (
    <div className="container-fluid px-4 py-4">
      <h2 className="mb-4">🚨 Alert Management</h2>

      <div className="card shadow" style={{ marginBottom: 16 }}>
        <div className="card-body" style={{ background: "#101d39", color: "#dbe7ff", borderRadius: 12 }}>
          <strong>🔴 Live monitoring active</strong> — NVR CPU, memory, temperature, connectivity and storage issues are checked automatically every 5 seconds.
        </div>
      </div>

      <div className="card shadow">
        <div className="card-header bg-danger text-white d-flex justify-content-between align-items-center">
          <h5 className="mb-0">Recent Alerts</h5>
          <span>{alerts.length} events</span>
        </div>

        <div className="card-body p-0">
          <div className="table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-dark">
                <tr>
                  <th>Time</th>
                  <th>NVR</th>
                  <th>Camera</th>
                  <th>IP</th>
                  <th>Severity</th>
                  <th>Alert Type</th>
                  <th>Details</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {alerts.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="text-center text-muted py-4">
                      No Alerts Found
                    </td>
                  </tr>
                ) : (
                  alerts.map((alert, index) => {
                    const type = alert.type || alert.status || "Alert";
                    const details =
                      alert.change ||
                      (alert.affected_cameras !== undefined
                        ? `${alert.affected_cameras} affected cameras`
                        : "-");
                    return (
                      <tr key={`${alert.time || "event"}-${index}`}>
                        <td>{alert.time || "-"}</td>
                        <td>{alert.nvr || "-"}</td>
                        <td>{alert.camera || "-"}</td>
                        <td>{alert.ip || "-"}</td>
                        <td><span className={`badge ${alert.severity === "CRITICAL" ? "bg-danger" : alert.severity === "WARNING" ? "bg-warning text-dark" : "bg-info text-dark"}`}>{alert.severity || "INFO"}</span></td>
                        <td>{type}</td>
                        <td>{details}</td>
                        <td>{alert.status === "ACKNOWLEDGED" ? <span className="badge bg-success">ACKNOWLEDGED</span> : <button className="btn btn-sm btn-outline-success" disabled={ackBusy === alert._index} onClick={() => acknowledge(alert)}>{ackBusy === alert._index ? "Saving…" : "Acknowledge"}</button>}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Alerts;

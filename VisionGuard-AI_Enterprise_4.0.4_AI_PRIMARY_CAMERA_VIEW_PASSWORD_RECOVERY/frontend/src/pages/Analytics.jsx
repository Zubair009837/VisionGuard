import { useCallback, useEffect, useState } from "react";
import api from "../services/api";
import Loader from "../components/Loader";
import "./Analytics.css";

const fmtTime = (value) => value ? new Date(value).toLocaleTimeString("en-IN") : "—";
const severityClass = (s) => String(s || "INFO").toLowerCase();

export default function Analytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setError("");
      const r = await api.get("/analytics/summary");
      setData(r.data || {});
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Analytics service unavailable");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); const t=setInterval(load,10000); return()=>clearInterval(t); }, [load]);
  const overview = data?.overview || {};
  const nvrs = data?.nvr_health || [];
  const alerts = data?.recent_alerts || [];
  const recording = data?.recording || {};
  const storage = data?.storage || [];
  const movement = data?.movement || {};
  const angles = data?.angle || {};

  const healthRate = overview.total_cameras ? Math.round((overview.online_cameras / overview.total_cameras) * 100) : 0;
  const storageKnown = storage.filter(x => x.used_percent != null);
  const avgStorage = storageKnown.length ? Math.round(storageKnown.reduce((a,x)=>a+Number(x.used_percent),0)/storageKnown.length) : null;
  const criticalAlerts = alerts.filter(a=>["CRITICAL","ERROR"].includes(String(a.severity).toUpperCase())).length;

  if (loading && !data) return <Loader text="Loading live analytics..." />;

  return <div className="vg-analytics-page">
    <header className="vg-analytics-header">
      <div><div className="vg-eyebrow">LIVE OPERATIONS INTELLIGENCE</div><h1>Analytics Dashboard</h1><p>Real monitoring telemetry from all configured NVRs, cameras, recording and alert engines.</p></div>
      <button className="vg-primary-btn" onClick={load}>↻ Refresh</button>
    </header>
    {error && <div className="vg-analytics-error">{error}</div>}

    <section className="vg-kpi-grid">
      <div className="vg-kpi"><span>Total Cameras</span><strong>{overview.total_cameras ?? 0}</strong><small>{healthRate}% currently healthy</small></div>
      <div className="vg-kpi"><span>Online Cameras</span><strong className="green">{overview.online_cameras ?? 0}</strong><small>Live status cache</small></div>
      <div className="vg-kpi"><span>Offline Cameras</span><strong className="red">{overview.offline_cameras ?? 0}</strong><small>Needs attention</small></div>
      <div className="vg-kpi"><span>NVR Availability</span><strong className="blue">{overview.online_nvrs ?? 0}/{overview.total_nvrs ?? 0}</strong><small>{overview.offline_nvrs ?? 0} offline</small></div>
      <div className="vg-kpi"><span>Critical Alerts</span><strong className="red">{criticalAlerts}</strong><small>{alerts.length} recent events loaded</small></div>
      <div className="vg-kpi"><span>Recording Loss</span><strong className="orange">{recording.active_losses ?? 0}</strong><small>5-minute threshold</small></div>
      <div className="vg-kpi"><span>Confirmed Camera Moves</span><strong className="purple">{movement.total_movements ?? 0}</strong><small>{movement.unique_cameras ?? 0} affected cameras</small></div>
      <div className="vg-kpi"><span>Movement Verification</span><strong className="blue">{movement.pending_movements ?? 0}</strong><small>Pending 10-minute confirmation</small></div>
      <div className="vg-kpi"><span>Avg HDD Used</span><strong>{avgStorage == null ? "—" : `${avgStorage}%`}</strong><small>{storageKnown.length}/{overview.total_nvrs ?? 0} reporting storage</small></div>
    </section>

    <div className="vg-analytics-grid">
      <section className="vg-panel vg-wide"><div className="vg-panel-head"><div><h2>NVR Health Matrix</h2><span>Online state and discovered camera load</span></div><b>{overview.online_nvrs ?? 0}/{overview.total_nvrs ?? 0} ONLINE</b></div><div className="vg-nvr-matrix">{nvrs.map(n=><div className="vg-nvr-health" key={n.name}><div><strong>{n.name}</strong><small>{n.ip || "IP unavailable"}</small></div><span className={n.status === "ONLINE" ? "online":"offline"}>{n.status}</span><div className="vg-mini-meter"><i style={{width:`${n.camera_count ? Math.min(100, n.camera_count*3) : 0}%`}}/></div><em>{n.camera_count ?? 0} cameras</em></div>)}</div></section>
      <section className="vg-panel"><div className="vg-panel-head"><div><h2>Recording Monitor</h2><span>Enterprise gap detection</span></div></div><div className="vg-big-number orange">{recording.active_losses ?? 0}</div><p className="vg-muted">Active recording-loss events</p><div className="vg-detail-list"><div><span>Threshold</span><b>{Math.round((recording.threshold_seconds ?? 300)/60)} min</b></div><div><span>Pending verification</span><b>{recording.pending ?? 0}</b></div><div><span>History events</span><b>{recording.history ?? 0}</b></div></div></section>
      <section className="vg-panel"><div className="vg-panel-head"><div><h2>Camera Integrity</h2><span>Identity and viewpoint monitoring</span></div></div><div className="vg-detail-list"><div><span>NVR movements</span><b>{movement.total_movements ?? 0}</b></div><div><span>Affected cameras</span><b>{movement.unique_cameras ?? 0}</b></div><div><span>Angle changed</span><b>{angles.changed ?? 0}</b></div><div><span>Angle monitored</span><b>{angles.cameras ?? angles.total ?? 0}</b></div></div></section>
      <section className="vg-panel vg-wide"><div className="vg-panel-head"><div><h2>Recent Alerts</h2><span>Latest events from the alert engine</span></div><b>{alerts.length} events</b></div><div className="vg-alert-list">{alerts.slice(0,8).map((a,i)=><div className="vg-alert-row" key={`${a.time}-${i}`}><span className={`vg-alert-sev ${severityClass(a.severity)}`}>{a.severity || "INFO"}</span><div><strong>{a.title || a.type || "Alert"}</strong><p>{a.description || "No description"}</p></div><time>{a.time || "—"}</time></div>)}{!alerts.length&&<div className="vg-empty">No alert events recorded yet.</div>}</div></section>
    </div>
  </div>;
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import api from "../services/api";
import Loader from "../components/Loader";
import "./HealthCenter.css";

const thresholds = { cpuWarn: 75, cpuCritical: 90, memWarn: 80, memCritical: 90, tempWarn: 70, tempCritical: 80 };
const tone = (v, warn, critical) => v == null ? "muted" : v >= critical ? "critical" : v >= warn ? "warning" : "good";
const fmtUptime = (seconds) => {
  if (seconds == null) return "—";
  const s = Math.max(0, Number(seconds));
  const d = Math.floor(s / 86400); const h = Math.floor((s % 86400) / 3600); const m = Math.floor((s % 3600) / 60);
  return `${d}d ${h}h ${m}m`;
};

export default function HealthCenter() {
  const [health, setHealth] = useState([]); const [history, setHistory] = useState([]); const [insights, setInsights] = useState([]);
  const [selected, setSelected] = useState(""); const [minutes, setMinutes] = useState(60); const [loading, setLoading] = useState(true); const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [h, hist] = await Promise.all([api.get("/nvr/health", { params: { force: 0 } }), api.get("/nvr/health/history", { params: { nvr: selected, minutes } })]);
      setHealth(h.data?.data || []); setInsights(h.data?.insights || []); setHistory(hist.data?.data || []); setError("");
    } catch (e) { setError(e.response?.data?.detail || e.message || "Health service unavailable"); }
    finally { setLoading(false); }
  }, [selected, minutes]);
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const selectedName = selected || (health[0]?.name || "");
  const chart = useMemo(() => history.filter(x => !selected || x.name === selected).map(x => ({ time: new Date((x.timestamp || 0) * 1000).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }), cpu: x.cpu_percent, memory: x.memory_percent, temp: x.temperature_c, latency: x.latency_ms })), [history, selected]);
  const selectedHealth = health.find(x => x.name === selectedName) || health[0];
  const problemCount = health.filter(x => x.status !== "ONLINE" || tone(x.cpu_percent, thresholds.cpuWarn, thresholds.cpuCritical) !== "good" || tone(x.memory_percent, thresholds.memWarn, thresholds.memCritical) !== "good" || tone(x.temperature_c, thresholds.tempWarn, thresholds.tempCritical) !== "good").length;

  if (loading && !health.length) return <Loader text="Loading NVR health intelligence..." />;
  return <div className="health-page">
    <header className="health-header"><div><div className="health-eyebrow">VISIONGUARD AI • INFRASTRUCTURE INTELLIGENCE</div><h1>NVR Health Center</h1><p>Live CPU, memory, temperature, storage, uptime and network telemetry with persistent trend history.</p></div><div className="health-actions"><select value={selected} onChange={e => setSelected(e.target.value)}><option value="">All NVRs / aggregate history</option>{health.map(n => <option key={n.name} value={n.name}>{n.name}</option>)}</select><select value={minutes} onChange={e => setMinutes(Number(e.target.value))}><option value="15">15 minutes</option><option value="60">1 hour</option><option value="360">6 hours</option><option value="1440">24 hours</option></select><button onClick={async()=>{setLoading(true); try { const h=await api.get("/nvr/health", {params:{force:1}}); setHealth(h.data?.data||[]); setInsights(h.data?.insights||[]); const hist=await api.get("/nvr/health/history", {params:{nvr:selected,minutes}}); setHistory(hist.data?.data||[]); setError(""); } catch(e){setError(e.response?.data?.detail||e.message||"Health refresh failed")} finally {setLoading(false)} }}>↻ Refresh Live</button></div></header>
    {error && <div className="health-error">⚠ {error}</div>}
    <section className="health-kpis"><div><span>NVRs Online</span><strong>{health.filter(x=>x.status==='ONLINE').length}/{health.length}</strong><small>Live connectivity</small></div><div><span>Attention Needed</span><strong className={problemCount ? "warn" : "ok"}>{problemCount}</strong><small>Based on configured thresholds</small></div><div><span>Highest Temperature</span><strong>{Math.max(...health.map(x=>Number(x.temperature_c)||0),0).toFixed(1)}°C</strong><small>Across reported sensors</small></div><div><span>Health Samples</span><strong>{history.length}</strong><small>Persisted telemetry points</small></div></section>

    <section className="health-panel"><div className="panel-title"><div><h2>Live NVR Matrix</h2><p>Click any recorder to focus its historical charts.</p></div><Link to="/diagnostics">Open diagnostics →</Link></div><div className="health-grid">{health.map(n => <button className={`nvr-health-card ${n.status !== "ONLINE" ? "offline" : ""}`} key={n.name} onClick={() => setSelected(n.name)}><div className="nvr-head"><b>{n.name}</b><span className={n.status === "ONLINE" ? "online" : "offline"}>{n.status}</span></div><div className="metric-row"><Metric label="CPU" value={n.cpu_percent == null ? "—" : `${n.cpu_percent}%`} tone={tone(n.cpu_percent,75,90)} /><Metric label="MEMORY" value={n.memory_percent == null ? "—" : `${n.memory_percent}%`} tone={tone(n.memory_percent,80,90)} /></div><div className="metric-row"><Metric label="TEMPERATURE" value={n.temperature_c == null ? "SENSOR N/A" : `${n.temperature_c}°C`} tone={tone(n.temperature_c,70,80)} /><Metric label="LATENCY" value={n.latency_ms == null ? "—" : `${n.latency_ms} ms`} tone={n.latency_ms >= 500 ? "warning" : "good"} /></div><div className="nvr-meta"><span>Uptime {fmtUptime(n.uptime_seconds)}</span><span>HDD {n.hdd_count ?? 0}</span><span>{n.temperature_source ? "TEMP SENSOR ✓" : "TEMP SENSOR —"}</span></div></button>)}</div></section>

    <section className="health-panel"><div className="panel-title"><div><h2>{selectedHealth?.name || "NVR"} Performance Trends</h2><p>Historical telemetry captured every health polling cycle.</p></div><span className="sample-badge">{chart.length} points</span></div><div className="charts"><Chart title="CPU / Memory" data={chart} keys={["cpu","memory"]} unit="%" /><Chart title="Temperature" data={chart} keys={["temp"]} unit="°C" /><Chart title="Network latency" data={chart} keys={["latency"]} unit="ms" /></div></section>

    <section className="health-panel"><div className="panel-title"><div><h2>AI Health Insights</h2><p>Rule-based operational recommendations generated from live telemetry.</p></div></div><div className="insight-list">{insights.length ? insights.map((i,idx)=><div className={`insight ${i.severity.toLowerCase()}`} key={`${i.nvr}-${idx}`}><b>{i.severity}</b><div><strong>{i.title}</strong><p>{i.detail}</p></div></div>) : <div className="empty-good">✓ No threshold breaches detected across online NVRs.</div>}</div></section>
  </div>;
}

function Metric({label,value,tone: t}) { return <div className="metric"><span>{label}</span><strong className={t}>{value}</strong></div>; }
function Chart({title,data,keys,unit}) { return <div className="chart-box"><div className="chart-title">{title}</div><ResponsiveContainer width="100%" height={210}><LineChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="rgba(130,160,220,.12)"/><XAxis dataKey="time" hide/><YAxis tick={{fill:'#8ea3c8',fontSize:11}}/><Tooltip contentStyle={{background:'#08142b',border:'1px solid #203c70',color:'#e8f1ff'}} formatter={(v,n)=>[`${v ?? "—"}${unit}` ,n]}/>{keys.map((k,i)=><Line key={k} type="monotone" dataKey={k} stroke={['#58a6ff','#58f2a7','#ffca5c','#b38cff'][i]} dot={false} strokeWidth={2}/>)}</LineChart></ResponsiveContainer></div>; }

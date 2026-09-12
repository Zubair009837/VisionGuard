import { useEffect, useMemo, useState } from "react";
import api from "../services/api";
import "./LiveView.css";

const BASE = api.defaults.baseURL || "";
const fmt = (v) => (v === null || v === undefined || v === "" ? "—" : v);

function localStamp(value) {
  const d = value ? new Date(value) : new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export default function LiveView() {
  const [nvrs, setNvrs] = useState([]);
  const [selectedNvr, setSelectedNvr] = useState(null);
  const [cameras, setCameras] = useState([]);
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState("live");
  const [start, setStart] = useState(localStamp(Date.now() - 5 * 60 * 1000).slice(0, 16));
  const [end, setEnd] = useState(localStamp().slice(0, 16));
  const [recordings, setRecordings] = useState([]);
  const [diagnostics, setDiagnostics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [volume, setVolume] = useState(100);
  const [streamNonce, setStreamNonce] = useState(0);
  const [streamRetrying, setStreamRetrying] = useState(false);
  const [playbackNonce, setPlaybackNonce] = useState(0);

  const loadNvrs = async () => {
    try {
      const r = await api.get("/live/nvrs");
      const list = Array.isArray(r.data) ? r.data : [];
      setNvrs(list);
      if (!selectedNvr && list.length) setSelectedNvr(list[0]);
    } catch (e) {
      setMessage(e.response?.data?.detail || e.message || "Unable to load NVRs");
    }
  };

  const loadCameras = async (nvr) => {
    if (!nvr) return;
    setLoading(true); setMessage(""); setSelected(null); setRecordings([]); setDiagnostics(null);
    try {
      const r = await api.get(`/live/cameras/${nvr.id}`);
      setCameras(r.data?.cameras || []);
    } catch (e) {
      setCameras([]); setMessage(e.response?.data?.detail || e.message || "Unable to load cameras");
    } finally { setLoading(false); }
  };

  useEffect(() => { loadNvrs(); }, []);
  useEffect(() => { loadCameras(selectedNvr); }, [selectedNvr?.id]);

  const filtered = useMemo(() => cameras.filter(c => {
    const q = search.trim().toLowerCase();
    return !q || `${c.name} ${c.ip} ${c.id}`.toLowerCase().includes(q);
  }), [cameras, search]);

  const streamUrl = selected
    ? `${BASE}/live/stream/${encodeURIComponent(selected.nvr)}/${selected.id}?stream=auto&retry=${streamNonce}`
    : "";

  const playbackUrl = useMemo(() => {
    if (!selected || !selectedNvr || mode !== "playback" || !recordings.length) return "";
    return `${BASE}/live/playback/${selectedNvr.id}/${selected.id}?start=${encodeURIComponent(start.replace("T", " ") + ":00")}&end=${encodeURIComponent(end.replace("T", " ") + ":00")}&v=${playbackNonce}`;
  }, [selected, selectedNvr, mode, recordings.length, start, end, playbackNonce]);

  async function inspect() {
    if (!selected || !selectedNvr) return;
    setMessage("Analyzing NVR, HDD, CPU, memory, temperature and camera health…");
    try {
      const r = await api.get(`/live/diagnostics/${selectedNvr.id}/${selected.id}`);
      setDiagnostics(r.data);
      setMessage("");
    } catch (e) { setMessage(e.response?.data?.detail || e.message || "Diagnostics unavailable"); }
  }

  async function snapshot() {
    if (!selected) return;
    try {
      const r = await api.post(`/live/snapshot/${encodeURIComponent(selected.nvr)}/${selected.id}`, {}, { responseType: "blob" });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `${selected.nvr}_CH-${selected.id}_${selected.name || "camera"}.jpg`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setMessage(e.response?.data?.detail || e.message || "Snapshot failed"); }
  }

  async function searchRecordings() {
    if (!selected || !selectedNvr) return;
    setLoading(true); setMessage("");
    try {
      const r = await api.get(`/live/recordings/search/${selectedNvr.id}/${selected.id}`, { params: { start: start.replace("T", " ") + ":00", end: end.replace("T", " ") + ":00" } });
      const results = r.data?.results || [];
      setRecordings(results);
      setPlaybackNonce(n => n + 1);
      setMode("playback");
      if (results.length) {
        const first = results[0];
        if (first.start_time) setStart(String(first.start_time).slice(0, 16).replace(" ", "T"));
        if (first.end_time) setEnd(String(first.end_time).slice(0, 16).replace(" ", "T"));
      }
      if (!r.data?.results?.length) setMessage("No recording segments found for this period. This is not treated as a recording failure automatically.");
    } catch (e) { setRecordings([]); setMessage(e.response?.data?.detail || e.message || "Recording search failed"); }
    finally { setLoading(false); }
  }

  function openPlayback(item) {
    setMode("playback");
    setPlaybackNonce(n => n + 1);
    if (item?.start_time && item?.end_time) {
      setStart(item.start_time.slice(0, 16).replace(" ", "T"));
      setEnd(item.end_time.slice(0, 16).replace(" ", "T"));
    }
  }

  return (
    <div className="vg-live-page">
      <div className="vg-live-head">
        <div>
          <div className="vg-live-eyebrow">VISIONGUARD AI · NVR COMMAND CENTER</div>
          <h1>Live View & Playback</h1>
          <p>Select an NVR first. Its complete discovered camera list is loaded automatically.</p>
        </div>
        <button className="vg-live-refresh" onClick={loadNvrs}>↻ Refresh NVRs</button>
      </div>

      <div className="vg-nvr-strip">
        {nvrs.map(n => (
          <button key={n.id} className={`vg-nvr-card ${selectedNvr?.id === n.id ? "active" : ""}`} onClick={() => setSelectedNvr(n)}>
            <span className={`vg-dot ${String(n.status).toUpperCase() === "ONLINE" ? "online" : "offline"}`} />
            <strong>{n.name}</strong><small>{n.ip}:{n.port}</small>
            <em>{n.camera_count ?? "—"} cameras · {n.status || "UNKNOWN"}</em>
          </button>
        ))}
      </div>

      {message && <div className="vg-live-message">⚠ {message}</div>}

      <div className="vg-live-layout">
        <aside className="vg-camera-panel">
          <div className="vg-panel-title"><div><b>{selectedNvr?.name || "Select NVR"}</b><span>{cameras.length} discovered cameras</span></div></div>
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search camera / IP / channel…" />
          <div className="vg-camera-list">
            {filtered.map(c => (
              <button key={`${c.nvr}-${c.id}`} className={`vg-camera-row ${selected?.id === c.id ? "active" : ""}`} onClick={() => { setSelected(c); setMode("live"); setDiagnostics(null); setStreamNonce(n => n + 1); setStreamRetrying(false); }}>
                <span className="vg-cam-number">CH-{c.id}</span>
                <span className="vg-cam-main"><b>{c.name || "Unnamed Camera"}</b><small>{c.ip || "No IP"}</small></span>
                <span className={`vg-cam-status ${String(c.status).toLowerCase().includes("off") ? "bad" : "good"}`}>{c.status || "UNKNOWN"}</span>
              </button>
            ))}
            {!filtered.length && <div className="vg-empty">No cameras found for this NVR.</div>}
          </div>
        </aside>

        <main className="vg-viewer-panel">
          <div className="vg-viewer-toolbar">
            <div><b>{selected ? selected.name : "No camera selected"}</b><span>{selected ? `${selected.nvr} · CH-${selected.id} · ${selected.ip}` : "Choose a camera from the left"}</span></div>
            <div className="vg-toolbar-actions">
              <button className={mode === "live" ? "selected" : ""} onClick={() => setMode("live")} disabled={!selected}>● Live</button>
              <button className={mode === "playback" ? "selected" : ""} onClick={() => { setMode("playback"); if (!recordings.length) searchRecordings(); }} disabled={!selected || loading}>▶ Playback</button>
              <button onClick={snapshot} disabled={!selected}>⇩ Snapshot</button>
              <button onClick={() => { if (!selected || !selectedNvr) return; window.open(`${BASE}/live/recordings/download/${selectedNvr.id}/${selected.id}?start=${encodeURIComponent(start.replace("T", " ") + ":00")}&end=${encodeURIComponent(end.replace("T", " ") + ":00")}`, "_blank"); }} disabled={!selected}>⬇ Clip</button>
              <button onClick={inspect} disabled={!selected}>✦ AI Diagnose</button>
            </div>
          </div>

          <div className="vg-video-shell">
            {selected && mode === "live" && (
              <div className="vg-live-stream-wrap">
                {streamRetrying && <div className="vg-stream-status">Connecting to camera…</div>}
                <img
                  key={streamUrl}
                  src={streamUrl}
                  alt={`${selected.name} live stream`}
                  onLoad={() => setStreamRetrying(false)}
                  onError={() => {
                    setStreamRetrying(true);
                    window.setTimeout(() => setStreamNonce(n => n + 1), 1200);
                  }}
                />
              </div>
            )}
            {selected && mode === "playback" && recordings.length > 0 && <video key={playbackUrl} className="vg-playback-video" src={playbackUrl} controls autoPlay playsInline preload="auto" onError={() => setMessage("Playback could not start. The NVR returned a recording URI that FFmpeg/browser could not open. Try Search Recordings again or select another segment.")} />}
            {!selected && <div className="vg-video-empty"><span>◉</span><b>Select a camera</b><small>Choose NVR → camera to start live monitoring.</small></div>}
            {selected && mode === "playback" && !recordings.length && <div className="vg-video-empty"><span>▶</span><b>No playback segment selected</b><small>Choose a time range and press Search Recordings.</small></div>}
          </div>

          <div className="vg-control-row">
            <label>Audio <input type="range" min="0" max="100" value={volume} onChange={e => setVolume(e.target.value)} /><b>{volume}%</b></label>
            <span className="vg-audio-note">MJPEG live proxy carries video only; audio is enabled only when the NVR exposes a browser-compatible audio stream.</span>
          </div>

          <section className="vg-playback-box">
            <div className="vg-section-head"><div><b>Recording Search</b><span>Search finalized NVR recording segments without treating indexing delay as loss.</span></div></div>
            <div className="vg-time-grid"><label>From<input type="datetime-local" value={start} onChange={e => setStart(e.target.value)} /></label><label>To<input type="datetime-local" value={end} onChange={e => setEnd(e.target.value)} /></label><button onClick={searchRecordings} disabled={!selected || loading}>🔎 Search Recordings</button></div>
            {recordings.length > 0 && <div className="vg-recordings">{recordings.map((r, i) => <button key={`${r.start_time}-${i}`} onClick={() => openPlayback(r)}><b>Segment {i + 1}</b><span>{fmt(r.start_time)} → {fmt(r.end_time)}</span><small>Track {r.track_id}</small></button>)}</div>}
          </section>

          {diagnostics && <section className="vg-diagnostics"><div className="vg-section-head"><div><b>AI Health Diagnosis</b><span>Rule-based diagnosis from live NVR telemetry and storage data.</span></div></div><div className="vg-metrics"><span>CPU <b>{fmt(diagnostics.health?.cpu_percent)}{diagnostics.health?.cpu_percent != null ? "%" : ""}</b></span><span>Memory <b>{fmt(diagnostics.health?.memory_percent)}{diagnostics.health?.memory_percent != null ? "%" : ""}</b></span><span>Temperature <b>{fmt(diagnostics.health?.temperature_c)}{diagnostics.health?.temperature_c != null ? "°C" : ""}</b></span><span>HDDs <b>{diagnostics.storage?.hdds?.length ?? 0}</b></span></div><div className="vg-issues">{diagnostics.issues?.map((x,i)=><div key={i}>• {x}</div>)}</div></section>}
        </main>
      </div>
    </div>
  );
}

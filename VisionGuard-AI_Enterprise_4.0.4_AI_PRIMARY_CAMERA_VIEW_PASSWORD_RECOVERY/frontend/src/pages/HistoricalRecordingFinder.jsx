import { useState } from "react";
import api from "../services/api";
import "./HistoricalRecordingFinder.css";

function todayAt(offsetDays = 0) {
  const d = new Date(); d.setDate(d.getDate() + offsetDays);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function fmtDuration(sec) {
  const s = Number(sec || 0); const h = Math.floor(s / 3600); const m = Math.floor((s % 3600) / 60); const r = Math.floor(s % 60);
  return h ? `${h}h ${m}m` : `${m}m ${r}s`;
}

export default function HistoricalRecordingFinder() {
  const [cameraName, setCameraName] = useState("");
  const [date, setDate] = useState(todayAt());
  const [from, setFrom] = useState("00:00");
  const [to, setTo] = useState("23:59");
  const [historyFrom, setHistoryFrom] = useState(todayAt(-7));
  const [historyTo, setHistoryTo] = useState(todayAt());
  const [data, setData] = useState(null); const [history, setHistory] = useState(null); const [timeline, setTimeline] = useState(null); const [gaps, setGaps] = useState(null);
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(""); const [playing, setPlaying] = useState(null);
  const [tab, setTab] = useState("finder");

  function validateName() { const n = cameraName.trim(); if (!n) { setMessage("Enter a camera name."); return null; } return n; }
  async function search() {
    const name = validateName(); if (!name || !date) return;
    setBusy(true); setMessage(""); setData(null); setPlaying(null);
    try { const r = await api.get("/historical-recordings/search", { params: { camera_name: name, start: `${date} ${from}:00`, end: `${date} ${to}:00` } }); setData(r.data); if (!r.data?.results?.some(x => x.recording_found)) setMessage(`No recording found for "${name}" in the selected period.`); }
    catch (e) { setMessage(e.response?.data?.detail || e.message || "Historical recording search failed."); } finally { setBusy(false); }
  }
  async function searchHistory() {
    const name = validateName(); if (!name || !historyFrom || !historyTo) return;
    setBusy(true); setMessage(""); setHistory(null); setTimeline(null);
    try {
      const [r, t] = await Promise.all([
        api.get("/historical-recordings/history", { params: { camera_name: name, start_date: historyFrom, end_date: historyTo } }),
        api.get("/historical-recordings/timeline", { params: { camera_name: name, start: `${historyFrom} 00:00:00`, end: `${historyTo} 23:59:59` } })
      ]);
      setHistory(r.data); setTimeline(t.data);
    }
    catch (e) { setMessage(e.response?.data?.detail || e.message || "Camera history search failed."); } finally { setBusy(false); }
  }
  async function checkGaps() {
    const name = validateName(); if (!name) return;
    setBusy(true); setMessage(""); setGaps(null);
    try { const r = await api.get("/historical-recordings/gaps", { params: { camera_name: name, start: `${date} ${from}:00`, end: `${date} ${to}:00`, gap_minutes: 10 } }); setGaps(r.data); }
    catch (e) { setMessage(e.response?.data?.detail || e.message || "Recording gap check failed."); } finally { setBusy(false); }
  }
  function openPlayback(item) { const first = item.results?.[0]; if (!first) return; setPlaying({ ...item, start: first.start_time, end: first.end_time }); }

  return <div className="hrf-page">
    <div className="hrf-head"><div><div className="hrf-eyebrow">VISIONGUARD AI · RECORDING INTELLIGENCE</div><h1>Historical Recording Finder</h1><p>Find any camera across all connected NVRs — smart matching ignores case, spaces and punctuation.</p></div><div className="hrf-head-tools"><div className="hrf-badge">ALL NVRs</div><div className="hrf-smart-note">Smart match: <b>B2C1</b> = <b>B2C-1</b></div></div></div>
    <div className="hrf-tabs">
      <button className={tab === "finder" ? "active" : ""} onClick={() => setTab("finder")}>🔎 Find Recording</button>
      <button className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>🗓 Camera History</button>
      <button className={tab === "gaps" ? "active" : ""} onClick={() => setTab("gaps")}>⚠ Recording Gaps</button>
    </div>

    {tab === "finder" && <>
      <div className="hrf-search-card"><div className="hrf-field camera-field"><label>Camera Name</label><input autoFocus value={cameraName} onChange={e => setCameraName(e.target.value)} onKeyDown={e => e.key === "Enter" && search()} placeholder="Example: B2C1 / Dispatch Gate / CAM27" /></div><div className="hrf-field"><label>Date</label><input type="date" value={date} onChange={e => setDate(e.target.value)} /></div><div className="hrf-field small"><label>From</label><input type="time" value={from} onChange={e => setFrom(e.target.value)} /></div><div className="hrf-field small"><label>To</label><input type="time" value={to} onChange={e => setTo(e.target.value)} /></div><button className="hrf-search-btn" onClick={search} disabled={busy}>{busy ? "Searching…" : "🔎 Smart Search All NVRs"}</button></div>
      {data && <><div className="hrf-summary"><div><span>Camera</span><strong>{data.camera_name}</strong></div><div><span>NVRs searched</span><strong>{data.searched_nvr_count}</strong></div><div><span>Matching channels</span><strong>{data.matched_channels}</strong></div><div><span>Match</span><strong>{data.historical_mapping_used ? "Historical mapping" : (data.exact_match ? "Exact name" : "Name contains query")}</strong></div></div><div className="hrf-results"><div className="hrf-results-title"><div><h2>Recording Locations</h2><span>Only matching camera channels are searched for recordings.</span></div></div>{data.results.length === 0 ? <div className="hrf-empty">Camera name was not found on any configured NVR.</div> : <div className="hrf-table-wrap"><table><thead><tr><th>NVR</th><th>Camera Name</th><th>Channel</th><th>Mapping</th><th>Valid During</th><th>Movement</th><th>Recording</th><th>Available Range</th><th></th></tr></thead><tbody>{data.results.map(item => <tr key={`${item.nvr_id}-${item.channel}`}><td><b>{item.nvr}</b><small>{item.nvr_ip}</small></td><td>{item.camera_name}</td><td><span className="channel-pill">CH-{item.channel}</span></td><td><span className={`mapping-pill ${item.mapping_source === "movement-history" || item.mapping_source === "device-registry" ? "historical" : "current"}`}>{item.mapping_source === "movement-history" ? "Historical move" : item.mapping_source === "device-registry" ? "Historical registry" : "Current"}</span></td><td className="valid-cell">{item.valid_from ? `${item.valid_from.replace("T"," ")} → ${item.valid_to ? item.valid_to.replace("T"," ") : "Present"}` : "—"}</td><td className="move-cell">{item.moved_from ? <><b>{item.moved_from}</b><small>→ {item.moved_to || "Current"}</small></> : "—"}</td><td><span className={`record-pill ${item.recording_found ? "found" : "not-found"}`}>{item.recording_found ? `✓ FOUND (${item.recording_count})` : "— Not found"}</span></td><td className="range-cell">{item.first_recording ? `${item.first_recording} → ${item.last_recording}` : "—"}</td><td>{item.recording_found && <button className="view-btn" onClick={() => openPlayback(item)}>▶ Open Recording</button>}</td></tr>)}</tbody></table></div>}</div></>}
    </>}

    {tab === "history" && <><div className="hrf-search-card"><div className="hrf-field camera-field"><label>Camera Name</label><input value={cameraName} onChange={e => setCameraName(e.target.value)} placeholder="Any camera name" /></div><div className="hrf-field"><label>From Date</label><input type="date" value={historyFrom} onChange={e => setHistoryFrom(e.target.value)} /></div><div className="hrf-field"><label>To Date</label><input type="date" value={historyTo} onChange={e => setHistoryTo(e.target.value)} /></div><button className="hrf-search-btn" onClick={searchHistory} disabled={busy}>{busy ? "Scanning…" : "🗓 Find Camera History"}</button></div>{timeline && <div className="hrf-timeline-card"><div className="hrf-timeline-head"><div><h2>Camera Movement Timeline</h2><span>Confirmed NVR/channel assignment intervals used for date-wise recording search.</span></div><b>{timeline.count} assignment(s)</b></div>{timeline.timeline.length ? <div className="hrf-timeline">{timeline.timeline.map((x,i) => <div className="timeline-row" key={`${x.identity}-${x.valid_from}-${i}`}><div className="timeline-dot"></div><div className="timeline-main"><div className="timeline-top"><strong>{x.nvr} · CH-{x.channel}</strong><span>{x.source === "confirmed-move" ? "CONFIRMED MOVE" : "ASSIGNMENT"}</span></div><div className="timeline-time">{String(x.valid_from || "").replace("T"," ")} → {x.valid_to ? String(x.valid_to).replace("T"," ") : "Present"}</div>{x.moved_from && <div className="timeline-move">{x.moved_from} → {x.moved_to}</div>}</div></div>)}</div> : <div className="hrf-empty">No confirmed movement timeline exists for this camera in the selected period. Future moves will be tracked automatically.</div>}</div>}{history && <div className="hrf-history-grid">{history.days.map(day => <div className={`history-day ${day.found ? "found" : "missing"}`} key={day.date}><div><b>{day.date}</b><span>{day.found ? "FOUND" : "NOT FOUND"}</span></div>{day.locations.length ? day.locations.map((x, i) => <div className="history-location" key={`${x.nvr_id}-${x.channel}-${i}`}><strong>{x.nvr}</strong><span>CH-{x.channel}</span><small>{x.first_recording || "—"} → {x.last_recording || "—"}</small></div>) : <p>No recording evidence</p>}</div>)}</div>}</>}

    {tab === "gaps" && <><div className="hrf-search-card"><div className="hrf-field camera-field"><label>Camera Name</label><input value={cameraName} onChange={e => setCameraName(e.target.value)} placeholder="Any camera name" /></div><div className="hrf-field"><label>Date</label><input type="date" value={date} onChange={e => setDate(e.target.value)} /></div><div className="hrf-field small"><label>From</label><input type="time" value={from} onChange={e => setFrom(e.target.value)} /></div><div className="hrf-field small"><label>To</label><input type="time" value={to} onChange={e => setTo(e.target.value)} /></div><button className="hrf-search-btn" onClick={checkGaps} disabled={busy}>{busy ? "Checking…" : "⚠ Check Recording Gaps"}</button></div>{gaps && <div className="hrf-gap-grid">{gaps.locations.map(x => <div className="gap-card" key={`${x.nvr_id}-${x.channel}`}><div className="gap-head"><div><b>{x.nvr}</b><span>CH-{x.channel}</span></div><strong>{x.gaps.length ? `⚠ ${x.gaps.length} gap(s)` : "✓ Continuous"}</strong></div><div className="gap-stat"><span>Clips</span><b>{x.clip_count}</b><span>Largest gap</span><b>{x.largest_gap_seconds ? fmtDuration(x.largest_gap_seconds) : "—"}</b></div>{x.gaps.slice(0, 8).map((g, i) => <div className="gap-row" key={i}><span>{g.from}</span><b>{fmtDuration(g.duration_seconds)}</b><span>{g.to}</span></div>)}</div>)}{!gaps.locations.length && <div className="hrf-empty">No recording evidence found for this camera in the selected period.</div>}</div>}</>}

    {busy && <div className="hrf-progress"><span className="hrf-spinner" />Checking configured NVRs…</div>}
    {message && <div className="hrf-message">{message}</div>}
    {playing && <div className="hrf-player"><div className="hrf-player-head"><div><b>{playing.camera_name}</b><span>{playing.nvr} · CH-{playing.channel}</span></div><button onClick={() => setPlaying(null)}>✕</button></div><video controls autoPlay src={`${api.defaults.baseURL}/live/playback/${playing.nvr_id}/${playing.channel}?start=${encodeURIComponent(String(playing.start).replace(" ", "T"))}&end=${encodeURIComponent(String(playing.end).replace(" ", "T"))}`} /></div>}
  </div>;
}

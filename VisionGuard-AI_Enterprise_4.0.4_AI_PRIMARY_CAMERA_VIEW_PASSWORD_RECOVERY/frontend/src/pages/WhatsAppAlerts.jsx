import { useEffect, useState } from "react";
import api from "../services/api";
import "./WhatsAppAlerts.css";

export default function WhatsAppAlerts() {
  const [cfg, setCfg] = useState({ enabled: false, to: "919548749677", phone_number_id: "", has_token: false, configured: false });
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const load = async () => {
    try { const r = await api.get("/whatsapp/config"); setCfg(r.data || cfg); }
    catch (e) { setErr(e.response?.data?.detail || e.message || "Unable to load WhatsApp settings"); }
  };
  useEffect(() => { load(); }, []);

  const save = async () => {
    setBusy(true); setMsg(""); setErr("");
    try {
      const r = await api.put("/whatsapp/config", { ...cfg, token });
      setCfg(r.data); setToken(""); setMsg("WhatsApp alert settings saved.");
    } catch (e) { setErr(e.response?.data?.detail || e.message || "Unable to save WhatsApp settings"); }
    finally { setBusy(false); }
  };

  const test = async () => {
    setBusy(true); setMsg(""); setErr("");
    try { await api.post("/whatsapp/test"); setMsg("✅ Test WhatsApp alert sent."); }
    catch (e) { setErr(e.response?.data?.detail || e.message || "WhatsApp test failed"); }
    finally { setBusy(false); }
  };

  return <div className="vg-page whatsapp-page">
    <div className="vg-page-header">
      <div><div className="vg-eyebrow">ALERT CHANNEL</div><h1>WhatsApp Alerts</h1><p>Send VisionGuard NVR, camera, angle and recovery alerts to the configured WhatsApp number.</p></div>
      <div className={`wa-status ${cfg.configured && cfg.enabled ? "on" : "off"}`}>{cfg.configured && cfg.enabled ? "● ACTIVE" : "● NOT CONFIGURED"}</div>
    </div>
    {msg && <div className="wa-banner success">{msg}</div>}
    {err && <div className="wa-banner error">{err}</div>}
    <section className="wa-card">
      <div className="wa-card-title"><div><div className="vg-eyebrow">WHATSAPP DELIVERY</div><h2>Alert destination</h2><p>Default recipient is <b>+91 9548749677</b>.</p></div><label className="wa-switch"><input type="checkbox" checked={!!cfg.enabled} onChange={e=>setCfg({...cfg, enabled:e.target.checked})}/><span></span></label></div>
      <div className="wa-grid">
        <label>Recipient number<input value={cfg.to || ""} onChange={e=>setCfg({...cfg,to:e.target.value})} placeholder="919548749677"/></label>
        <label>Meta WhatsApp Phone Number ID<input value={cfg.phone_number_id || ""} onChange={e=>setCfg({...cfg,phone_number_id:e.target.value})} placeholder="Phone Number ID"/></label>
        <label className="wide">Meta access token<input type="password" value={token} onChange={e=>setToken(e.target.value)} placeholder={cfg.has_token ? "Token already saved — leave blank to keep it" : "Paste Meta Cloud API token"}/></label>
      </div>
      <div className="wa-actions"><button onClick={save} disabled={busy}>{busy ? "Saving…" : "SAVE SETTINGS"}</button><button className="secondary" onClick={test} disabled={busy || !cfg.configured}>SEND TEST</button></div>
      <div className="wa-note"><b>Important:</b> the phone number alone cannot authorize WhatsApp delivery. Meta WhatsApp Cloud API credentials (Phone Number ID + access token) are required. Existing email alerts continue independently.</div>
    </section>
    <section className="wa-card compact"><h2>Events sent to WhatsApp</h2><div className="wa-events"><span>🔴 NVR DOWN</span><span>🟢 NVR RECOVERY</span><span>📹 Camera Offline/Recovery</span><span>↪ Camera Angle Change</span><span>⚠ Video / Storage / Network alerts</span></div></section>
  </div>;
}

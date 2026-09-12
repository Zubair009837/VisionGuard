import { useEffect, useMemo, useState } from "react";
import api from "../services/api";
import "./Settings.css";

const SECTIONS = [
  { key: "device", label: "Device Info", icon: "▣", endpoint: "/ISAPI/System/deviceInfo", readOnly: true },
  { key: "network", label: "Network", icon: "⌁", endpoint: "/ISAPI/System/Network/interfaces" },
  { key: "time", label: "Date & Time", icon: "◷", endpoint: "/ISAPI/System/time" },
  { key: "capabilities", label: "Capabilities", icon: "✓", endpoint: "/ISAPI/System/capabilities", readOnly: true },
];

const getNodes = (doc, name) => Array.from(doc.getElementsByTagNameNS("*", name));
const getValue = (doc, name, fallback = "") => getNodes(doc, name)[0]?.textContent?.trim() || fallback;
const setValue = (doc, name, value, index = 0) => {
  const node = getNodes(doc, name)[index];
  if (node) node.textContent = value ?? "";
};
const parseXml = (xml) => {
  const doc = new DOMParser().parseFromString(xml || "", "application/xml");
  if (doc.querySelector("parsererror")) throw new Error("NVR returned invalid XML");
  return doc;
};
const serializeXml = (doc) => new XMLSerializer().serializeToString(doc);

function inputValue(value) { return value ?? ""; }

export default function Settings() {
  const [nvrs, setNvrs] = useState([]);
  const [selectedIds, setSelectedIds] = useState([1]);
  const [section, setSection] = useState("device");
  const [rawByNvr, setRawByNvr] = useState({});
  const [forms, setForms] = useState({});
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [advancedEndpoint, setAdvancedEndpoint] = useState("/ISAPI/System/deviceInfo");
  const [advancedXml, setAdvancedXml] = useState("");
  const [showNvrPicker, setShowNvrPicker] = useState(false);

  const selectedNvrs = useMemo(() => nvrs.filter(n => selectedIds.includes(Number(n.id))), [nvrs, selectedIds]);
  const selectedCount = selectedIds.length;
  const activeSection = SECTIONS.find(x => x.key === section);

  useEffect(() => {
    api.get("/nvr/status").then(r => {
      const data = Array.isArray(r.data) ? r.data : [];
      const normalized = Array.from({ length: 12 }, (_, i) => data.find(n => Number(n.id) === i + 1) || { id: i + 1, name: `NVR-${i + 1}` });
      setNvrs(normalized);
    }).catch(() => setNvrs(Array.from({ length: 12 }, (_, i) => ({ id: i + 1, name: `NVR-${i + 1}` }))));
  }, []);

  useEffect(() => {
    if (!selectedIds.length) return;
    loadSection(section, selectedIds);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section, selectedIds.join(",")]);

  async function loadSection(nextSection = section, ids = selectedIds) {
    if (!ids.length) return;
    setLoading(true); setError(""); setMessage("");
    try {
      const responses = await Promise.all(ids.map(async (id) => {
        const r = await api.get(`/nvr/${id}/settings`, { params: { section: nextSection } });
        return [id, r.data?.body || ""];
      }));
      const raw = Object.fromEntries(responses);
      setRawByNvr(raw);
      const nextForms = {};
      for (const [id, xml] of responses) {
        const doc = parseXml(xml);
        if (nextSection === "network") {
          nextForms[id] = {
            ip: getValue(doc, "ipAddress"),
            subnet: getValue(doc, "subnetMask"),
            gateway: getValue(doc, "ipAddress", ""),
            dns1: getValue(doc, "ipAddress", ""),
            dns2: getValue(doc, "ipAddress", ""),
            _gateway: getValue(doc, "ipAddress", ""),
            _dns1: getValue(doc, "ipAddress", ""),
            _dns2: getValue(doc, "ipAddress", ""),
          };
          // The NVR response contains several ipAddress nodes; use explicit parents.
          nextForms[id].gateway = getNodes(doc, "DefaultGateway")[0] ? getValue(getNodes(doc, "DefaultGateway")[0].ownerDocument, "ipAddress") : "";
          const gateways = getNodes(doc, "DefaultGateway");
          if (gateways[0]) nextForms[id].gateway = gateways[0].getElementsByTagNameNS("*", "ipAddress")[0]?.textContent?.trim() || "";
          const dns = getNodes(doc, "PrimaryDNS");
          const dns2 = getNodes(doc, "SecondaryDNS");
          nextForms[id].dns1 = dns[0]?.getElementsByTagNameNS("*", "ipAddress")[0]?.textContent?.trim() || "";
          nextForms[id].dns2 = dns2[0]?.getElementsByTagNameNS("*", "ipAddress")[0]?.textContent?.trim() || "";
        } else if (nextSection === "time") {
          nextForms[id] = {
            mode: getValue(doc, "timeMode", "NTP"),
            localTime: getValue(doc, "localTime"),
            timezone: getValue(doc, "timeZone", "CST+5:30:00"),
          };
        } else if (nextSection === "device") {
          nextForms[id] = {
            name: getValue(doc, "deviceName"), model: getValue(doc, "model"), serial: getValue(doc, "serialNumber"),
            firmware: getValue(doc, "firmwareVersion"), mac: getValue(doc, "macAddress"), manufacturer: getValue(doc, "manufacturer"),
          };
        }
      }
      setForms(nextForms);
      setAdvancedEndpoint(activeSection?.endpoint || advancedEndpoint);
      if (nextSection === "advanced") setAdvancedXml(responses[0]?.[1] || "");
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Unable to load NVR settings");
    } finally { setLoading(false); }
  }

  function toggleNvr(id) {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id].sort((a,b) => a-b));
  }

  function selectAll() { setSelectedIds(nvrs.map(n => Number(n.id))); }
  function clearAll() { setSelectedIds([]); }

  function updateForm(id, key, value) {
    setForms(prev => ({ ...prev, [id]: { ...(prev[id] || {}), [key]: value } }));
  }

  function buildXmlForNvr(id) {
    const xml = rawByNvr[id];
    const form = forms[id] || {};
    const doc = parseXml(xml);
    if (section === "network") {
      setValue(doc, "ipAddress", form.ip);
      setValue(doc, "subnetMask", form.subnet);
      const gateway = getNodes(doc, "DefaultGateway")[0]?.getElementsByTagNameNS("*", "ipAddress")[0];
      if (gateway) gateway.textContent = form.gateway;
      const dns1 = getNodes(doc, "PrimaryDNS")[0]?.getElementsByTagNameNS("*", "ipAddress")[0];
      const dns2 = getNodes(doc, "SecondaryDNS")[0]?.getElementsByTagNameNS("*", "ipAddress")[0];
      if (dns1) dns1.textContent = form.dns1;
      if (dns2) dns2.textContent = form.dns2;
    }
    if (section === "time") {
      setValue(doc, "timeMode", form.mode);
      setValue(doc, "localTime", form.localTime);
      setValue(doc, "timeZone", form.timezone);
    }
    return serializeXml(doc);
  }

  async function saveSettings() {
    if (activeSection?.readOnly) return;
    if (!selectedIds.length) { setError("Select at least one NVR."); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      const items = selectedIds.map(id => ({ nvr_id: id, name: `NVR-${id}`, endpoint: activeSection.endpoint, xml: buildXmlForNvr(id) }));
      const r = await api.put("/nvr/bulk/settings", { items });
      const result = r.data;
      setMessage(`${result.succeeded}/${result.total} NVRs updated successfully. ${result.failed ? `${result.failed} failed.` : ""}`);
      if (result.failed) setError(result.results.filter(x => !x.success).map(x => `${x.nvr}: ${x.error}`).join(" | "));
      await loadSection(section, selectedIds);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "NVR rejected the change");
    } finally { setSaving(false); }
  }

  async function loadAdvanced() {
    if (selectedCount !== 1) { setError("Advanced ISAPI is opened for one NVR at a time. Select one NVR first."); return; }
    setLoading(true); setError("");
    try {
      const id = selectedIds[0];
      const response = await api.get(`/nvr/${id}/settings`, { params: { section: "advanced", endpoint: advancedEndpoint } });
      setAdvancedXml(response.data?.body || "");
    } catch (err) { setError(err.response?.data?.detail || err.message || "Unable to load advanced settings"); }
    finally { setLoading(false); }
  }

  async function saveAdvanced() {
    if (!advancedEndpoint.startsWith("/ISAPI/")) { setError("Endpoint must start with /ISAPI/"); return; }
    if (!advancedXml) { setError("Advanced XML is empty."); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      const items = selectedIds.map(id => ({ nvr_id: id, name: `NVR-${id}`, endpoint: advancedEndpoint, xml: advancedXml }));
      const r = await api.put("/nvr/bulk/settings", { items });
      setMessage(`Advanced ISAPI applied: ${r.data.succeeded}/${r.data.total} NVRs succeeded.`);
      if (r.data.failed) setError(r.data.results.filter(x => !x.success).map(x => `${x.nvr}: ${x.error}`).join(" | "));
    } catch (err) { setError(err.response?.data?.detail || err.message || "Advanced update failed"); }
    finally { setSaving(false); }
  }

  async function syncTimeSelected() {
    if (!selectedIds.length) { setError("Select at least one NVR."); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      const r = await api.post("/nvr-control/time/sync-selected", { nvr_ids: selectedIds });
      setMessage(`Time sync completed: ${r.data.succeeded}/${r.data.total} NVRs succeeded.`);
      if (r.data.failed) {
        setError((r.data.results || []).filter(x => !x.ok).map(x => `${x.nvr}: ${x.error || "sync failed"}`).join(" | "));
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Time sync failed");
    } finally { setSaving(false); }
  }

  async function rebootSelected() {
    if (!selectedIds.length) { setError("Select at least one NVR."); return; }
    if (!window.confirm(`Reboot ${selectedIds.length} selected NVR${selectedIds.length > 1 ? "s" : ""}? Recording/live view will be interrupted.`)) return;
    setSaving(true); setError(""); setMessage("");
    const results = await Promise.allSettled(selectedIds.map(id => api.post(`/nvr/${id}/reboot`)));
    const ok = results.filter(x => x.status === "fulfilled").length;
    setMessage(`${ok}/${selectedIds.length} reboot command${selectedIds.length > 1 ? "s" : ""} accepted.`);
    setSaving(false);
  }

  return (
    <div className="vg-settings-page">
      <div className="vg-settings-header">
        <div><div className="vg-eyebrow">NVR CONFIGURATION CENTER</div><h1>Settings Control</h1><p>Configure one NVR, multiple NVRs, or all nine from one controlled workspace.</p></div>
        <div style={{display:"flex",gap:"10px",flexWrap:"wrap"}}><button className="vg-apply-btn" onClick={syncTimeSelected} disabled={saving || !selectedIds.length}>🕐 Sync Time Selected</button><button className="vg-danger-btn" onClick={rebootSelected} disabled={saving}>↻ Reboot Selected</button></div>
      </div>

      <div className="vg-selection-panel">
        <div className="vg-selection-top">
          <div><span className="vg-label">TARGET NVRs</span><strong>{selectedCount} selected</strong></div>
          <div className="vg-selection-actions"><button onClick={selectAll}>Select All 9</button><button onClick={clearAll}>Clear</button><button className="vg-picker-toggle" onClick={() => setShowNvrPicker(v => !v)}>{showNvrPicker ? "Hide NVR List" : "Choose NVRs"} ▾</button></div>
        </div>
        <div className="vg-selected-chips">
          {selectedNvrs.length ? selectedNvrs.map(n => <span key={n.id} className="vg-nvr-chip"><i className={String(n.status).toUpperCase() === "ONLINE" ? "online" : "offline"} />{n.name || `NVR-${n.id}`}<button onClick={() => toggleNvr(Number(n.id))}>×</button></span>) : <span className="vg-no-selection">No NVR selected</span>}
        </div>
        {showNvrPicker && <div className="vg-nvr-picker">{nvrs.map(n => {
          const id = Number(n.id), checked = selectedIds.includes(id), online = String(n.status).toUpperCase() === "ONLINE";
          return <label key={id} className={`vg-nvr-option ${checked ? "selected" : ""}`}><input type="checkbox" checked={checked} onChange={() => toggleNvr(id)} /><span className={`vg-picker-dot ${online ? "online" : "offline"}`} /><span className="vg-picker-name">{n.name || `NVR-${id}`}</span><span className="vg-picker-ip">{n.ip || "configured"}</span><span className={`vg-picker-status ${online ? "online" : "offline"}`}>{n.status || "UNKNOWN"}</span></label>;
        })}</div>}
        <div className="vg-selection-note">Changes apply only to the selected NVRs. Unique values such as each NVR IP are preserved independently.</div>
      </div>

      <div className="vg-settings-layout">
        <nav className="vg-settings-nav">
          {SECTIONS.map(item => <button key={item.key} onClick={() => setSection(item.key)} className={section === item.key ? "active" : ""}><span>{item.icon}</span>{item.label}{item.readOnly && <em>READ</em>}</button>)}
        </nav>

        <section className="vg-settings-card">
          <header className="vg-settings-card-head"><div><h2>{activeSection.label}</h2><p>{selectedCount > 1 ? `Bulk configuration • ${selectedCount} NVRs selected` : `Configuration • ${selectedNvrs[0]?.name || `NVR-${selectedIds[0] || 1}`}`}</p></div><span className={`vg-connection ${loading ? "loading" : ""}`}><i />{loading ? "Loading NVR data…" : "Connected via ISAPI"}</span></header>
          <div className="vg-settings-body">
            {error && <div className="vg-alert error">⚠ {error}</div>}
            {message && <div className="vg-alert success">✓ {message}</div>}

            {section === "device" && <div className="vg-device-grid">{["name","model","serial","firmware","mac","manufacturer"].map(key => <div className="vg-field" key={key}><label>{({name:"Device Name",model:"Model",serial:"Serial Number",firmware:"Firmware Version",mac:"MAC Address",manufacturer:"Manufacturer"})[key]}</label><div className="vg-readonly-value">{selectedIds.length === 1 ? inputValue(forms[selectedIds[0]]?.[key]) || "—" : "Multiple NVRs selected"}</div></div>)}</div>}

            {section === "network" && <div className="vg-bulk-table-wrap"><div className="vg-section-banner"><strong>Network Configuration</strong><span>Each NVR keeps its own IP address. Edit only the values you intend to change.</span></div><table className="vg-config-table"><thead><tr><th>NVR</th><th>IP Address</th><th>Subnet Mask</th><th>Gateway</th><th>Primary DNS</th><th>Secondary DNS</th></tr></thead><tbody>{selectedIds.map(id => <tr key={id}><td><strong>NVR-{id}</strong></td>{["ip","subnet","gateway","dns1","dns2"].map(key => <td key={key}><input value={inputValue(forms[id]?.[key])} onChange={e => updateForm(id,key,e.target.value)} /></td>)}</tr>)}</tbody></table></div>}

            {section === "time" && <div className="vg-bulk-table-wrap"><div className="vg-section-banner"><strong>Date & Time</strong><span>Use the same policy across selected NVRs or fine-tune an individual recorder.</span></div><table className="vg-config-table"><thead><tr><th>NVR</th><th>Mode</th><th>Local Time</th><th>Time Zone</th></tr></thead><tbody>{selectedIds.map(id => <tr key={id}><td><strong>NVR-{id}</strong></td><td><select value={forms[id]?.mode || "NTP"} onChange={e => updateForm(id,"mode",e.target.value)}><option value="NTP">NTP</option><option value="manual">Manual</option></select></td><td><input type="datetime-local" value={(forms[id]?.localTime || "").replace("Z","")} onChange={e => updateForm(id,"localTime",e.target.value)} /></td><td><input value={inputValue(forms[id]?.timezone)} onChange={e => updateForm(id,"timezone",e.target.value)} placeholder="CST+5:30:00" /></td></tr>)}</tbody></table></div>}

            {section === "capabilities" && <div className="vg-capabilities-grid"><div className="vg-capability-note"><strong>Read-only capability inventory</strong><span>These values are reported by each NVR firmware and cannot be safely edited from this screen.</span></div>{selectedIds.map(id => <div className="vg-cap-card" key={id}><strong>NVR-{id}</strong><span>{rawByNvr[id] ? "Capability data received" : "No response"}</span></div>)}</div>}

            {activeSection?.readOnly === false && <div className="vg-save-bar"><div><strong>Ready to apply</strong><span>{selectedCount === 1 ? "Changes will be sent to the selected NVR." : `Changes will be sent independently to all ${selectedCount} selected NVRs.`}</span></div><button className="vg-apply-btn" onClick={saveSettings} disabled={saving || loading || !selectedIds.length}>{saving ? "Applying…" : `Apply to ${selectedCount} NVR${selectedCount === 1 ? "" : "s"}`}</button></div>}
          </div>
        </section>
      </div>

      <section className="vg-advanced-card">
        <div className="vg-advanced-head"><div><span className="vg-eyebrow">EXPERT MODE</span><h2>Advanced ISAPI</h2><p>Raw XML remains available for supported Hikvision endpoints when a standard control is not enough.</p></div><span className="vg-warning-tag">ADMIN / ADVANCED</span></div>
        <div className="vg-advanced-controls"><input value={advancedEndpoint} onChange={e => setAdvancedEndpoint(e.target.value)} placeholder="/ISAPI/System/..." /><button onClick={loadAdvanced} disabled={loading}>Load</button><button className="primary" onClick={saveAdvanced} disabled={saving || !advancedXml}>Apply to Selected</button></div>
        <textarea value={advancedXml} onChange={e => setAdvancedXml(e.target.value)} spellCheck="false" placeholder="Load an ISAPI endpoint to inspect its XML response..." />
      </section>
    </div>
  );
}

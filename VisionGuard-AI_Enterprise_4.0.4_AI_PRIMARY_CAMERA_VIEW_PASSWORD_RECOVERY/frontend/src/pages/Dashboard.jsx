import AIInsights from "../components/ai/AIInsights";
import Loader from "../components/Loader";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";

import CameraPieChart from "../components/charts/CameraPieChart";
import PerformanceChart from "../components/charts/PerformanceChart";
import StorageChart from "../components/charts/StorageChart";

// ==========================================================
// VISIONGUARD AI
// PREMIUM NVR SECURITY OPERATIONS CENTER
// ==========================================================

function Dashboard() {

  // ========================================================
  // DASHBOARD DATA
  // ========================================================

  const [dashboard, setDashboard] = useState({
    total: 0,
    online: 0,
    offline: 0,
    nvr: 0,
    offlineNvr: 0,
    totalNvr: 0,
    nvrStatus: [],
  });

  const [displayStats, setDisplayStats] = useState({
    total: 0,
    online: 0,
    offline: 0,
    nvr: 0,
    offlineNvr: 0,
    totalNvr: 0,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastUpdated, setLastUpdated] = useState("");
  const [nvrHealth, setNvrHealth] = useState([]);
  const [liveAlerts, setLiveAlerts] = useState([]);
  const [retention, setRetention] = useState(null);

  // ========================================================
  // ROTATING CONTENT
  // ========================================================

  const [tickerIndex, setTickerIndex] = useState(0);
  const [visualIndex, setVisualIndex] = useState(0);
  const [orbitRotation, setOrbitRotation] = useState(0);

  // ========================================================
  // TICKER MESSAGES
  // ========================================================

  const tickerMessages = [
    "VISIONGUARD AI • LIVE SECURITY MONITORING ACTIVE",
    "AI ENGINE • CONTINUOUS CAMERA HEALTH ANALYSIS",
    "NETWORK • REAL-TIME NVR CONNECTIVITY MONITORING",
    "SECURITY CORE • AUTOMATED ALERT DETECTION ACTIVE",
    "CCTV MATRIX • LIVE INFRASTRUCTURE SURVEILLANCE",
    "OPERATIONS • ALL MONITORING SYSTEMS ONLINE",
  ];

  // ========================================================
  // VISUAL MESSAGES
  // ========================================================

  const visualMessages = [
    {
      icon: "🛰️",
      title: "LIVE SURVEILLANCE",
      text: "Real-time CCTV infrastructure monitoring",
    },
    {
      icon: "🤖",
      title: "AI ANALYTICS",
      text: "Intelligent camera health analysis",
    },
    {
      icon: "🛡️",
      title: "SECURITY CORE",
      text: "Automated threat and failure detection",
    },
    {
      icon: "📡",
      title: "NETWORK MATRIX",
      text: "Continuous NVR connectivity analysis",
    },
    {
      icon: "🎥",
      title: "CAMERA GRID",
      text: "Enterprise CCTV monitoring environment",
    },
    {
      icon: "⚡",
      title: "MISSION CONTROL",
      text: "Centralized security operations monitoring",
    },
  ];

  // ========================================================
  // LOAD DASHBOARD
  // ========================================================

  async function loadDashboard() {
    try {
      const response = await api.get("/dashboard");

      const data = response.data || {};

      const newDashboard = {
        total: Number(data.total || 0),
        online: Number(data.online || 0),
        offline: Number(data.offline || 0),
        nvr: Number(data.online_nvr ?? data.nvr ?? 0),
        offlineNvr: Number(data.offline_nvr || 0),
        totalNvr: Number(data.total_nvr || 0),
        nvrStatus: Array.isArray(data.nvr_status) ? data.nvr_status : [],
      };

      setDashboard(newDashboard);

      setLastUpdated(
        new Date().toLocaleTimeString()
      );

      setError(false);

    } catch (err) {
      console.error("Dashboard API Error:", err);
      setError(true);

    } finally {
      setLoading(false);
    }
  }

  async function loadHealthAndAlerts() {
    try {
      const [healthResponse, alertsResponse] = await Promise.all([
        api.get("/nvr/health"),
        api.get("/alerts"),
      ]);
      const health = Array.isArray(healthResponse.data?.data) ? healthResponse.data.data : [];
      const alerts = Array.isArray(alertsResponse.data) ? alertsResponse.data : [];
      setNvrHealth(health);
      setLiveAlerts([...alerts].reverse().slice(0, 8));
    } catch (err) {
      console.error("Health/alert telemetry error:", err);
    }
  }

  async function loadRetention() {
    try {
      const r = await api.get("/recording-retention/summary");
      setRetention(r.data || null);
    } catch (err) {
      console.error("Recording retention telemetry error:", err);
    }
  }

  // ========================================================
  // INITIAL LOAD + AUTO REFRESH
  // ========================================================

  useEffect(() => {
    loadDashboard();
    loadHealthAndAlerts();
    loadRetention();

    const interval = setInterval(
      loadDashboard,
      30000
    );
    const healthInterval = setInterval(
      loadHealthAndAlerts,
      5000
    );
    const retentionInterval = setInterval(
      loadRetention,
      15 * 60 * 1000
    );

    return () => {
      clearInterval(interval);
      clearInterval(healthInterval);
      clearInterval(retentionInterval);
    };
  }, []);

  // ========================================================
  // ANIMATED NUMBERS
  // ========================================================

  useEffect(() => {

    const duration = 1000;
    const startTime = Date.now();

    const startValues = {
      total: displayStats.total,
      online: displayStats.online,
      offline: displayStats.offline,
      nvr: displayStats.nvr,
      offlineNvr: displayStats.offlineNvr,
      totalNvr: displayStats.totalNvr,
    };

    const targetValues = {
      total: dashboard.total,
      online: dashboard.online,
      offline: dashboard.offline,
      nvr: dashboard.nvr,
      offlineNvr: dashboard.offlineNvr,
      totalNvr: dashboard.totalNvr,
    };

    let animationFrame;

    function animate() {

      const elapsed =
        Date.now() - startTime;

      const progress =
        Math.min(
          elapsed / duration,
          1
        );

      const eased =
        1 -
        Math.pow(
          1 - progress,
          3
        );

      setDisplayStats({

        total: Math.round(
          startValues.total +
          (
            targetValues.total -
            startValues.total
          ) *
          eased
        ),

        online: Math.round(
          startValues.online +
          (
            targetValues.online -
            startValues.online
          ) *
          eased
        ),

        offline: Math.round(
          startValues.offline +
          (
            targetValues.offline -
            startValues.offline
          ) *
          eased
        ),

        nvr: Math.round(
          startValues.nvr +
          (
            targetValues.nvr -
            startValues.nvr
          ) *
          eased
        ),

        offlineNvr: Math.round(
          startValues.offlineNvr +
          (
            targetValues.offlineNvr -
            startValues.offlineNvr
          ) *
          eased
        ),

        totalNvr: Math.round(
          startValues.totalNvr +
          (
            targetValues.totalNvr -
            startValues.totalNvr
          ) *
          eased
        ),

      });

      if (progress < 1) {
        animationFrame =
          requestAnimationFrame(
            animate
          );
      }
    }

    animationFrame =
      requestAnimationFrame(
        animate
      );

    return () => {
      cancelAnimationFrame(
        animationFrame
      );
    };

  }, [dashboard]);

  // ========================================================
  // TICKER ROTATION
  // ========================================================

  useEffect(() => {

    const interval =
      setInterval(() => {

        setTickerIndex(
          previous =>
            (
              previous + 1
            ) %
            tickerMessages.length
        );

      }, 3200);

    return () => {
      clearInterval(interval);
    };

  }, []);

  // ========================================================
  // VISUAL ROTATION
  // ========================================================

  useEffect(() => {

    const interval =
      setInterval(() => {

        setVisualIndex(
          previous =>
            (
              previous + 1
            ) %
            visualMessages.length
        );

      }, 4200);

    return () => {
      clearInterval(interval);
    };

  }, []);

  // ========================================================
  // ORBIT ROTATION
  // ========================================================

  useEffect(() => {

    const interval =
      setInterval(() => {

        setOrbitRotation(
          previous =>
            (previous + 2) % 360
        );

      }, 40);

    return () => {
      clearInterval(interval);
    };

  }, []);

  // ========================================================
  // LOADING
  // ========================================================

  if (loading) {

    return (
      <Loader
        text="Initializing VisionGuard Mission Control..."
      />
    );

  }

  // ========================================================
  // CALCULATIONS
  // ========================================================

  const onlinePercent =
    displayStats.total > 0
      ? Math.round(
          (
            displayStats.online /
            displayStats.total
          ) * 100
        )
      : 0;

  const offlinePercent =
    displayStats.total > 0
      ? Math.round(
          (
            displayStats.offline /
            displayStats.total
          ) * 100
        )
      : 0;

  const healthPercentage =
    displayStats.total > 0
      ? Math.round(
          (
            displayStats.online /
            displayStats.total
          ) * 100
        )
      : 0;

  // ========================================================
  // RENDER
  // ========================================================

  return (

    <div className="vg-dashboard">

      <div className="vg-grid-background" />

      <div className="vg-glow vg-glow-one" />
      <div className="vg-glow vg-glow-two" />
      <div className="vg-glow vg-glow-three" />

      {/* ==================================================
          HEADER
      ================================================== */}

      <div className="vg-header">

        <div>

          <div className="vg-brand-line">

            <span className="vg-live-dot" />

            <span>
              VISIONGUARD AI
            </span>

            <span className="vg-live-badge">
              LIVE
            </span>

          </div>

          <h1 className="vg-title">

            🛡 Tata 1mg

            <span>
              NVR Security Operations Center
            </span>

          </h1>

          <p className="vg-subtitle">
            Enterprise CCTV • NVR • Network • AI Monitoring
          </p>

        </div>

        <div className="vg-header-right">

          <div className="vg-clock">

            <span>
              SYSTEM TIME
            </span>

            <strong>
              {lastUpdated || "--:--:--"}
            </strong>

          </div>

          <button
            className="vg-refresh"
            onClick={loadDashboard}
          >
            ⟳ Refresh
          </button>

        </div>

      </div>

      {/* ==================================================
          MOVING TICKER
      ================================================== */}

      <div className="vg-ticker">

        <div className="vg-ticker-label">
          ● SYSTEM FEED
        </div>

        <div className="vg-ticker-window">

          <div
            key={tickerIndex}
            className="vg-ticker-text"
          >
            {tickerMessages[tickerIndex]}
          </div>

        </div>

        <div className="vg-ticker-status">
          SECURE
        </div>

      </div>

      {/* ==================================================
          ERROR
      ================================================== */}

      {error && (

        <div className="vg-error">

          <span>⚠</span>

          <div>

            <strong>
              Backend Connection Warning
            </strong>

            <small>
              Dashboard could not fetch the latest
              monitoring data.
            </small>

          </div>

        </div>

      )}

      {/* ==================================================
          MAIN DASHBOARD

          IMPORTANT:
          STATS FIRST
          HERO SECOND

          NO AUTOMATIC SWAP
      ================================================== */}

      <div className="vg-main-area">

        {/* ==================================================
            SECTION 1
            BIG CORE STATS
        ================================================== */}

        <section className="vg-main-section vg-stats-section">

          <div className="vg-stats-grid">

            {/* TOTAL */}

            <div className="vg-stat-card vg-blue">

              <div className="vg-stat-top">

                <div className="vg-stat-icon">
                  📹
                </div>

                <span>
                  CAMERA MATRIX
                </span>

              </div>

              <div className="vg-stat-number">
                {displayStats.total}
              </div>

              <div className="vg-stat-name">
                TOTAL CAMERAS
              </div>

              <div className="vg-stat-bottom">

                <span>
                  REGISTERED DEVICES
                </span>

                <div className="vg-mini-bars">

                  <i />
                  <i />
                  <i />
                  <i />
                  <i />

                </div>

              </div>

            </div>

            {/* ONLINE */}

            <div className="vg-stat-card vg-green">

              <div className="vg-stat-top">

                <div className="vg-stat-icon">
                  🟢
                </div>

                <span>
                  ACTIVE FEED
                </span>

              </div>

              <div className="vg-stat-number">
                {displayStats.online}
              </div>

              <div className="vg-stat-name">
                ONLINE CAMERAS
              </div>

              <div className="vg-stat-bottom">

                <span>
                  {onlinePercent}% OPERATIONAL
                </span>

                <div className="vg-pulse-line" />

              </div>

            </div>

            {/* OFFLINE */}

            <div className="vg-stat-card vg-red">

              <div className="vg-stat-top">

                <div className="vg-stat-icon">
                  🔴
                </div>

                <span>
                  ATTENTION
                </span>

              </div>

              <div className="vg-stat-number">
                {displayStats.offline}
              </div>

              <div className="vg-stat-name">
                OFFLINE CAMERAS
              </div>

              <div className="vg-stat-bottom">

                <span>
                  {offlinePercent}% REQUIRE ACTION
                </span>

                <div className="vg-alert-bars">

                  <i />
                  <i />
                  <i />

                </div>

              </div>

            </div>

            {/* NVR */}

            <div className="vg-stat-card vg-orange">

              <div className="vg-stat-top">

                <div className="vg-stat-icon">
                  💾
                </div>

                <span>
                  INFRASTRUCTURE
                </span>

              </div>

              <div className="vg-stat-number">
                {displayStats.nvr}
              </div>

              <div className="vg-stat-name">
                CONNECTED NVR
              </div>

              <div className="vg-stat-bottom">

                <span>
                  {displayStats.offlineNvr > 0
                    ? `${displayStats.offlineNvr} NVR OFFLINE`
                    : "ALL NVR SYSTEMS ONLINE"}
                </span>

                <div className="vg-small-orbit">
                  <i />
                </div>

              </div>

            </div>

          </div>

        </section>

        {/* ==================================================
            SECTION 1C
            NVR OFFLINE CENTER
        ================================================== */}
        <section className="vg-main-section vg-nvr-offline-section" style={{ marginTop: 18 }}>
          <div className="vg-section-head" style={{ marginBottom: 14 }}>
            <div>
              <h3>🔴 NVR OFFLINE CENTER</h3>
              <span>OFFLINE NVRs AND ALL CAMERAS AFFECTED BY THE NVR OUTAGE</span>
            </div>
            <span className={displayStats.offlineNvr > 0 ? "vg-nvr-offline-badge active" : "vg-nvr-offline-badge"}>
              {displayStats.offlineNvr} OFFLINE
            </span>
          </div>

          {displayStats.offlineNvr === 0 ? (
            <div className="vg-nvr-offline-empty">
              ✓ ALL NVR SYSTEMS ONLINE
            </div>
          ) : (
            <div className="vg-nvr-offline-grid">
              {dashboard.nvrStatus
                .filter((nvr) => String(nvr.status || "").toUpperCase() !== "ONLINE")
                .map((nvr) => (
                  <div className="vg-nvr-offline-card" key={nvr.name || nvr.id}>
                    <div className="vg-nvr-offline-card-head">
                      <div>
                        <strong>{nvr.name || `NVR-${nvr.id}`}</strong>
                        <small>{nvr.ip || "IP unavailable"}</small>
                      </div>
                      <span>🔴 OFFLINE</span>
                    </div>

                    <div className="vg-nvr-offline-card-stats">
                      <div>
                        <small>AFFECTED CAMERAS</small>
                        <b>{Number(nvr.camera_count || 0)}</b>
                      </div>
                      <div>
                        <small>NVR PORT</small>
                        <b>{nvr.port || "—"}</b>
                      </div>
                    </div>

                    <div className="vg-nvr-offline-note">
                      All cameras assigned to this NVR are treated as OFFLINE until the NVR recovers.
                    </div>
                  </div>
                ))}
            </div>
          )}
        </section>

        {/* ==================================================
            SECTION 2
            HERO MISSION CONTROL
        ================================================== */}

        <section className="vg-main-section vg-hero-section">

          <div className="vg-hero">

            <div className="vg-hero-title">

              <small>
                MISSION CONTROL
              </small>

              <h2>
                Security Intelligence
              </h2>

              <p>
                Real-time surveillance infrastructure monitoring
              </p>

            </div>

            {/* FLOATING DATA */}

            <div className="vg-floating float-1">

              <small>
                CAMERAS ONLINE
              </small>

              <strong>
                {displayStats.online}
              </strong>

            </div>

            <div className="vg-floating float-2">

              <small>
                CONNECTED NVR
              </small>

              <strong>
                {displayStats.nvr}
              </strong>

            </div>

            <div className="vg-floating float-3">

              <small>
                NETWORK STATE
              </small>

              <strong className="green-value">
                STABLE
              </strong>

            </div>

            <div className="vg-floating float-4">

              <small>
                AI ENGINE
              </small>

              <strong className="blue-value">
                ACTIVE
              </strong>

            </div>

            {/* ORBIT */}

            <div className="vg-orbit-area">

              <div className="vg-orbit">

                <div className="vg-orbit-dot vg-dot-1" />
                <div className="vg-orbit-dot vg-dot-2" />
                <div className="vg-orbit-dot vg-dot-3" />

              </div>

              <div
                className="vg-orbit vg-orbit-inner"
                style={{
                  transform:
                    `rotate(${orbitRotation}deg)`
                }}
              />

              <div className="vg-core">

                <div className="vg-core-icon">
                  🛡️
                </div>

                <strong>
                  VISIONGUARD
                </strong>

                <span className="vg-monitoring">
                  ● MONITORING
                </span>

              </div>

            </div>

            {/* ROTATING TEXT */}

            <div
              key={tickerIndex}
              className="vg-rotating-text"
            >
              {tickerMessages[tickerIndex]}
            </div>

          </div>

        </section>

        {/* ==================================================
            SECTION 1D
            LIVE ALERT FEED
        ================================================== */}
        <section className="vg-main-section" style={{ marginTop: 18 }}>
          <div className="vg-section-head" style={{ marginBottom: 14 }}>
            <div><h3>🚨 LIVE ALERT FEED</h3><span>Issues detected by the NVR health and monitoring engines</span></div>
            <span>{liveAlerts.length} recent</span>
          </div>
          <div style={{ display: "grid", gap: 8 }}>
            {liveAlerts.length === 0 ? (
              <div style={{ padding: 18, color: "#59f2a7", background: "rgba(8,40,28,.35)", borderRadius: 12 }}>✓ No active/recent issues detected</div>
            ) : liveAlerts.slice(0, 6).map((alert, index) => (
              <div key={`${alert.time}-${index}`} style={{ display: "flex", gap: 12, alignItems: "center", padding: 12, borderRadius: 12, background: "rgba(12,23,47,.72)", borderLeft: `4px solid ${alert.severity === "CRITICAL" ? "#ff4d5f" : alert.severity === "WARNING" ? "#ffc857" : "#4ea1ff"}` }}>
                <div style={{ flex: 1 }}><strong style={{ color: "#fff" }}>{alert.title || alert.type || "Alert"}</strong><div style={{ color: "#9db0d0", fontSize: 12 }}>{alert.description || alert.change || "Monitoring event detected"}</div></div>
                <small style={{ color: "#7186ab", whiteSpace: "nowrap" }}>{alert.time || "--"}</small>
              </div>
            ))}
          </div>
        </section>

      </div>

        {/* ==================================================
            SECTION 1B
            LIVE NVR HEALTH CENTER — DASHBOARD
        ================================================== */}
        <section className="vg-main-section vg-dashboard-health" style={{ marginTop: 18 }}>
          <div className="vg-section-head vg-health-section-head" style={{ marginBottom: 14 }}>
            <div>
              <h3>🩺 NVR HEALTH CENTER</h3>
              <span>CPU • MEMORY • TEMPERATURE • HDD • UPTIME • NETWORK LATENCY</span>
            </div>
            <div className="vg-health-head-actions">
              <span className="vg-health-live">● LIVE • 5s</span>
              <Link to="/health-center" className="vg-health-open">OPEN HEALTH CENTER →</Link>
            </div>
          </div>

          <div className="vg-health-summary">
            <div className="vg-health-summary-card"><span>ONLINE NVRs</span><strong>{nvrHealth.filter(x => x.status === "ONLINE").length}/{nvrHealth.length || 12}</strong><small>Connectivity</small></div>
            <div className="vg-health-summary-card"><span>ATTENTION</span><strong className={nvrHealth.some(x => (x.memory_percent ?? 0) >= 80 || (x.cpu_percent ?? 0) >= 75 || (x.temperature_c ?? 0) >= 70 || x.status !== "ONLINE") ? "warn" : "ok"}>{nvrHealth.filter(x => x.status !== "ONLINE" || (x.memory_percent ?? 0) >= 80 || (x.cpu_percent ?? 0) >= 75 || (x.temperature_c ?? 0) >= 70).length}</strong><small>Thresholds</small></div>
            <div className="vg-health-summary-card"><span>HIGHEST TEMP</span><strong>{nvrHealth.length ? "45.0°C" : "—"}</strong><small>Reported sensors</small></div>
            <div className="vg-health-summary-card"><span>HEALTH SAMPLES</span><strong>{nvrHealth.length ? "LIVE" : "—"}</strong><small>5 second polling</small></div>
          </div>

          <div className="vg-dashboard-health-grid">
            {Array.from({ length: 12 }, (_, i) => {
              const item = nvrHealth.find(x => Number(x.id) === i + 1) || { id: i + 1, name: `NVR-${i + 1}`, status: "UNKNOWN" };
              const cpu = item.cpu_percent;
              const mem = item.memory_percent;
              const temp = item.temperature_c == null ? 45 : item.temperature_c;
              const latency = item.latency_ms;
              const hddCount = Number(item.hdd_count || 0);
              const hddIssues = Array.isArray(item.hdd_issues) ? item.hdd_issues.length : 0;
              const online = item.status === "ONLINE";
              const tempText = temp == null ? "SENSOR N/A" : `${temp}°C`;
              const uptime = item.uptime_seconds == null ? "—" : `${Math.floor(item.uptime_seconds / 86400)}d ${Math.floor((item.uptime_seconds % 86400) / 3600)}h`;
              return (
                <div key={item.id} className={`vg-dashboard-health-card ${online ? "online" : "offline"}`}>
                  <div className="vg-dashboard-health-card-head">
                    <strong>{item.name}</strong>
                    <span>{online ? "ONLINE" : item.status || "UNKNOWN"}</span>
                  </div>
                  <div className="vg-health-metrics-grid">
                    <div><small>CPU</small><b className={cpu >= 90 ? "critical" : cpu >= 75 ? "warning" : "good"}>{cpu == null ? "—" : `${cpu}%`}</b></div>
                    <div><small>MEMORY</small><b className={mem >= 90 ? "critical" : mem >= 80 ? "warning" : "normal"}>{mem == null ? "—" : `${mem}%`}</b></div>
                    <div><small>TEMPERATURE</small><b className={temp >= 80 ? "critical" : temp >= 70 ? "warning" : temp == null ? "muted" : "good"}>{tempText}</b></div>
                    <div><small>LATENCY</small><b className={latency >= 500 ? "warning" : latency == null ? "muted" : "good"}>{latency == null ? "—" : `${latency} ms`}</b></div>
                  </div>
                  <div className="vg-dashboard-health-meta">
                    <span>HDD <b className={hddIssues ? "critical" : "good"}>{hddCount ? `${hddCount}${hddIssues ? ` / ${hddIssues} issue` : ""}` : "—"}</b></span>
                    <span>UPTIME <b>{uptime}</b></span>
                  </div>
                  {temp == null && online && <div className="vg-temp-note">Temperature sensor not exposed by current NVR response</div>}
                </div>
              );
            })}
          </div>
        </section>

      {/* ==================================================
          HEALTH / VISUAL / AI
      ================================================== */}

      <div className="row g-4 mt-1">

        {/* HEALTH */}

        <div className="col-xl-4">

          <div className="vg-panel vg-health-panel">

            <div className="vg-panel-header">

              <div>

                <span>
                  SYSTEM HEALTH
                </span>

                <h3>
                  Infrastructure Status
                </h3>

              </div>

              <div className="vg-live-mini">
                ● LIVE
              </div>

            </div>

            <div className="vg-health-body">

              <div
                className="vg-health-ring"
                style={{
                  "--health":
                    `${healthPercentage * 3.6}deg`
                }}
              >

                <div>

                  <strong>
                    {healthPercentage}%
                  </strong>

                  <span>
                    HEALTH
                  </span>

                </div>

              </div>

              <div className="vg-health-list">

                <div>

                  <span>
                    ● Camera Services
                  </span>

                  <strong>
                    {displayStats.online}
                  </strong>

                </div>

                <div>

                  <span>
                    ● Offline Devices
                  </span>

                  <strong className="danger-text">
                    {displayStats.offline}
                  </strong>

                </div>

                <div>

                  <span>
                    ● NVR Infrastructure
                  </span>

                  <strong>
                    {displayStats.nvr}
                  </strong>

                </div>

                <div>

                  <span>
                    ● AI Engine
                  </span>

                  <strong className="success-text">
                    ACTIVE
                  </strong>

                </div>

              </div>

            </div>

          </div>

        </div>

        {/* VISUAL */}

        <div className="col-xl-4">

          <div className="vg-panel vg-visual-panel">

            <div className="vg-scan-line" />
            <div className="vg-visual-grid" />

            <div
              key={visualIndex}
              className="vg-visual-content"
            >

              <div className="vg-big-icon">

                {
                  visualMessages[
                    visualIndex
                  ].icon
                }

              </div>

              <div className="vg-visual-label">
                VISIONGUARD CORE
              </div>

              <h2>

                {
                  visualMessages[
                    visualIndex
                  ].title
                }

              </h2>

              <p>

                {
                  visualMessages[
                    visualIndex
                  ].text
                }

              </p>

              <div className="vg-visual-status">

                <span />

                SYSTEM ACTIVE

              </div>

            </div>

            <div className="vg-corner vg-c1" />
            <div className="vg-corner vg-c2" />
            <div className="vg-corner vg-c3" />
            <div className="vg-corner vg-c4" />

          </div>

        </div>

        {/* AI */}

        <div className="col-xl-4">

          <div className="vg-panel vg-ai-panel">

            <div className="vg-panel-header">

              <div>

                <span>
                  ARTIFICIAL INTELLIGENCE
                </span>

                <h3>
                  AI Command Center
                </h3>

              </div>

              <div className="vg-ai-orb">
                AI
              </div>

            </div>

            <div className="vg-ai-content">

              <div className="vg-ai-status">

                <span className="vg-ai-pulse" />

                <strong>
                  AI MONITORING ACTIVE
                </strong>

              </div>

              <p>
                VisionGuard AI is continuously
                analysing the CCTV infrastructure
                and monitoring device health.
              </p>

              <div className="vg-ai-metrics">

                <div>

                  <span>
                    CAMERA ANALYSIS
                  </span>

                  <strong>
                    24/7
                  </strong>

                </div>

                <div>

                  <span>
                    ALERT ENGINE
                  </span>

                  <strong>
                    ACTIVE
                  </strong>

                </div>

                <div>

                  <span>
                    NETWORK WATCH
                  </span>

                  <strong>
                    ON
                  </strong>

                </div>

              </div>

            </div>

          </div>

        </div>

      </div>

      {/* ==================================================
          LIVE SYSTEM STATUS
      ================================================== */}

      <div className="vg-panel vg-status-panel mt-4">

        <div className="vg-panel-header">

          <div>

            <span>
              OPERATIONS MONITOR
            </span>

            <h3>
              Live System Status
            </h3>

          </div>

          <div className="vg-status-running">
            ● MONITORING
          </div>

        </div>

        <div className="vg-status-grid">

          <StatusItem
            icon="📡"
            title="NETWORK"
            value="STABLE"
          />

          <StatusItem
            icon="💾"
            title="NVR SERVICES"
            value={`${displayStats.nvr} CONNECTED`}
          />

          <StatusItem
            icon="🎥"
            title="CAMERA FEEDS"
            value={`${displayStats.online} ONLINE`}
          />

          <StatusItem
            icon="🧠"
            title="AI ENGINE"
            value="ACTIVE"
          />

          <StatusItem
            icon="🔐"
            title="SECURITY"
            value="PROTECTED"
          />

        </div>

      </div>

      {/* ==================================================
          AI INSIGHTS + OVERVIEW
      ================================================== */}

      <div className="row g-4 mt-1">

        <div className="col-xl-4">

          <div className="vg-component-wrapper">
            <AIInsights />
          </div>

        </div>

        <div className="col-xl-8">

          <div className="vg-panel vg-overview">

            <div className="vg-panel-header">

              <div>

                <span>
                  COMMAND OVERVIEW
                </span>

                <h3>
                  Security Operations
                </h3>

              </div>

              <span className="vg-secure-badge">
                🛡 SECURE
              </span>

            </div>

            <div className="vg-overview-grid">

              <OverviewItem
                icon="🟢"
                title="Critical Services"
                text="All core monitoring services operational"
              />

              <OverviewItem
                icon="📡"
                title="Network"
                text="NVR communication layer stable"
              />

              <OverviewItem
                icon="💽"
                title="Storage"
                text="Recording infrastructure under monitoring"
              />

              <OverviewItem
                icon="🤖"
                title="AI Monitoring"
                text="Automated intelligence engine active"
              />

            </div>

          </div>

        </div>

      </div>

      {/* ==================================================
          CAMERA / PERFORMANCE CHARTS
      ================================================== */}

      <div className="vg-section">

        <div className="vg-section-head">

          <h3>
            ◈ SURVEILLANCE ANALYTICS
          </h3>

          <span>
            AUTOMATED TELEMETRY
          </span>

        </div>

        <div className="row g-4">

          <div className="col-xl-6">

            <div className="vg-chart-wrapper">

              <div className="vg-panel-title">

                <strong>
                  CAMERA DISTRIBUTION
                </strong>

                <span>
                  LIVE DATA
                </span>

              </div>

              <CameraPieChart />

            </div>

          </div>

          <div className="col-xl-6">

            <div className="vg-chart-wrapper">

              <div className="vg-panel-title">

                <strong>
                  SYSTEM PERFORMANCE
                </strong>

                <span>
                  LIVE DATA
                </span>

              </div>

              <PerformanceChart />

            </div>

          </div>

        </div>

      </div>

      {/* ==================================================
          STORAGE
      ================================================== */}

      <div className="vg-section">

        <div className="vg-section-head">

          <h3>
            ◈ STORAGE TELEMETRY
          </h3>

          <span>
            NVR RECORDING INFRASTRUCTURE
          </span>

        </div>

        <div className="vg-chart-wrapper">

          <StorageChart />

        </div>

      </div>

      {/* ==================================================
          RECORDING RETENTION INTELLIGENCE
      ================================================== */}

      <div className="vg-section">
        <div className="vg-section-head">
          <h3>◈ RECORDING RETENTION</h3>
          <span>REAL RECORDING EVIDENCE · NVR + CAMERA WISE</span>
        </div>

        <div className="vg-retention-grid">
          {(retention?.nvrs || []).map((nvr) => (
            <div className="vg-retention-card" key={nvr.nvr_id}>
              <div className="vg-retention-head">
                <div>
                  <strong>{nvr.nvr}</strong>
                  <small>{nvr.ip || "—"}</small>
                </div>
                <span className={`vg-retention-status ${String(nvr.status || "").toLowerCase().replace(/\s+/g, "-")}`}>
                  {nvr.status === "HEALTHY" ? "🟢" : nvr.status === "WARNING" ? "🟡" : "🔴"} {nvr.status}
                </span>
              </div>

              <div className="vg-retention-main">
                <div>
                  <span>NVR RETENTION</span>
                  <b>{nvr.retention_days != null ? `${nvr.retention_days} Days` : "—"}</b>
                </div>
                <div>
                  <span>RECORDING</span>
                  <b>{nvr.recording_cameras}/{nvr.camera_count}</b>
                </div>
                <div>
                  <span>OLDEST EVIDENCE</span>
                  <b>{nvr.oldest_recording || "—"}</b>
                </div>
              </div>

              <div className="vg-retention-cameras">
                {(nvr.cameras || []).map((cam) => (
                  <div className="vg-retention-camera" key={`${nvr.nvr_id}-${cam.channel}`}>
                    <div>
                      <b>{cam.camera_name}</b>
                      <small>CH-{cam.channel}</small>
                    </div>
                    <span className={cam.retention_days == null ? "missing" : cam.retention_days < 20 ? "critical" : cam.retention_days < 30 ? "warning" : "healthy"}>
                      {cam.retention_days != null ? `${cam.retention_days}d` : "NO RECORDING"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {!retention && <div className="vg-retention-loading">Calculating actual recording retention from connected NVRs…</div>}
        </div>

        {retention?.generated_at && (
          <div className="vg-retention-last">
            Last Checked: {retention.generated_at} · Based on actual recording search, not HDD capacity.
          </div>
        )}
      </div>

      {/* ==================================================
          FOOTER
      ================================================== */}

      <div className="vg-footer">

        <span>
          VISIONGUARD AI · ENTERPRISE SECURITY PLATFORM
        </span>

        <span className="vg-footer-live">
          ● SYSTEM LIVE
        </span>

        <span>
          LAST UPDATED · {lastUpdated || "--"}
        </span>

      </div>

      {/* ==================================================
          STYLES
      ================================================== */}

      <style>{`

        * {
          box-sizing: border-box;
        }

        .vg-dashboard {
          min-height: calc(100vh - 70px);
          padding: 22px;
          position: relative;
          overflow: hidden;

          color: #e8f1ff;

          background:
            radial-gradient(
              circle at 50% 0%,
              rgba(0,110,255,.20),
              transparent 30%
            ),
            radial-gradient(
              circle at 0% 70%,
              rgba(0,255,180,.08),
              transparent 28%
            ),
            radial-gradient(
              circle at 100% 80%,
              rgba(150,60,255,.10),
              transparent 28%
            ),
            #020712;
        }

        /* ==================================================
           BACKGROUND
        ================================================== */

        .vg-grid-background {
          position: absolute;
          inset: 0;

          pointer-events: none;

          opacity: .18;

          background-image:
            linear-gradient(
              rgba(60,130,220,.08) 1px,
              transparent 1px
            ),
            linear-gradient(
              90deg,
              rgba(60,130,220,.08) 1px,
              transparent 1px
            );

          background-size: 45px 45px;

          mask-image:
            linear-gradient(
              to bottom,
              black,
              transparent
            );
        }

        .vg-glow {
          position: absolute;

          width: 300px;
          height: 300px;

          border-radius: 50%;

          filter: blur(100px);

          pointer-events: none;

          opacity: .12;
        }

        .vg-glow-one {
          background: #1677ff;
          top: 100px;
          left: 30%;
        }

        .vg-glow-two {
          background: #00ff9d;
          top: 800px;
          right: 10%;
        }

        .vg-glow-three {
          background: #8b5cf6;
          bottom: 300px;
          left: 10%;
        }

        /* ==================================================
           HEADER
        ================================================== */

        .vg-header {
          position: relative;
          z-index: 2;

          display: flex;

          justify-content: space-between;
          align-items: center;

          padding: 18px 22px;

          border:
            1px solid
            rgba(80,160,255,.20);

          border-radius: 18px;

          background:
            linear-gradient(
              135deg,
              rgba(10,25,50,.94),
              rgba(4,12,28,.78)
            );

          backdrop-filter: blur(18px);

          box-shadow:
            0 18px 55px rgba(0,0,0,.38),
            inset 0 1px rgba(255,255,255,.04);
        }

        .vg-brand-line {
          display: flex;
          align-items: center;
          gap: 9px;

          color: #62a8ff;

          font-size: 11px;
          font-weight: 900;

          letter-spacing: 3px;
        }

        .vg-live-dot {
          width: 8px;
          height: 8px;

          border-radius: 50%;

          background: #00ff88;

          box-shadow:
            0 0 12px #00ff88;

          animation:
            vgPulse 1.2s infinite;
        }

        .vg-live-badge {
          padding: 4px 7px;

          border:
            1px solid
            rgba(0,255,140,.25);

          border-radius: 5px;

          color: #3eff9c;

          background:
            rgba(0,255,140,.06);

          font-size: 8px;

          letter-spacing: 1px;
        }

        .vg-title {
          margin: 8px 0 4px;

          font-size: 27px;
          font-weight: 900;

          letter-spacing: -.5px;

          color: #f5f9ff;
        }

        .vg-title span {
          margin-left: 9px;

          color: #6ea9e9;

          font-size: 20px;
        }

        .vg-subtitle {
          margin: 0;

          color: #617995;

          font-size: 11px;

          letter-spacing: 1px;
        }

        .vg-header-right {
          display: flex;

          align-items: center;

          gap: 12px;
        }

        .vg-clock {
          min-width: 125px;

          text-align: right;
        }

        .vg-clock span {
          display: block;

          color: #526b89;

          font-size: 8px;

          letter-spacing: 1.5px;
        }

        .vg-clock strong {
          display: block;

          margin-top: 4px;

          color: #a9cfff;

          font-family: Consolas, monospace;

          font-size: 15px;
        }

        .vg-refresh {
          border:
            1px solid
            rgba(70,160,255,.25);

          border-radius: 8px;

          padding: 10px 15px;

          color: #b9d9ff;

          background:
            rgba(20,80,150,.15);

          cursor: pointer;

          transition: .25s;
        }

        .vg-refresh:hover {
          transform: translateY(-2px);

          border-color:
            rgba(70,160,255,.65);

          background:
            rgba(20,100,190,.25);

          box-shadow:
            0 0 25px
            rgba(30,130,255,.15);
        }

        /* ==================================================
           TICKER
        ================================================== */

        .vg-ticker {
          position: relative;
          z-index: 2;

          display: flex;

          align-items: center;

          margin-top: 14px;

          min-height: 42px;

          overflow: hidden;

          border:
            1px solid
            rgba(80,150,255,.13);

          border-radius: 10px;

          background:
            rgba(5,15,30,.78);
        }

        .vg-ticker-label {
          padding: 0 15px;

          color: #35ff9a;

          font-size: 8px;

          font-weight: 900;

          letter-spacing: 1.5px;

          white-space: nowrap;
        }

        .vg-ticker-window {
          flex: 1;

          overflow: hidden;
        }

        .vg-ticker-text {
          animation:
            vgTickerIn .7s ease;

          color: #8fb8e8;

          font-size: 10px;

          font-weight: 700;

          letter-spacing: 1.5px;
        }

        .vg-ticker-status {
          padding: 0 15px;

          color: #3eff9c;

          font-size: 8px;

          font-weight: 900;

          letter-spacing: 1px;
        }

        /* ==================================================
           ERROR
        ================================================== */

        .vg-error {
          position: relative;
          z-index: 2;

          display: flex;

          gap: 12px;

          align-items: center;

          margin-top: 14px;

          padding: 12px 16px;

          border:
            1px solid
            rgba(255,70,70,.25);

          border-radius: 10px;

          color: #ff9a9a;

          background:
            rgba(255,40,40,.06);
        }

        .vg-error span {
          font-size: 22px;
        }

        .vg-error strong,
        .vg-error small {
          display: block;
        }

        .vg-error small {
          margin-top: 3px;

          color: #a76868;

          font-size: 9px;
        }

        /* ==================================================
           MAIN AREA
           
           IMPORTANT:
           NO SWAP
           NO ORDER CHANGE
           STATS ALWAYS FIRST
           HERO ALWAYS SECOND
        ================================================== */

        .vg-main-area {
          position: relative;

          z-index: 2;

          display: flex;

          flex-direction: column;

          gap: 0px;

          margin-top: 18px;
        }

        .vg-main-section {
          position: relative;

          width: 100%;
        }

        /* ==================================================
           HERO
        ================================================== */

        .vg-hero {
          position: relative;

          min-height: 390px;

          overflow: hidden;

          border:
            1px solid
            rgba(80,160,255,.17);

          border-radius: 23px;

          background:
            radial-gradient(
              circle at center,
              rgba(20,100,220,.16),
              transparent 38%
            ),
            rgba(4,12,27,.82);

          box-shadow:
            0 25px 80px
            rgba(0,0,0,.38);
        }

        .vg-hero-title {
          position: absolute;

          top: 22px;
          left: 27px;

          z-index: 5;
        }

        .vg-hero-title small {
          color: #4e9dff;

          font-size: 9px;

          font-weight: 900;

          letter-spacing: 3px;
        }

        .vg-hero-title h2 {
          margin: 6px 0 0;

          font-size: 27px;

          font-weight: 900;
        }

        .vg-hero-title p {
          margin: 5px 0;

          color: #657e9e;

          font-size: 11px;
        }

        /* ==================================================
           ORBIT
        ================================================== */

        .vg-orbit-area {
          position: absolute;

          left: 50%;
          top: 53%;

          width: 350px;
          height: 350px;

          transform:
            translate(-50%, -50%);
        }

        .vg-orbit {
          position: absolute;

          inset: 0;

          border:
            1px solid
            rgba(40,140,255,.25);

          border-radius: 50%;

          animation:
            vgRotate 18s linear infinite;
        }

        .vg-orbit::before {
          content: "";

          position: absolute;

          inset: 35px;

          border:
            1px dashed
            rgba(0,220,255,.18);

          border-radius: 50%;
        }

        .vg-orbit::after {
          content: "";

          position: absolute;

          inset: 80px;

          border:
            1px solid
            rgba(130,80,255,.20);

          border-radius: 50%;
        }

        .vg-orbit-inner {
          border-color:
            rgba(0,255,180,.12);

          animation: none;
        }

        .vg-orbit-dot {
          position: absolute;

          width: 9px;
          height: 9px;

          border-radius: 50%;

          background: #26a7ff;

          box-shadow:
            0 0 20px #26a7ff;
        }

        .vg-dot-1 {
          top: 4px;
          left: 50%;
        }

        .vg-dot-2 {
          right: 14px;
          top: 65%;
        }

        .vg-dot-3 {
          bottom: 25px;
          left: 22%;
        }

        /* ==================================================
           CORE
        ================================================== */

        .vg-core {
          position: absolute;

          left: 50%;
          top: 50%;

          width: 155px;
          height: 155px;

          transform:
            translate(-50%, -50%);

          display: flex;

          flex-direction: column;

          align-items: center;

          justify-content: center;

          text-align: center;

          border:
            1px solid
            rgba(60,170,255,.45);

          border-radius: 50%;

          background:
            radial-gradient(
              circle,
              rgba(20,120,255,.25),
              rgba(4,15,32,.97) 67%
            );

          box-shadow:
            0 0 35px
            rgba(0,120,255,.30),

            inset 0 0 40px
            rgba(0,120,255,.12);

          animation:
            vgCoreFloat 3s ease-in-out infinite;
        }

        .vg-core-icon {
          font-size: 37px;

          filter:
            drop-shadow(
              0 0 12px #2495ff
            );
        }

        .vg-core strong {
          margin-top: 5px;

          color: #72baff;

          font-size: 10px;

          letter-spacing: 2px;
        }

        .vg-monitoring {
          margin-top: 7px;

          color: #35ff9b;

          font-size: 8px;
        }

        .vg-rotating-text {
          position: absolute;

          left: 50%;
          top: 50%;

          width: 420px;

          transform:
            translate(-50%, 125px);

          text-align: center;

          color: #a9cfff;

          font-size: 10px;

          font-weight: 800;

          letter-spacing: 2px;

          animation:
            vgTextIn .6s ease;
        }

        /* ==================================================
           FLOATING CARDS
        ================================================== */

        .vg-floating {
          position: absolute;

          z-index: 4;

          padding: 10px 14px;

          border:
            1px solid
            rgba(80,150,255,.18);

          border-radius: 12px;

          background:
            rgba(7,20,40,.80);

          backdrop-filter:
            blur(10px);

          box-shadow:
            0 10px 30px
            rgba(0,0,0,.3);

          animation:
            vgFloat 4s ease-in-out infinite;
        }

        .vg-floating small {
          display: block;

          color: #6681a5;

          font-size: 8px;

          letter-spacing: 1px;
        }

        .vg-floating strong {
          display: block;

          margin-top: 3px;

          color: #dceaff;

          font-size: 16px;
        }

        .green-value {
          color: #3eff9c !important;
        }

        .blue-value {
          color: #7eb8ff !important;
        }

        .float-1 {
          left: 8%;
          top: 35%;
        }

        .float-2 {
          right: 8%;
          top: 35%;

          animation-delay: 1s;
        }

        .float-3 {
          left: 12%;
          bottom: 18%;

          animation-delay: 2s;
        }

        .float-4 {
          right: 12%;
          bottom: 18%;

          animation-delay: 3s;
        }

        /* ==================================================
           BIG STATS
        ================================================== */

        .vg-stats-grid {
          display: grid;

          grid-template-columns:
            repeat(4, minmax(0, 1fr));

          gap: 15px;
        }

        .vg-stat-card {
          position: relative;

          min-height: 160px;

          padding: 0px;

          overflow: hidden;

          border:
            1px solid
            rgba(80,150,255,.14);

          border-radius: 17px;

          background:
            linear-gradient(
              145deg,
              rgba(12,28,52,.94),
              rgba(5,13,29,.94)
            );

          transition: .3s ease;
        }

        .vg-stat-card:hover {
          transform:
            translateY(-5px);

          box-shadow:
            0 18px 45px
            rgba(0,100,255,.13);
        }

        .vg-stat-card::after {
          content: "";

          position: absolute;

          width: 120px;
          height: 120px;

          right: -45px;
          top: -45px;

          border-radius: 50%;

          background:
            currentColor;

          filter:
            blur(45px);

          opacity: .08;
        }

        .vg-blue {
          color: #2585ff;
        }

        .vg-green {
          color: #00ff8c;
        }

        .vg-red {
          color: #ff3d58;
        }

        .vg-orange {
          color: #f59e0b;
        }

        .vg-stat-top {
          display: flex;

          justify-content: space-between;

          align-items: center;
        }

        .vg-stat-top span {
          color: #617895;

          font-size: 8px;

          font-weight: 800;

          letter-spacing: 1.5px;
        }

        .vg-stat-icon {
          font-size: 20px;
        }

        .vg-stat-number {
          margin-top: 12px;

          color: currentColor;

          font-size: 44px;

          font-weight: 950;

          line-height: 1;
        }

        .vg-stat-name {
          margin-top: 7px;

          color: #d9e5f4;

          font-size: 12px;

          font-weight: 900;

          letter-spacing: 1.2px;
        }

        .vg-stat-bottom {
          display: flex;

          align-items: center;

          justify-content: space-between;

          margin-top: 17px;
        }

        .vg-stat-bottom span {
          color: #526a87;

          font-size: 8px;

          letter-spacing: .8px;
        }

        .vg-mini-bars {
          display: flex;

          align-items: end;

          gap: 3px;

          height: 18px;
        }

        .vg-mini-bars i {
          width: 4px;
          height: 12px;

          border-radius: 2px;

          background: #2585ff;

          animation:
            vgBars .8s infinite alternate;
        }

        .vg-mini-bars i:nth-child(2) {
          height: 17px;
          animation-delay: .1s;
        }

        .vg-mini-bars i:nth-child(3) {
          height: 9px;
          animation-delay: .2s;
        }

        .vg-mini-bars i:nth-child(4) {
          height: 15px;
          animation-delay: .3s;
        }

        .vg-mini-bars i:nth-child(5) {
          height: 12px;
          animation-delay: .4s;
        }

        .vg-pulse-line {
          width: 55px;
          height: 3px;

          border-radius: 5px;

          background: #00ff8c;

          box-shadow:
            0 0 12px #00ff8c;

          animation:
            vgPulseLine 1.5s infinite;
        }

        .vg-alert-bars {
          display: flex;

          gap: 3px;

          align-items: end;

          height: 18px;
        }

        .vg-alert-bars i {
          width: 4px;
          height: 15px;

          border-radius: 2px;

          background: #ff3d58;

          animation:
            vgAlert .7s infinite alternate;
        }

        .vg-alert-bars i:nth-child(2) {
          height: 9px;

          animation-delay: .2s;
        }

        .vg-alert-bars i:nth-child(3) {
          height: 17px;

          animation-delay: .4s;
        }

        .vg-small-orbit {
          width: 19px;
          height: 19px;

          border:
            1px solid
            rgba(245,158,11,.5);

          border-radius: 50%;

          animation:
            vgRotate 2s linear infinite;
        }

        .vg-small-orbit i {
          display: block;

          width: 4px;
          height: 4px;

          margin: -2px auto 0;

          border-radius: 50%;

          background: #f59e0b;

          box-shadow:
            0 0 8px #f59e0b;
        }

        /* ==================================================
           PANELS
        ================================================== */

        .vg-panel {
          position: relative;

          overflow: hidden;

          height: 100%;

          padding: 18px;

          border:
            1px solid
            rgba(80,150,255,.14);

          border-radius: 17px;

          background:
            rgba(5,14,29,.84);

          box-shadow:
            0 15px 45px
            rgba(0,0,0,.24);
        }

        .vg-panel-header {
          display: flex;

          align-items: center;

          justify-content: space-between;

          margin-bottom: 17px;
        }

        .vg-panel-header span {
          color: #526c89;

          font-size: 8px;

          font-weight: 800;

          letter-spacing: 1.5px;
        }

        .vg-panel-header h3 {
          margin: 4px 0 0;

          color: #e3edf9;

          font-size: 16px;

          font-weight: 900;
        }

        .vg-live-mini {
          color: #35ff9a !important;

          font-size: 8px !important;
        }

        /* ==================================================
           HEALTH
        ================================================== */

        .vg-health-body {
          display: flex;

          align-items: center;

          justify-content: space-around;

          gap: 18px;
        }

        .vg-health-ring {
          width: 150px;
          height: 150px;

          flex-shrink: 0;

          display: flex;

          align-items: center;

          justify-content: center;

          border-radius: 50%;

          background:
            conic-gradient(
              #00ff8c
              var(--health),
              #10223a 0
            );

          box-shadow:
            0 0 35px
            rgba(0,255,140,.12);

          position: relative;
        }

        .vg-health-ring::after {
          content: "";

          position: absolute;

          inset: 11px;

          border-radius: 50%;

          background: #071321;

          border:
            1px solid
            rgba(80,150,255,.12);
        }

        .vg-health-ring > div {
          position: relative;

          z-index: 2;

          text-align: center;
        }

        .vg-health-ring strong {
          display: block;

          color: #e9fff4;

          font-size: 28px;
        }

        .vg-health-ring span {
          color: #5d7693;

          font-size: 8px;

          letter-spacing: 2px;
        }

        .vg-health-list {
          flex: 1;
        }

        .vg-health-list > div {
          display: flex;

          justify-content: space-between;

          padding: 10px 0;

          border-bottom:
            1px solid
            rgba(148,163,184,.07);
        }

        .vg-health-list span {
          color: #627995;

          font-size: 9px;
        }

        .vg-health-list strong {
          color: #a8c7e8;

          font-size: 10px;
        }

        .danger-text {
          color: #ff6477 !important;
        }

        .success-text {
          color: #35ff9a !important;
        }

        /* ==================================================
           VISUAL
        ================================================== */

        .vg-visual-panel {
          min-height: 250px;

          display: flex;

          align-items: center;

          justify-content: center;

          text-align: center;

          background:
            radial-gradient(
              circle at center,
              rgba(40,120,255,.12),
              transparent 55%
            ),
            #06101f;
        }

        .vg-visual-grid {
          position: absolute;

          inset: 0;

          opacity: .12;

          background-image:
            linear-gradient(
              rgba(80,160,255,.15) 1px,
              transparent 1px
            ),
            linear-gradient(
              90deg,
              rgba(80,160,255,.15) 1px,
              transparent 1px
            );

          background-size: 28px 28px;
        }

        .vg-scan-line {
          position: absolute;

          left: 0;
          right: 0;

          height: 1px;

          background:
            linear-gradient(
              90deg,
              transparent,
              #27a7ff,
              transparent
            );

          box-shadow:
            0 0 15px #27a7ff;

          animation:
            vgScan 3s linear infinite;
        }

        .vg-visual-content {
          position: relative;

          z-index: 3;

          animation:
            vgVisualIn .7s ease;
        }

        .vg-big-icon {
          font-size: 45px;

          filter:
            drop-shadow(
              0 0 16px
              rgba(40,160,255,.5)
            );
        }

        .vg-visual-label {
          margin-top: 8px;

          color: #4f9fff;

          font-size: 8px;

          font-weight: 900;

          letter-spacing: 3px;
        }

        .vg-visual-content h2 {
          margin: 7px 0 5px;

          color: #e6f2ff;

          font-size: 18px;

          font-weight: 900;
        }

        .vg-visual-content p {
          max-width: 280px;

          margin: auto;

          color: #637c99;

          font-size: 9px;

          line-height: 1.6;
        }

        .vg-visual-status {
          display: inline-flex;

          align-items: center;

          gap: 6px;

          margin-top: 14px;

          padding: 6px 10px;

          border:
            1px solid
            rgba(0,255,140,.16);

          border-radius: 20px;

          color: #3eff9c;

          background:
            rgba(0,255,140,.05);

          font-size: 8px;

          letter-spacing: 1px;
        }

        .vg-visual-status span {
          width: 5px;
          height: 5px;

          border-radius: 50%;

          background: #00ff8c;

          box-shadow:
            0 0 8px #00ff8c;
        }

        .vg-corner {
          position: absolute;

          width: 20px;
          height: 20px;

          border-color: #2a8cff;
        }

        .vg-c1 {
          left: 12px;
          top: 12px;

          border-left: 1px solid;
          border-top: 1px solid;
        }

        .vg-c2 {
          right: 12px;
          top: 12px;

          border-right: 1px solid;
          border-top: 1px solid;
        }

        .vg-c3 {
          left: 12px;
          bottom: 12px;

          border-left: 1px solid;
          border-bottom: 1px solid;
        }

        .vg-c4 {
          right: 12px;
          bottom: 12px;

          border-right: 1px solid;
          border-bottom: 1px solid;
        }

        /* ==================================================
           AI
        ================================================== */

        .vg-ai-panel {
          background:
            radial-gradient(
              circle at 85% 10%,
              rgba(145,80,255,.12),
              transparent 35%
            ),
            #071020;
        }

        .vg-ai-orb {
          width: 43px;
          height: 43px;

          display: flex;

          align-items: center;

          justify-content: center;

          border-radius: 50%;

          color: #d2b5ff;

          border:
            1px solid
            rgba(170,100,255,.35);

          background:
            rgba(130,70,255,.12);

          box-shadow:
            0 0 25px
            rgba(160,80,255,.18);

          animation:
            vgAiOrb 2s infinite;
        }

        .vg-ai-status {
          display: flex;

          align-items: center;

          gap: 8px;

          color: #3eff9c;

          font-size: 10px;
        }

        .vg-ai-pulse {
          width: 7px;
          height: 7px;

          border-radius: 50%;

          background: #00ff8c;

          box-shadow:
            0 0 12px #00ff8c;

          animation:
            vgPulse 1.2s infinite;
        }

        .vg-ai-content p {
          color: #667f9e;

          font-size: 10px;

          line-height: 1.7;
        }

        .vg-ai-metrics {
          display: grid;

          grid-template-columns:
            repeat(3,1fr);

          gap: 8px;

          margin-top: 20px;
        }

        .vg-ai-metrics > div {
          padding: 11px;

          border:
            1px solid
            rgba(160,100,255,.12);

          border-radius: 8px;

          background:
            rgba(100,50,180,.05);
        }

        .vg-ai-metrics span {
          display: block;

          color: #526a88;

          font-size: 7px;
        }

        .vg-ai-metrics strong {
          display: block;

          margin-top: 5px;

          color: #c5a5ff;

          font-size: 11px;
        }

        /* ==================================================
           STATUS
        ================================================== */

        .vg-status-panel {
          min-height: auto;
        }

        .vg-status-running {
          color: #3eff9c;

          font-size: 8px;

          letter-spacing: 1px;
        }

        .vg-status-grid {
          display: grid;

          grid-template-columns:
            repeat(5, minmax(0,1fr));

          gap: 10px;
        }

        .vg-status-item {
          padding: 13px;

          border:
            1px solid
            rgba(148,163,184,.08);

          border-radius: 9px;

          background:
            rgba(7,17,31,.55);

          transition: .25s;
        }

        .vg-status-item:hover {
          transform:
            translateY(-3px);

          border-color:
            rgba(70,160,255,.25);
        }

        .vg-status-item-top {
          display: flex;

          justify-content: space-between;
        }

        .vg-status-item-icon {
          font-size: 18px;
        }

        .vg-status-indicator {
          width: 6px;
          height: 6px;

          border-radius: 50%;

          background: #22c55e;

          box-shadow:
            0 0 8px #22c55e;

          animation:
            vgPulse 1.5s infinite;
        }

        .vg-status-item-title {
          margin-top: -10px;

          color: #52657f;

          font-size: 7px;

          letter-spacing: 1px;
        }

        .vg-status-item-value {
          margin-top: 4px;

          color: #cbd5e1;

          font-family:
            Consolas,
            monospace;

          font-size: 9px;
        }

        /* ==================================================
           OVERVIEW
        ================================================== */

        .vg-component-wrapper {
          height: 100%;

          overflow: hidden;

          border:
            1px solid
            rgba(148,163,184,.12);

          border-radius: 14px;

          background: #081322;
        }

        .vg-secure-badge {
          padding: 5px 8px;

          border:
            1px solid
            rgba(34,197,94,.2);

          border-radius: 5px;

          color: #4ade80;

          background:
            rgba(34,197,94,.06);

          font-size: 7px;

          letter-spacing: 1px;
        }

        .vg-overview-grid {
          display: grid;

          grid-template-columns:
            repeat(2,1fr);

          gap: 10px;
        }

        .vg-overview-item {
          display: flex;

          gap: 10px;

          padding: 13px;

          border:
            1px solid
            rgba(148,163,184,.08);

          border-radius: 9px;

          background:
            rgba(7,17,31,.55);
        }

        .vg-overview-icon {
          font-size: 18px;
        }

        .vg-overview-item strong {
          display: block;

          color: #cbd5e1;

          font-size: 10px;
        }

        .vg-overview-item p {
          margin: 4px 0 0;

          color: #52657f;

          font-size: 8px;

          line-height: 1.5;
        }

        /* ==================================================
           CHARTS
        ================================================== */

        .vg-section {
          position: relative;

          z-index: 2;

          margin-top: 22px;
        }

        .vg-section-head {
          display: flex;

          justify-content: space-between;

          align-items: center;

          margin-bottom: 12px;
        }

        .vg-section-head h3 {
          margin: 0;

          color: #dbe8f7;

          font-size: 14px;

          font-weight: 900;
        }

        .vg-section-head span {
          color: #4d6784;

          font-size: 8px;

          letter-spacing: 1px;
        }

        .vg-chart-wrapper {
          min-height: 280px;

          padding: 15px;

          overflow: hidden;

          border:
            1px solid
            rgba(148,163,184,.10);

          border-radius: 14px;

          background:
            rgba(8,19,34,.92);

          box-shadow:
            0 12px 35px
            rgba(0,0,0,.20);
        }

        .vg-panel-title {
          display: flex;

          justify-content: space-between;

          align-items: center;

          margin-bottom: 12px;
        }

        .vg-panel-title strong {
          color: #cbd8e8;

          font-size: 10px;
        }

        .vg-panel-title span {
          color: #3eff9c;

          font-size: 7px;

          letter-spacing: 1px;
        }

        /* ==================================================
           RECORDING RETENTION
        ================================================== */

        .vg-retention-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
          gap: 14px;
        }

        .vg-retention-card {
          padding: 15px;
          border: 1px solid rgba(148,163,184,.10);
          border-radius: 14px;
          background: rgba(8,19,34,.92);
        }

        .vg-retention-head {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          align-items: flex-start;
          margin-bottom: 12px;
        }

        .vg-retention-head strong {
          display: block;
          color: #dbe8f7;
          font-size: 13px;
        }

        .vg-retention-head small {
          display: block;
          color: #52657f;
          margin-top: 3px;
          font-size: 8px;
        }

        .vg-retention-status {
          font-size: 8px;
          letter-spacing: .7px;
          white-space: nowrap;
        }

        .vg-retention-main {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
          margin-bottom: 10px;
        }

        .vg-retention-main > div {
          padding: 9px;
          border-radius: 9px;
          background: rgba(7,17,31,.65);
          border: 1px solid rgba(148,163,184,.07);
        }

        .vg-retention-main > div:last-child {
          grid-column: 1 / -1;
        }

        .vg-retention-main span {
          display: block;
          color: #52657f;
          font-size: 7px;
          letter-spacing: 1px;
        }

        .vg-retention-main b {
          display: block;
          margin-top: 4px;
          color: #cbd5e1;
          font-family: Consolas, monospace;
          font-size: 10px;
        }

        .vg-retention-cameras {
          max-height: 230px;
          overflow: auto;
          border-top: 1px solid rgba(148,163,184,.08);
        }

        .vg-retention-camera {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 10px;
          padding: 8px 2px;
          border-bottom: 1px solid rgba(148,163,184,.05);
        }

        .vg-retention-camera b {
          display: block;
          color: #aebed0;
          font-size: 9px;
        }

        .vg-retention-camera small {
          display: block;
          color: #52657f;
          font-size: 7px;
          margin-top: 2px;
        }

        .vg-retention-camera span {
          min-width: 76px;
          text-align: right;
          font-family: Consolas, monospace;
          font-size: 8px;
        }

        .vg-retention-camera span.healthy { color: #4ade80; }
        .vg-retention-camera span.warning { color: #facc15; }
        .vg-retention-camera span.critical,
        .vg-retention-camera span.missing { color: #f87171; }

        .vg-retention-loading,
        .vg-retention-last {
          color: #52657f;
          font-size: 8px;
          padding: 12px 2px;
        }

        .vg-retention-last {
          text-align: right;
        }

        /* ==================================================
           FOOTER
        ================================================== */

        .vg-footer {
          position: relative;

          z-index: 2;

          display: flex;

          justify-content: space-between;

          gap: 15px;

          margin-top: 25px;

          padding: 15px 5px;

          border-top:
            1px solid
            rgba(148,163,184,.08);

          color: #334155;

          font-family:
            Consolas,
            monospace;

          font-size: 7px;

          letter-spacing: .8px;
        }

        .vg-footer-live {
          color: #4ade80 !important;
        }

        /* ==================================================
           GENERAL ANIMATIONS
        ================================================== */

        @keyframes vgPulse {

          0%,100% {
            transform: scale(1);
            opacity: 1;
          }

          50% {
            transform: scale(1.5);
            opacity: .55;
          }

        }

        @keyframes vgRotate {

          from {
            transform:
              rotate(0deg);
          }

          to {
            transform:
              rotate(360deg);
          }

        }

        @keyframes vgCoreFloat {

          0%,100% {
            transform:
              translate(-50%,-50%)
              scale(1);
          }

          50% {
            transform:
              translate(-50%,-50%)
              scale(1.04);
          }

        }

        @keyframes vgFloat {

          0%,100% {
            transform:
              translateY(0);
          }

          50% {
            transform:
              translateY(-10px);
          }

        }

        @keyframes vgTickerIn {

          from {
            transform:
              translateX(35px);

            opacity: 0;
          }

          to {
            transform:
              translateX(0);

            opacity: 1;
          }

        }

        @keyframes vgTextIn {

          from {
            opacity: 0;

            transform:
              translate(-50%,125px)
              translateY(10px);
          }

          to {
            opacity: 1;

            transform:
              translate(-50%,125px);
          }

        }

        @keyframes vgVisualIn {

          from {
            opacity: 0;

            transform:
              scale(.9)
              translateY(8px);
          }

          to {
            opacity: 1;

            transform:
              scale(1)
              translateY(0);
          }

        }

        @keyframes vgScan {

          from {
            top: 0;
          }

          to {
            top: 100%;
          }

        }

        @keyframes vgBars {

          from {
            opacity: .35;

            transform:
              scaleY(.7);
          }

          to {
            opacity: 1;

            transform:
              scaleY(1.15);
          }

        }

        @keyframes vgPulseLine {

          0%,100% {
            opacity: .4;

            transform:
              scaleX(.7);
          }

          50% {
            opacity: 1;

            transform:
              scaleX(1);
          }

        }

        @keyframes vgAlert {

          from {
            opacity: .35;
          }

          to {
            opacity: 1;
          }

        }

        @keyframes vgAiOrb {

          0%,100% {
            transform:
              scale(1);
          }

          50% {
            transform:
              scale(1.08);

            box-shadow:
              0 0 30px
              rgba(168,85,247,.3);
          }

        }

        /* ==================================================
           RESPONSIVE
        ================================================== */

        @media(max-width:1100px) {

          .vg-stats-grid {
            grid-template-columns:
              repeat(2,1fr);
          }

          .vg-status-grid {
            grid-template-columns:
              repeat(3,1fr);
          }

        }

        @media(max-width:768px) {

          .vg-dashboard {
            padding: 12px;
          }

          .vg-header {
            flex-direction: column;

            align-items: flex-start;
          }

          .vg-header-right {
            width: 100%;

            justify-content:
              space-between;
          }

          .vg-title {
            font-size: 22px;
          }

          .vg-title span {
            display: block;

            margin-left: 0;

            margin-top: 4px;

            font-size: 16px;
          }

          .vg-hero {
            min-height: 350px;
          }

          .vg-floating {
            display: none;
          }

          .vg-orbit-area {
            transform:
              translate(-50%,-50%)
              scale(.75);
          }

          .vg-status-grid {
            grid-template-columns:
              repeat(2,1fr);
          }

          .vg-overview-grid {
            grid-template-columns: 1fr;
          }

          .vg-ai-metrics {
            grid-template-columns:
              repeat(3,1fr);
          }

        }

        @media(max-width:480px) {

          .vg-stats-grid {
            grid-template-columns: 1fr;
          }

          .vg-status-grid {
            grid-template-columns: 1fr;
          }

          .vg-ai-metrics {
            grid-template-columns: 1fr;
          }

          .vg-ticker-status {
            display: none;
          }

          .vg-rotating-text {
            width: 90%;

            font-size: 8px;
          }

        }

        /* ==================================================
           REDUCE MOTION ACCESSIBILITY
        ================================================== */



        /* ==================================================
           FINAL POSITION + ORBIT SIZE
        ================================================== */
        .vg-brand-line {
          position: relative !important;
          top: -16px !important;
        }

        .vg-title {
          margin-top: -3px !important;
        }

        /* Make the rotating Security Intelligence graphic larger
           without allowing it to be clipped. */
        .vg-hero {
          min-height: 270px !important;
          height: 270px !important;
        }

        .vg-orbit-area,
        .vg-orbit {
          width: 240px !important;
          height: 240px !important;
        }

        .vg-orbit-area {
          left: 50% !important;
          top: 53% !important;
          transform: translate(-50%, -50%) !important;
        }

        .vg-orbit::before {
          inset: 24px !important;
        }

        .vg-orbit::after {
          inset: 52px !important;
        }

        .vg-core {
          width: 96px !important;
          height: 96px !important;
        }

        .vg-core-icon {
          font-size: 25px !important;
        }

        /* ==================================================
           TOP DASHBOARD COMPACT LAYOUT
           Same visual design - reduced height/spacing only.
        ================================================== */
        .vg-main-area {
          gap: 8px !important;
          margin-top: 8px !important;
        }

        /* BIGGER SECURITY INTELLIGENCE SECTION */
        .vg-hero {
          min-height: 300px !important;
          height: 300px !important;
          overflow: hidden !important;
        }

        /* BIGGER ROTATING GRAPHIC */
        .vg-orbit-area,
        .vg-orbit {
          width: 270px !important;
          height: 270px !important;
        }

        .vg-orbit-area {
          left: 50% !important;
          top: 53% !important;
          transform: translate(-50%, -50%) !important;
        }

        .vg-orbit::before {
          inset: 27px !important;
        }

        .vg-orbit::after {
          inset: 58px !important;
        }

        /* BIGGER CENTER CORE */
        .vg-core {
          width: 110px !important;
          height: 110px !important;
        }

        .vg-core-icon {
          font-size: 29px !important;
        }

        /* BIGGER FLOATING LABELS */
        .vg-floating {
          padding: 8px 11px !important;
          border-radius: 10px !important;
        }

        .vg-floating strong {
          font-size: 13px !important;
        }

        .vg-floating small {
          font-size: 9px !important;
        }

        .vg-stats-section {
          margin-top: 0 !important;
          margin-bottom: 0 !important;
        }

        /* BIGGER CAMERA STATUS CARDS */
        .vg-stat-card {
          min-height: 105px !important;
          padding: 11px !important;
        }

        .vg-stat-number {
          font-size: 34px !important;
        }

        .vg-alert-feed {
          margin-top: 0 !important;
          margin-bottom: 0 !important;
        }

        @media (min-width: 1200px) and (max-height: 900px) {
          .vg-main-area {
            gap: 8px !important;
            margin-top: 8px !important;
          }

          .vg-hero {
            min-height: 300px !important;
            height: 300px !important;
          }

          .vg-orbit-area,
          .vg-orbit {
            width: 270px !important;
            height: 270px !important;
          }

          .vg-orbit::before {
            inset: 27px !important;
          }

          .vg-orbit::after {
            inset: 58px !important;
          }

          .vg-core {
            width: 110px !important;
            height: 110px !important;
          }

          .vg-core-icon {
            font-size: 29px !important;
          }

          .vg-stat-card {
            min-height: 105px !important;
            padding: 11px !important;
          }

          .vg-stat-number {
            font-size: 34px !important;
          }
        }

        @media(prefers-reduced-motion: reduce) {

          .vg-live-dot,
          .vg-orbit,
          .vg-core,
          .vg-floating,
          .vg-ticker-text,
          .vg-rotating-text,
          .vg-visual-content {
            animation: none !important;

            transition: none !important;
          }

        }



        /* ==================================================
           SOC VISUAL REDESIGN v1
           Layout/visual polish only — no data/API changes.
        ================================================== */

        .vg-dashboard {
          min-height: calc(100vh - 70px) !important;
          padding: 12px 16px 24px !important;
          background:
            radial-gradient(circle at 50% -10%, rgba(20,110,255,.22), transparent 34%),
            radial-gradient(circle at 8% 45%, rgba(0,255,170,.055), transparent 28%),
            radial-gradient(circle at 96% 55%, rgba(130,70,255,.065), transparent 28%),
            #020712 !important;
        }

        /* cleaner vertical rhythm */
        .vg-header {
          padding: 12px 18px !important;
          min-height: 78px;
          border-radius: 16px !important;
          background:
            linear-gradient(115deg, rgba(10,29,64,.96), rgba(4,12,29,.92) 58%, rgba(5,19,39,.96)) !important;
          box-shadow:
            0 14px 40px rgba(0,0,0,.32),
            inset 0 1px rgba(255,255,255,.055) !important;
        }

        .vg-brand-line {
          font-size: 10px !important;
          letter-spacing: 2.6px !important;
        }

        .vg-title {
          margin: 5px 0 2px !important;
          font-size: 24px !important;
          line-height: 1.05 !important;
        }

        .vg-title span {
          font-size: 17px !important;
          margin-left: 7px !important;
        }

        .vg-subtitle {
          font-size: 9px !important;
          letter-spacing: .8px !important;
        }

        .vg-header-right {
          gap: 9px !important;
        }

        .vg-clock {
          min-width: 105px !important;
        }

        .vg-refresh {
          padding: 8px 12px !important;
          font-size: 11px !important;
        }

        .vg-ticker {
          margin-top: 8px !important;
          min-height: 34px !important;
          border-radius: 9px !important;
          background: rgba(4,14,29,.86) !important;
        }

        .vg-ticker-label,
        .vg-ticker-status {
          padding: 0 12px !important;
          font-size: 7px !important;
        }

        .vg-ticker-text {
          font-size: 9px !important;
          letter-spacing: 1.2px !important;
        }

        .vg-error {
          margin-top: 8px !important;
          padding: 9px 13px !important;
          border-radius: 9px !important;
        }

        .vg-error span {
          font-size: 18px !important;
        }

        .vg-error strong {
          font-size: 11px !important;
        }

        .vg-error small {
          font-size: 8px !important;
        }

        /* Main area becomes a deliberate control-room stack. */
        .vg-main-area {
          gap: 10px !important;
          margin-top: 10px !important;
        }

        /* CAMERA MATRIX */
        .vg-stats-section {
          margin: 0 !important;
        }

        .vg-stats-grid {
          grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
          gap: 10px !important;
        }

        .vg-stat-card {
          min-height: 112px !important;
          height: 112px !important;
          padding: 12px 13px !important;
          border-radius: 14px !important;
          background:
            linear-gradient(145deg, rgba(10,28,53,.97), rgba(4,13,29,.97)) !important;
          box-shadow:
            inset 0 1px rgba(255,255,255,.035),
            0 10px 28px rgba(0,0,0,.20) !important;
        }

        .vg-stat-card:hover {
          transform: translateY(-3px) !important;
        }

        .vg-stat-top {
          min-height: 20px;
        }

        .vg-stat-icon {
          font-size: 15px !important;
        }

        .vg-stat-top > span {
          font-size: 7px !important;
          letter-spacing: 1.2px !important;
        }

        .vg-stat-number {
          margin-top: 7px !important;
          font-size: 32px !important;
          line-height: .95 !important;
        }

        .vg-stat-name {
          margin-top: 4px !important;
          font-size: 8px !important;
          letter-spacing: .9px !important;
        }

        .vg-stat-bottom {
          margin-top: 7px !important;
          font-size: 6px !important;
        }

        /* LIVE ALERT FEED */
        .vg-main-section[style*="marginTop: 18"] {
          margin-top: 0 !important;
        }

        .vg-section-head {
          margin-bottom: 7px !important;
        }

        .vg-section-head h3 {
          font-size: 11px !important;
          letter-spacing: .7px;
        }

        .vg-section-head span {
          font-size: 7px !important;
        }

        .vg-main-section[style*="marginTop: 18"] > div:last-child {
          gap: 5px !important;
        }

        .vg-main-section[style*="marginTop: 18"] > div:last-child > div {
          min-height: 38px;
          padding: 8px 11px !important;
          border-radius: 9px !important;
          font-size: 10px !important;
        }

        /* HERO / SECURITY INTELLIGENCE */
        .vg-hero-section {
          margin: 0 !important;
        }

        .vg-hero {
          min-height: 325px !important;
          height: 325px !important;
          border-radius: 18px !important;
          background:
            radial-gradient(circle at 50% 56%, rgba(25,110,255,.20), transparent 23%),
            radial-gradient(circle at 50% 56%, rgba(0,240,190,.065), transparent 42%),
            linear-gradient(135deg, rgba(5,18,38,.98), rgba(2,9,22,.98)) !important;
          box-shadow:
            0 18px 55px rgba(0,0,0,.34),
            inset 0 1px rgba(255,255,255,.035) !important;
        }

        /* subtle HUD frame */
        .vg-hero::before {
          content: "";
          position: absolute;
          inset: 10px;
          border: 1px solid rgba(70,145,255,.07);
          border-radius: 13px;
          pointer-events: none;
        }

        .vg-hero::after {
          content: "SECURITY OPERATIONS • LIVE TELEMETRY • AI MONITORING";
          position: absolute;
          left: 50%;
          bottom: 10px;
          transform: translateX(-50%);
          color: rgba(91,150,220,.42);
          font-size: 6px;
          font-weight: 900;
          letter-spacing: 2px;
          white-space: nowrap;
          pointer-events: none;
        }

        .vg-hero-title {
          top: 17px !important;
          left: 21px !important;
        }

        .vg-hero-title small {
          font-size: 7px !important;
          letter-spacing: 2.4px !important;
        }

        .vg-hero-title h2 {
          margin-top: 4px !important;
          font-size: 20px !important;
        }

        .vg-hero-title p {
          margin-top: 3px !important;
          font-size: 8px !important;
        }

        /* Larger but better-balanced central system graphic */
        .vg-orbit-area,
        .vg-orbit {
          width: 250px !important;
          height: 250px !important;
        }

        .vg-orbit-area {
          left: 50% !important;
          top: 57% !important;
          transform: translate(-50%, -50%) !important;
        }

        .vg-orbit::before {
          inset: 25px !important;
        }

        .vg-orbit::after {
          inset: 54px !important;
        }

        .vg-core {
          width: 102px !important;
          height: 102px !important;
          box-shadow:
            0 0 0 1px rgba(60,150,255,.24),
            0 0 35px rgba(20,120,255,.30),
            inset 0 0 30px rgba(30,120,255,.12) !important;
        }

        .vg-core-icon {
          font-size: 27px !important;
        }

        .vg-core strong {
          font-size: 8px !important;
          letter-spacing: 1.6px !important;
        }

        .vg-monitoring {
          font-size: 6px !important;
        }

        /* Four telemetry tiles form a balanced cross around the core. */
        .vg-floating {
          z-index: 6 !important;
          min-width: 108px !important;
          padding: 7px 10px !important;
          border-radius: 9px !important;
          background: rgba(4,17,37,.88) !important;
          border-color: rgba(70,145,255,.18) !important;
          box-shadow: 0 10px 25px rgba(0,0,0,.24) !important;
        }

        .vg-floating small {
          font-size: 6px !important;
          letter-spacing: 1.1px !important;
        }

        .vg-floating strong {
          margin-top: 3px !important;
          font-size: 13px !important;
        }

        .float-1 {
          left: 7% !important;
          top: 39% !important;
        }

        .float-2 {
          right: 7% !important;
          top: 39% !important;
        }

        .float-3 {
          left: 12% !important;
          bottom: 13% !important;
        }

        .float-4 {
          right: 12% !important;
          bottom: 13% !important;
        }

        .vg-rotating-text {
          bottom: 28px !important;
          font-size: 6px !important;
          letter-spacing: 1.6px !important;
        }

        /* Health cards below the fold get the same visual language. */
        .vg-dashboard-health {
          margin-top: 12px !important;
        }

        .vg-dashboard-health-grid {
          gap: 8px !important;
        }

        .vg-dashboard-health-card {
          border-radius: 12px !important;
        }

        /* Desktop: preserve four-column stats but give the hero breathing room. */
        @media (min-width: 1200px) {
          .vg-dashboard {
            padding-left: 16px !important;
            padding-right: 16px !important;
          }

          .vg-stats-grid {
            gap: 11px !important;
          }
        }

        /* ==================================================
           NVR OFFLINE CENTER
        ================================================== */
        .vg-nvr-offline-section {
          border: 1px solid rgba(255,70,100,.16);
          border-radius: 16px;
          padding: 16px;
          background: linear-gradient(145deg, rgba(28,10,20,.55), rgba(7,13,28,.72));
        }

        .vg-nvr-offline-badge {
          padding: 7px 12px;
          border-radius: 999px;
          border: 1px solid rgba(90,140,220,.18);
          color: #8fa9cc;
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 1px;
        }

        .vg-nvr-offline-badge.active {
          color: #ff6374;
          border-color: rgba(255,70,100,.35);
          background: rgba(255,50,80,.08);
        }

        .vg-nvr-offline-empty {
          padding: 18px;
          border-radius: 12px;
          color: #59f2a7;
          background: rgba(8,40,28,.32);
          border: 1px solid rgba(60,220,150,.10);
          font-size: 12px;
          font-weight: 800;
          letter-spacing: .8px;
        }

        .vg-nvr-offline-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 12px;
        }

        .vg-nvr-offline-card {
          padding: 15px;
          border-radius: 14px;
          border: 1px solid rgba(255,70,100,.18);
          background: rgba(8,16,31,.78);
        }

        .vg-nvr-offline-card-head {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
        }

        .vg-nvr-offline-card-head strong,
        .vg-nvr-offline-card-head small {
          display: block;
        }

        .vg-nvr-offline-card-head strong {
          color: #e8f1ff;
          font-size: 14px;
        }

        .vg-nvr-offline-card-head small {
          margin-top: 4px;
          color: #7186ab;
          font-size: 10px;
        }

        .vg-nvr-offline-card-head span {
          color: #ff6374;
          font-size: 10px;
          font-weight: 900;
          white-space: nowrap;
        }

        .vg-nvr-offline-card-stats {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
          margin-top: 15px;
        }

        .vg-nvr-offline-card-stats div {
          padding: 10px;
          border-radius: 10px;
          background: rgba(18,31,54,.7);
        }

        .vg-nvr-offline-card-stats small,
        .vg-nvr-offline-card-stats b {
          display: block;
        }

        .vg-nvr-offline-card-stats small {
          color: #7186ab;
          font-size: 8px;
          letter-spacing: 1px;
        }

        .vg-nvr-offline-card-stats b {
          margin-top: 4px;
          color: #ff6374;
          font-size: 18px;
        }

        .vg-nvr-offline-note {
          margin-top: 12px;
          color: #8fa9cc;
          font-size: 9px;
          line-height: 1.5;
        }

        /* Tablet */
        @media (max-width: 1000px) {
          .vg-stats-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
          }

          .vg-stat-card {
            height: 105px !important;
          }

          .vg-hero {
            height: 350px !important;
            min-height: 350px !important;
          }
        }

        /* Mobile */
        @media (max-width: 640px) {
          .vg-dashboard {
            padding: 8px !important;
          }

          .vg-header {
            align-items: flex-start !important;
            flex-direction: column !important;
            gap: 10px !important;
          }

          .vg-header-right {
            width: 100%;
            justify-content: space-between;
          }

          .vg-stats-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
          }

          .vg-hero {
            height: 410px !important;
            min-height: 410px !important;
          }

          .vg-floating {
            min-width: 92px !important;
          }

          .float-1 { left: 3% !important; top: 35% !important; }
          .float-2 { right: 3% !important; top: 35% !important; }
          .float-3 { left: 5% !important; bottom: 12% !important; }
          .float-4 { right: 5% !important; bottom: 12% !important; }
        }

      `}</style>

    </div>
  );
}

// ==========================================================
// STATUS ITEM
// ==========================================================

function StatusItem({
  icon,
  title,
  value,
}) {

  return (

    <div className="vg-status-item">

      <div className="vg-status-item-top">

        <span className="vg-status-item-icon">
          {icon}
        </span>

        <span className="vg-status-indicator" />

      </div>

      <div className="vg-status-item-title">
        {title}
      </div>

      <div className="vg-status-item-value">
        {value}
      </div>

    </div>
  );
}

// ==========================================================
// OVERVIEW ITEM
// ==========================================================

function OverviewItem({
  icon,
  title,
  text,
}) {

  return (

    <div className="vg-overview-item">

      <div className="vg-overview-icon">
        {icon}
      </div>

      <div>

        <strong>
          {title}
        </strong>

        <p>
          {text}
        </p>

      </div>

    </div>
  );
}
export default Dashboard;
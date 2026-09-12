import Loader from "../components/Loader";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import api from "../services/api";
import "./Cameras.css";

export default function Cameras() {
  const [cameras, setCameras] = useState([]);
  const [nvrs, setNvrs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedNvr, setSelectedNvr] = useState("ALL");
  const [search, setSearch] = useState("");
  const [searchParams] = useSearchParams();
  const [selected, setSelected] = useState([]);
  const [bulk, setBulk] = useState({ name: "", ip: "", enabled: "" });
  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(null);

  useEffect(() => {
    const q = searchParams.get("search");
    if (q) setSearch(q);
  }, [searchParams]);

  async function load() {
    try {
      const [cameraResponse, nvrResponse] = await Promise.all([
        api.get("/cameras"),
        api.get("/nvr/status"),
      ]);

      setCameras(
        Array.isArray(cameraResponse.data)
          ? cameraResponse.data
          : []
      );

      setNvrs(
        Array.isArray(nvrResponse.data)
          ? nvrResponse.data
          : []
      );
    } catch (error) {
      console.error("Camera load failed", error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();

    const timer = setInterval(load, 5000);

    return () => clearInterval(timer);
  }, []);

  /*
   * IMPORTANT:
   * A camera must be treated as OFFLINE when its parent NVR
   * is OFFLINE, even if the camera API still contains its
   * previous/last-known status as "Online".
   */
  const effectiveCameras = useMemo(() => {
    const nvrStatusMap = new Map(
      nvrs
        .filter((nvr) => nvr && nvr.name)
        .map((nvr) => [
          String(nvr.name).trim(),
          String(nvr.status || "").trim().toUpperCase(),
        ])
    );

    return cameras.map((camera) => {
      const cameraNvr = String(camera.nvr || "").trim();
      const nvrStatus = nvrStatusMap.get(cameraNvr);

      if (nvrStatus === "OFFLINE") {
        return {
          ...camera,
          status: "Offline",
          nvrOffline: true,
        };
      }

      return {
        ...camera,
        nvrOffline: false,
      };
    });
  }, [cameras, nvrs]);

  const groups = useMemo(() => {
    return [...new Set(nvrs.map((n) => n.name).filter(Boolean))]
      .sort((a, b) =>
        a.localeCompare(b, undefined, { numeric: true })
      );
  }, [nvrs]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase().trim();

    return effectiveCameras.filter((c) => {
      const nvrMatch =
        selectedNvr === "ALL" || c.nvr === selectedNvr;

      const text =
        `${c.name} ${c.ip} ${c.nvr} ${c.id}`.toLowerCase();

      return nvrMatch && (!q || text.includes(q));
    });
  }, [effectiveCameras, selectedNvr, search]);

  const allFilteredSelected =
    filtered.length > 0 &&
    filtered.every((c) =>
      selected.includes(`${c.nvr}:${c.id}`)
    );

  const toggleOne = (camera) => {
    const key = `${camera.nvr}:${camera.id}`;

    setSelected((old) =>
      old.includes(key)
        ? old.filter((x) => x !== key)
        : [...old, key]
    );
  };

  const toggleAll = () => {
    const keys = filtered.map(
      (c) => `${c.nvr}:${c.id}`
    );

    if (allFilteredSelected) {
      setSelected((old) =>
        old.filter((x) => !keys.includes(x))
      );
    } else {
      setSelected((old) =>
        [...new Set([...old, ...keys])]
      );
    }
  };

  const selectedCameras = effectiveCameras.filter((c) =>
    selected.includes(`${c.nvr}:${c.id}`)
  );

  async function applyBulk() {
    const changes = {};

    if (bulk.name.trim()) changes.name = bulk.name.trim();
    if (bulk.ip.trim()) changes.ip = bulk.ip.trim();
    if (bulk.enabled !== "") {
      changes.enabled = bulk.enabled === "true";
    }

    if (!Object.keys(changes).length) {
      return setMessage(
        "Choose at least one setting to change."
      );
    }

    try {
      const res = await api.post(
        "/cameras/bulk-update",
        {
          cameras: selectedCameras,
          changes,
        }
      );

      setMessage(
        `Updated ${res.data.updated || 0} camera(s); failed ${res.data.failed || 0}.`
      );

      setBulk({
        name: "",
        ip: "",
        enabled: "",
      });

      await load();
    } catch (error) {
      setMessage(
        error?.response?.data?.detail ||
          "Bulk update failed."
      );
    }
  }

  async function saveSingle() {
    if (!editing) return;

    const changes = {};

    if (editing.name.trim()) {
      changes.name = editing.name.trim();
    }

    if (editing.ip.trim()) {
      changes.ip = editing.ip.trim();
    }

    if (editing.enabled !== editing.originalEnabled) {
      changes.enabled = editing.enabled;
    }

    try {
      await api.post(
        `/cameras/${encodeURIComponent(editing.nvr)}/${editing.id}/settings`,
        { changes }
      );

      setMessage(
        `${editing.name} updated successfully.`
      );

      setEditing(null);

      await load();
    } catch (error) {
      setMessage(
        error?.response?.data?.detail ||
          "Camera update failed."
      );
    }
  }

  if (loading) {
    return <Loader text="Loading Cameras..." />;
  }

  const online = effectiveCameras.filter(
    (c) =>
      String(c.status).toLowerCase() === "online"
  ).length;

  const offline = effectiveCameras.length - online;

  const offlineNvrNames = nvrs
    .filter(
      (nvr) =>
        String(nvr.status || "").toUpperCase() ===
        "OFFLINE"
    )
    .map((nvr) => nvr.name)
    .filter(Boolean);

  return (
    <div className="vg-cameras-page">

      <div className="vg-camera-header">
        <div>
          <div className="vg-eyebrow">
            NVR SECURITY OPERATIONS CENTER
          </div>

          <h1>Camera Management</h1>

          <p>
            Change one camera or select multiple cameras
            across multiple NVRs and apply settings together.
          </p>
        </div>

        <div className="vg-live-pill">
          ● Live Monitoring
        </div>
      </div>

      <div className="vg-camera-stats">

        <div>
          <span>Total Cameras</span>
          <strong>{effectiveCameras.length}</strong>
          <small>Discovered inventory</small>
        </div>

        <div>
          <span>Online</span>
          <strong className="green">{online}</strong>
          <small>Currently reachable</small>
        </div>

        <div>
          <span>Offline</span>
          <strong className="red">{offline}</strong>
          <small>
            {offlineNvrNames.length > 0
              ? `${offlineNvrNames.length} NVR offline`
              : "Requires attention"}
          </small>
        </div>

        <div>
          <span>NVRs</span>
          <strong>{groups.length}</strong>
          <small>
            {offlineNvrNames.length > 0
              ? `${offlineNvrNames.length} offline`
              : "Camera sources"}
          </small>
        </div>

      </div>

      {offlineNvrNames.length > 0 && (
        <div
          className="vg-camera-message"
          style={{
            borderLeft: "4px solid #ef4444",
            marginBottom: "16px",
          }}
        >
          <span>
            🔴 <strong>NVR Offline:</strong>{" "}
            {offlineNvrNames.join(", ")}
            {" — "}
            all cameras belonging to these NVRs are
            shown as Offline.
          </span>
        </div>
      )}

      <div className="vg-camera-control">

        <div className="vg-nvr-filter">

          <div className="vg-filter-title">
            Camera Scope
          </div>

          <div className="vg-filter-buttons">

            <button
              className={
                selectedNvr === "ALL" ? "active" : ""
              }
              onClick={() => setSelectedNvr("ALL")}
            >
              All NVRs <b>{effectiveCameras.length}</b>
            </button>

            {groups.map((nvr) => {
              const nvrOffline = nvrs.some(
                (item) =>
                  item.name === nvr &&
                  String(item.status || "").toUpperCase() ===
                    "OFFLINE"
              );

              return (
                <button
                  key={nvr}
                  className={
                    selectedNvr === nvr ? "active" : ""
                  }
                  onClick={() => setSelectedNvr(nvr)}
                >
                  {nvr}
                  {nvrOffline ? " 🔴" : ""}
                  {" "}
                  <b>
                    {
                      effectiveCameras.filter(
                        (c) => c.nvr === nvr
                      ).length
                    }
                  </b>
                </button>
              );
            })}

          </div>
        </div>

        <div className="vg-camera-search">

          <span>⌕</span>

          <input
            placeholder="Search camera name, IP, channel or NVR..."
            value={search}
            onChange={(e) =>
              setSearch(e.target.value)
            }
          />

          <button onClick={toggleAll}>
            {allFilteredSelected
              ? "Clear Shown"
              : `Select ${filtered.length} Shown`}
          </button>

        </div>

      </div>

      {selected.length > 0 && (
        <div className="vg-bulk-camera">

          <div className="vg-bulk-head">

            <div>
              <strong>Bulk Camera Settings</strong>

              <span>
                {selected.length} cameras selected across{" "}
                {
                  new Set(
                    selectedCameras.map(
                      (c) => c.nvr
                    )
                  ).size
                } NVR(s)
              </span>
            </div>

            <button
              onClick={() => setSelected([])}
            >
              Clear Selection
            </button>

          </div>

          <div className="vg-bulk-note">
            Only filled fields are changed. For IP changes,
            use unique target addresses to avoid creating an
            IP conflict.
          </div>

          <div className="vg-bulk-fields">

            <input
              placeholder="New camera name"
              value={bulk.name}
              onChange={(e) =>
                setBulk({
                  ...bulk,
                  name: e.target.value,
                })
              }
            />

            <input
              placeholder="New IP address"
              value={bulk.ip}
              onChange={(e) =>
                setBulk({
                  ...bulk,
                  ip: e.target.value,
                })
              }
            />

            <select
              value={bulk.enabled}
              onChange={(e) =>
                setBulk({
                  ...bulk,
                  enabled: e.target.value,
                })
              }
            >
              <option value="">
                Enable / Disable
              </option>
              <option value="true">
                Enable
              </option>
              <option value="false">
                Disable
              </option>
            </select>

            <button onClick={applyBulk}>
              Apply to Selected
            </button>

          </div>

        </div>
      )}

      {message && (
        <div className="vg-camera-message">
          <span>{message}</span>

          <button
            onClick={() => setMessage("")}
          >
            ×
          </button>
        </div>
      )}

      <div className="vg-camera-inventory">

        <div className="vg-inventory-head">

          <div>
            <strong>Camera Inventory</strong>
            <span>
              Live camera configuration and status
            </span>
          </div>

          <b>{filtered.length} shown</b>

        </div>

        <div className="vg-camera-table-wrap">

          <table className="vg-camera-table">

            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={allFilteredSelected}
                    onChange={toggleAll}
                  />
                </th>
                <th>Camera</th>
                <th>IP</th>
                <th>NVR</th>
                <th>Channel</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>

            <tbody>

              {filtered.map((camera) => {
                const key =
                  `${camera.nvr}:${camera.id}`;

                const isOffline =
                  String(camera.status).toLowerCase() !==
                  "online";

                return (
                  <tr key={key}>

                    <td>
                      <input
                        className="vg-check"
                        type="checkbox"
                        checked={selected.includes(key)}
                        onChange={() =>
                          toggleOne(camera)
                        }
                      />
                    </td>

                    <td>
                      <strong>{camera.name}</strong>
                    </td>

                    <td className="mono">
                      {camera.ip || "-"}
                    </td>

                    <td>
                      {camera.nvr}
                    </td>

                    <td>
                      CH-{camera.id}
                    </td>

                    <td>
                      <span
                        className={`vg-camera-status ${
                          isOffline
                            ? "offline"
                            : "online"
                        }`}
                      >
                        {isOffline
                          ? "🔴 Offline"
                          : "🟢 Online"}

                        {camera.nvrOffline
                          ? " • NVR Offline"
                          : ""}
                      </span>
                    </td>

                    <td>
                      <button
                        className="vg-edit-btn"
                        onClick={() =>
                          setEditing({
                            ...camera,
                            enabled:
                              camera.enabled !== false,
                            originalEnabled:
                              camera.enabled !== false,
                          })
                        }
                      >
                        Edit
                      </button>
                    </td>

                  </tr>
                );
              })}

              {!filtered.length && (
                <tr>
                  <td
                    colSpan="7"
                    className="vg-empty"
                  >
                    No cameras found.
                  </td>
                </tr>
              )}

            </tbody>

          </table>

        </div>
      </div>

      {editing && (
        <div className="vg-modal-backdrop">

          <div className="vg-camera-modal">

            <div className="vg-modal-head">

              <div>
                <span>
                  CAMERA CONFIGURATION
                </span>

                <h3>
                  {editing.nvr} • CH-{editing.id}
                </h3>
              </div>

              <button
                onClick={() => setEditing(null)}
              >
                ×
              </button>

            </div>

            <div className="vg-modal-body">

              <label>
                Camera Name

                <input
                  value={editing.name}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      name: e.target.value,
                    })
                  }
                />
              </label>

              <label>
                Camera IP

                <input
                  value={editing.ip || ""}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      ip: e.target.value,
                    })
                  }
                />
              </label>

              <label>
                State

                <select
                  value={String(editing.enabled)}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      enabled:
                        e.target.value === "true",
                    })
                  }
                >
                  <option value="true">
                    Enabled
                  </option>

                  <option value="false">
                    Disabled
                  </option>
                </select>
              </label>

            </div>

            <div className="vg-modal-footer">

              <button
                className="secondary"
                onClick={() =>
                  setEditing(null)
                }
              >
                Cancel
              </button>

              <button
                className="primary"
                onClick={saveSingle}
              >
                Save Camera
              </button>

            </div>

          </div>

        </div>
      )}

    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import api from "../services/api";

function CameraTable() {
  const [cameras, setCameras] = useState([]);
  const [nvrs, setNvrs] = useState([]);
  const [search, setSearch] = useState("");

  async function loadCameras() {
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
      setCameras([]);
      setNvrs([]);
    }
  }

  useEffect(() => {
    loadCameras();

    const interval = setInterval(
      loadCameras,
      5000
    );

    return () => clearInterval(interval);
  }, []);

  /*
   * IMPORTANT:
   * If an NVR is offline, all cameras belonging to that
   * NVR are shown as Offline, even if their last-known
   * camera status is still Online.
   */
  const effectiveCameras = useMemo(() => {
    const nvrStatusMap = new Map(
      nvrs
        .filter((nvr) => nvr && nvr.name)
        .map((nvr) => [
          String(nvr.name).trim(),
          String(nvr.status || "")
            .trim()
            .toUpperCase(),
        ])
    );

    return cameras.map((camera) => {
      const cameraNvr = String(
        camera.nvr || ""
      ).trim();

      const nvrStatus =
        nvrStatusMap.get(cameraNvr);

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

  const filteredCameras = effectiveCameras.filter(
    (camera) =>
      String(camera.name || "")
        .toLowerCase()
        .includes(search.toLowerCase()) ||
      String(camera.nvr || "")
        .toLowerCase()
        .includes(search.toLowerCase()) ||
      String(camera.ip || "")
        .toLowerCase()
        .includes(search.toLowerCase())
  );

  const offlineNvrCount = nvrs.filter(
    (nvr) =>
      String(nvr.status || "").toUpperCase() ===
      "OFFLINE"
  ).length;

  return (
    <div className="card shadow-lg border-0 mt-4">

      <div className="card-header bg-dark text-white d-flex justify-content-between align-items-center">

        <h5 className="mb-0">
          📹 Camera Monitoring
        </h5>

        <span className="badge bg-primary">
          Total : {filteredCameras.length}
        </span>

      </div>

      <div className="card-body">

        {offlineNvrCount > 0 && (
          <div className="alert alert-danger">
            🔴 <strong>{offlineNvrCount} NVR</strong>{" "}
            offline — cameras belonging to the
            offline NVR are shown as Offline.
          </div>
        )}

        <div className="row mb-3">

          <div className="col-md-4">

            <input
              type="text"
              className="form-control"
              placeholder="🔍 Search Camera, NVR or IP..."
              value={search}
              onChange={(e) =>
                setSearch(e.target.value)
              }
            />

          </div>

        </div>

        <div className="table-responsive">

          <table className="table table-hover align-middle">

            <thead className="table-dark">

              <tr>
                <th>#</th>
                <th>Camera Name</th>
                <th>Status</th>
                <th>NVR</th>
                <th>IP Address</th>
              </tr>

            </thead>

            <tbody>

              {filteredCameras.length > 0 ? (

                filteredCameras.map(
                  (camera, index) => {

                    const isOffline =
                      String(
                        camera.status
                      ).toLowerCase() !==
                      "online";

                    return (
                      <tr key={camera.id}>

                        <td>
                          {index + 1}
                        </td>

                        <td>
                          <strong>
                            {camera.name}
                          </strong>
                        </td>

                        <td>

                          {isOffline ? (

                            <span className="badge bg-danger px-3 py-2">
                              🔴 Offline
                              {camera.nvrOffline
                                ? " • NVR Offline"
                                : ""}
                            </span>

                          ) : (

                            <span className="badge bg-success px-3 py-2">
                              🟢 Online
                            </span>

                          )}

                        </td>

                        <td>
                          {camera.nvr}
                        </td>

                        <td>
                          <code>
                            {camera.ip || "-"}
                          </code>
                        </td>

                      </tr>
                    );
                  }
                )

              ) : (

                <tr>

                  <td
                    colSpan="5"
                    className="text-center text-muted py-5"
                  >
                    📷 No Cameras Found
                  </td>

                </tr>

              )}

            </tbody>

          </table>

        </div>

      </div>

    </div>
  );
}

export default CameraTable;

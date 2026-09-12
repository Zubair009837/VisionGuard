import StorageChart from "../components/charts/StorageChart";

export default function Storage() {
  return (
    <div className="container-fluid py-4">
      <div className="mb-4">
        <h2 className="fw-bold text-white">Storage</h2>
        <p className="text-secondary mb-0">Live HDD capacity and free-space telemetry from all 9 configured NVRs.</p>
      </div>
      <StorageChart />
    </div>
  );
}

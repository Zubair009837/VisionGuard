import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

function PerformanceChart() {
  const data = [
    { time: "10:00", cpu: 42, ram: 38 },
    { time: "10:10", cpu: 50, ram: 44 },
    { time: "10:20", cpu: 61, ram: 48 },
    { time: "10:30", cpu: 47, ram: 41 },
    { time: "10:40", cpu: 55, ram: 50 },
    { time: "10:50", cpu: 40, ram: 37 },
  ];

  return (
    <div
      className="card border-0 shadow-lg"
      style={{
        background: "#111827",
        borderRadius: "18px",
      }}
    >
      <div className="card-body">

        <h5
          className="fw-bold mb-3"
          style={{ color: "#fff" }}
        >
          ⚡ CPU & RAM Usage
        </h5>

        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid stroke="#374151" />

            <XAxis dataKey="time" stroke="#9ca3af" />

            <YAxis stroke="#9ca3af" />

            <Tooltip />

            <Line
              type="monotone"
              dataKey="cpu"
              stroke="#22c55e"
              strokeWidth={3}
            />

            <Line
              type="monotone"
              dataKey="ram"
              stroke="#3b82f6"
              strokeWidth={3}
            />

          </LineChart>
        </ResponsiveContainer>

      </div>
    </div>
  );
}

export default PerformanceChart;
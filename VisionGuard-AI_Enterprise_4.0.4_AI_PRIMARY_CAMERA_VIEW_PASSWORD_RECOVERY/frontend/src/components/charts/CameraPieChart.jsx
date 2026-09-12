import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";

function CameraPieChart() {

  const data = [
    { name: "Online", value: 18 },
    { name: "Offline", value: 4 },
  ];

  const COLORS = ["#22c55e", "#ef4444"];

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
          📊 Camera Status
        </h5>

        <ResponsiveContainer width="100%" height={300}>
          <PieChart>

            <Pie
              data={data}
              dataKey="value"
              outerRadius={95}
              innerRadius={50}
              label
            >
              {data.map((entry, index) => (
                <Cell
                  key={index}
                  fill={COLORS[index]}
                />
              ))}
            </Pie>

            <Tooltip />

            <Legend />

          </PieChart>
        </ResponsiveContainer>

      </div>
    </div>
  );
}

export default CameraPieChart;
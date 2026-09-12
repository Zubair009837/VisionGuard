import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
} from "chart.js";

import { Doughnut } from "react-chartjs-2";

ChartJS.register(
  ArcElement,
  Tooltip,
  Legend
);

function CameraChart({ online, offline }) {

  const data = {
    labels: ["Online", "Offline"],
    datasets: [
      {
        label: "Camera Status",
        data: [online, offline],
        backgroundColor: [
          "#22c55e",
          "#ef4444",
        ],
        borderWidth: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: "bottom",
      },
    },
  };

  return (
    <div className="card shadow mt-4">
      <div className="card-header">
        <h5>Camera Status Chart</h5>
      </div>

      <div className="card-body">
        <div
          style={{
            maxWidth: "350px",
            margin: "0 auto",
          }}
        >
          <Doughnut
            data={data}
            options={options}
          />
        </div>
      </div>
    </div>
  );
}

export default CameraChart;
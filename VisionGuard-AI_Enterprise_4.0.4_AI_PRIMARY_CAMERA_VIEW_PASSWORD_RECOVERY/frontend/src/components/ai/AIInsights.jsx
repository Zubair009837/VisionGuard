import {
  FaBrain,
  FaCheckCircle,
  FaHdd,
  FaMicrochip,
  FaWifi,
} from "react-icons/fa";

function AIInsights() {
  const healthScore = 94;

  const recommendations = [
    {
      icon: <FaCheckCircle />,
      text: "Camera-12 Stable",
      color: "#22c55e",
    },
    {
      icon: <FaHdd />,
      text: "HDD Health Good",
      color: "#3b82f6",
    },
    {
      icon: <FaMicrochip />,
      text: "CPU Usage Normal",
      color: "#f59e0b",
    },
    {
      icon: <FaWifi />,
      text: "Network Excellent",
      color: "#06b6d4",
    },
  ];

  return (
    <div
      className="card border-0 shadow-lg h-100"
      style={{
        background: "linear-gradient(135deg,#0f172a,#1e293b)",
        color: "#fff",
        borderRadius: "20px",
      }}
    >
      <div className="card-body">

        <div className="d-flex align-items-center mb-4">
          <FaBrain
            size={30}
            style={{
              color: "#38bdf8",
              marginRight: "10px",
            }}
          />

          <div>
            <h5 className="mb-0 fw-bold">
              AI HEALTH
            </h5>

            <small
              style={{
                color: "#94a3b8",
              }}
            >
              VisionGuard Intelligence
            </small>
          </div>
        </div>

        <div className="text-center mb-4">

          <h1
            style={{
              fontSize: "58px",
              color: "#22c55e",
              fontWeight: "800",
            }}
          >
            {healthScore}%
          </h1>

          <small
            style={{
              color: "#94a3b8",
            }}
          >
            System Health Score
          </small>

        </div>

        <div
          className="progress mb-4"
          style={{
            height: "12px",
            borderRadius: "10px",
          }}
        >
          <div
            className="progress-bar bg-success"
            style={{
              width: `${healthScore}%`,
            }}
          ></div>
        </div>

        <h6 className="fw-bold mb-3">
          Recommendations
        </h6>

        {recommendations.map((item, index) => (
          <div
            key={index}
            className="d-flex align-items-center mb-3"
          >
            <div
              style={{
                color: item.color,
                width: "30px",
                fontSize: "20px",
              }}
            >
              {item.icon}
            </div>

            <span>{item.text}</span>
          </div>
        ))}

        <div
          className="mt-4 text-center"
          style={{
            background: "#22c55e22",
            padding: "12px",
            borderRadius: "12px",
            color: "#22c55e",
            fontWeight: "700",
          }}
        >
          No Critical Alerts
        </div>

      </div>
    </div>
  );
}

export default AIInsights;
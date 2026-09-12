function StatusCard({ title, value, color = "#0d6efd", icon }) {
  return (
    <div
      className="card border-0 h-100"
      style={{
        background: "linear-gradient(145deg, #0b1220, #111827)",
        borderLeft: `5px solid ${color}`,
        borderRadius: "18px",
        boxShadow: "0 10px 25px rgba(0,0,0,0.45)",
        transition: "all 0.3s ease",
        color: "#fff",
      }}
    >
      <div className="card-body">

        <div className="d-flex justify-content-between align-items-center">

          <div>

            <p
              style={{
                margin: 0,
                color: "#9CA3AF",
                fontSize: "14px",
                fontWeight: "600",
                letterSpacing: "0.5px",
              }}
            >
              {title}
            </p>

            <h2
              style={{
                marginTop: "12px",
                marginBottom: "10px",
                fontWeight: "800",
                color: "#ffffff",
                fontSize: "34px",
              }}
            >
              {value}
            </h2>

            <small
              style={{
                color: "#22c55e",
                fontWeight: "600",
              }}
            >
              ● Live Monitoring
            </small>

          </div>

          <div
            style={{
              width: "68px",
              height: "68px",
              borderRadius: "50%",
              background: `${color}25`,
              border: `2px solid ${color}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "30px",
              boxShadow: `0 0 20px ${color}55`,
            }}
          >
            {icon}
          </div>

        </div>

      </div>
    </div>
  );
}

export default StatusCard;
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { setSession } from "../services/auth";
import "../styles/login.css";

export default function Login() {
  const navigate = useNavigate();

  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [loading, setLoading] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setInfo("");
    setLoading(true);

    try {
      const response = await api.post("/auth/login", {
        username: username.trim(),
        password,
      });
      setSession(response.data);
      navigate("/", { replace: true });
    } catch (err) {
      console.error("[VISIONGUARD LOGIN ERROR]", err);
      const status = err.response?.status;
      const data = err.response?.data;
      const message =
        data?.detail ||
        data?.message ||
        data?.error ||
        err.message ||
        "Login failed. Check username and password.";
      setError(`Login failed${status ? ` (${status})` : ""}: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const forgotPassword = async () => {
    setError("");
    setInfo("");

    const cleanUsername = username.trim();
    if (!cleanUsername) {
      setError("Enter your username first.");
      return;
    }

    setResetLoading(true);

    try {
      const response = await api.post("/auth/password/forgot", {
        username: cleanUsername,
      });

      console.log("[VISIONGUARD PASSWORD RESET]", response.data);
      setInfo(
        response.data?.message ||
          "If the account is eligible, a password reset link has been sent to the registered recovery email."
      );
    } catch (err) {
      console.error("[VISIONGUARD PASSWORD RESET ERROR]", err);
      console.error("Status:", err.response?.status);
      console.error("Response:", err.response?.data);
      console.error("URL:", err.config?.url);
      console.error("Base URL:", err.config?.baseURL);

      const status = err.response?.status;
      const data = err.response?.data;
      let message =
        data?.detail ||
        data?.message ||
        data?.error ||
        err.message ||
        "Unknown error";

      if (Array.isArray(data?.detail)) {
        message = data.detail
          .map((item) => item?.msg || JSON.stringify(item))
          .join(", ");
      }

      setError(
        `Password reset failed${status ? ` (${status})` : ""}: ${message}`
      );
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <div className="vg-login-page">
      <div className="vg-login-glow vg-login-glow-one" />
      <div className="vg-login-glow vg-login-glow-two" />

      <form className="vg-login-card" onSubmit={submit}>
        <div className="vg-login-badge">🛡️</div>
        <div className="vg-login-eyebrow">VISIONGUARD AI • SECURE ACCESS</div>
        <h1>Security Operations Center</h1>
        <p>
          Sign in to access CCTV, NVR health, alerts and infrastructure intelligence.
        </p>

        <label>USERNAME</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          placeholder="Enter username"
          disabled={loading || resetLoading}
        />

        <label>PASSWORD</label>
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          autoComplete="current-password"
          placeholder="Enter password"
          disabled={loading || resetLoading}
        />

        {error && <div className="vg-login-error">⚠ {error}</div>}
        {info && <div className="vg-login-info">✓ {info}</div>}

        <button type="submit" disabled={loading || resetLoading}>
          {loading ? "AUTHENTICATING…" : "SIGN IN →"}
        </button>

        <button
          type="button"
          className="vg-forgot-password"
          onClick={forgotPassword}
          disabled={loading || resetLoading}
        >
          {resetLoading ? "SENDING RESET LINK…" : "Forgot password?"}
        </button>

        <div className="vg-login-footer">
          Enterprise monitoring access • Session protected
        </div>
      </form>
    </div>
  );
}

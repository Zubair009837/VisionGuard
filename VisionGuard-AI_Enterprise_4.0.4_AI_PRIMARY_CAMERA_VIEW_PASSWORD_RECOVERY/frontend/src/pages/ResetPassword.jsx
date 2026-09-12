import { useState } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import api from "../services/api";
import "../styles/login.css";

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!token) {
      setError("This password reset link is invalid or expired.");
      return;
    }
    if (password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const response = await api.post("/auth/password/reset", {
        token,
        password,
      });
      setSuccess(response.data?.message || "Password reset successfully.");
      setTimeout(() => navigate("/login", { replace: true }), 1600);
    } catch (err) {
      setError(err.response?.data?.detail || "Password reset failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="vg-login-page">
      <div className="vg-login-glow vg-login-glow-one" />
      <div className="vg-login-glow vg-login-glow-two" />
      <form className="vg-login-card" onSubmit={submit}>
        <div className="vg-login-badge">🔐</div>
        <div className="vg-login-eyebrow">VISIONGUARD AI • ACCOUNT RECOVERY</div>
        <h1>Reset Password</h1>
        <p>Create a new password for your VisionGuard application account.</p>

        <label>NEW PASSWORD</label>
        <input
          value={password}
          onChange={e => setPassword(e.target.value)}
          type="password"
          autoComplete="new-password"
          placeholder="Enter new password"
        />

        <label>CONFIRM PASSWORD</label>
        <input
          value={confirm}
          onChange={e => setConfirm(e.target.value)}
          type="password"
          autoComplete="new-password"
          placeholder="Confirm new password"
        />

        {error && <div className="vg-login-error">⚠ {error}</div>}
        {success && <div className="vg-login-info">✓ {success}</div>}

        <button disabled={loading}>{loading ? "UPDATING PASSWORD…" : "SET NEW PASSWORD →"}</button>
        <Link className="vg-forgot-password" to="/login">Back to sign in</Link>

        <div className="vg-login-footer">Reset links are one-time use and expire automatically.</div>
      </form>
    </div>
  );
}

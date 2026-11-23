import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setSession } from "../api";
import SiteBrand from "../components/SiteBrand";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const data = await api.login({ username, password });
      setSession(data.access_token, {
        display_name: data.display_name,
        role: data.role,
      });
      navigate("/qa");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell login-centered">
      <div className="login-card">
        <div className="login-brand center-brand">
          <SiteBrand
            to="/"
            title="Universidad de Manila"
            subtitle="Student Facility Evaluation System"
          />
        </div>

        <h1>Login</h1>
        <p className="lead login-sub">Sign in for authorization.</p>

        <form className="form" onSubmit={onSubmit}>
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error ? <p className="error">{error}</p> : null}
          <button className="btn primary full" type="submit" disabled={busy}>
            {busy ? "Logging in…" : "Login"}
          </button>
        </form>


      </div>
    </div>
  );
}

import { ROLE_DESCRIPTIONS, roleOf } from "../../permissions";
import RoleBadge from "../../components/RoleBadge";
import { useNotice } from "../../hooks/useNotice";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getProfile, api, clearSession } from "../../api";

export default function ProfilePage() {
  const profile = getProfile();
  const [username, setUsername] = useState(profile.username || "");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  // Load the real current username from the API (localStorage may not have it).
  useNotice(message,"success");
  useNotice(error,"error");
  useEffect(() => {
    api
      .me()
      .then((me) => {
        if (me?.username) setUsername(me.username);
      })
      .catch(() => {});
  }, []);
  const [newUsername, setNewUsername] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);

    try {
      // Password validation
      if (newPassword || confirmPassword) {
        if (newPassword !== confirmPassword) {
          throw new Error("New passwords do not match.");
        }
        if (newPassword.length < 12) {
          throw new Error("Password must be at least 12 characters.");
        }
        if (!/[a-zA-Z]/.test(newPassword) || !/[0-9]/.test(newPassword)) {
          throw new Error("Password must contain both letters and numbers.");
        }
      }

      // Username validation
      if (newUsername) {
        if (newUsername.length < 3 || newUsername.length > 20) {
          throw new Error("Username must be 3-20 characters.");
        }
        if (!/^[a-zA-Z0-9._]+$/.test(newUsername)) {
          throw new Error("Username can only contain letters, numbers, dots, and underscores.");
        }
      }

      // Only send fields that have values
      const updates = {current_password: currentPassword};
      if (newUsername) updates.new_username = newUsername;
      if (newPassword && currentPassword) {
        updates.current_password = currentPassword;
        updates.new_password = newPassword;
      }

      if (!newUsername && !newPassword) {
        setMessage("No changes to save.");
        setLoading(false);
        return;
      }

      if (!window.confirm("Are you sure you want to save your account changes? You will need to sign in again.")) return;

      // Call the profile update endpoint
      await api.updateProfile(updates);

      // Update local profile if username changed
      if (newUsername) {
        const updatedProfile = { ...profile, username: newUsername };
        localStorage.setItem("udm_qa_profile", JSON.stringify(updatedProfile));
        setUsername(newUsername);
      } else {
        const me = await api.me().catch(() => null);
        if (me?.username) setUsername(me.username);
      }

      clearSession();
      setMessage("Changes saved. Please sign in again with your updated credentials.");

      // Reset form
      setNewUsername("");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="profile-page">
      <header className="dash-topbar">
        <div className="dash-topbar-left">
          <h1 className="dash-title">Profile</h1>
          <div className="profile-role"><RoleBadge role={profile.role}/></div><p className="role-description">{ROLE_DESCRIPTIONS[roleOf(profile)]}</p>
          <p className="dash-subtitle">Change your username and password.</p>
        </div>
      </header>

      <section className="card profile-card">
        <h2>Change username &amp; password</h2>
        <p className="muted card-desc">Fill in only what you want to change. Passwords need 12+ characters with letters and numbers. Your current password is required to save changes.</p>

        <form onSubmit={handleSubmit}>
          {error && <p className="error">{error}</p>}
          {message.startsWith("Changes saved") && <Link className="btn primary" to="/qa/login">Sign in</Link>}

          <label className="pf-field">
            <span>Current Username</span>
            <input
              type="text"
              value={username}
              disabled
              style={{ background: "#f7faf8", cursor: "not-allowed" }}
            />
          </label>

          <label className="pf-field">
            <span>New Username</span>
            <input
              type="text"
              value={newUsername}
              onChange={(e) => setNewUsername(e.target.value)}
              placeholder="3–20 letters, numbers, dots or underscores"
            />
          </label>

          <label className="pf-field">
            <span>Current Password</span>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </label>

          <div className="pf-row">
            <label className="pf-field">
              <span>New Password</span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </label>
            <label className="pf-field">
              <span>Confirm New Password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </label>
          </div>

          <button type="submit" className="btn primary" disabled={loading}>
            {loading ? "Saving…" : "Save changes"}
          </button>
        </form>
      </section>
    </div>
  );
}

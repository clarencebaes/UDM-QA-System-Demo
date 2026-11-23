import { NavLink, useNavigate } from "react-router-dom";
import { api, clearSession, getProfile, getToken } from "../api";
import SiteBrand from "./SiteBrand";

export default function Navbar() {
  const navigate = useNavigate();
  const loggedIn = Boolean(getToken());
  const profile = getProfile();

  async function logout() {
    try { await api.logout(); } finally {clearSession();navigate("/qa/login");}
  }

  return (
    <header className="nav">
      <div className="nav-inner nav-minimal">
        <SiteBrand
          to="/"
          title="Student Facility Evaluation"
          subtitle="Universidad de Manila"
        />
        <nav><NavLink to="/" end>Home</NavLink><NavLink to="/about">About</NavLink><NavLink to="/faqs">FAQs</NavLink><NavLink to="/concern">Report</NavLink></nav>
        {loggedIn ? (
          <nav>
            <NavLink to="/qa">Dashboard</NavLink>
            <button type="button" className="linkish" onClick={logout}>
              Log out {profile.display_name ? `(${profile.display_name})` : ""}
            </button>
          </nav>
        ) : null}
      </div>
    </header>
  );
}

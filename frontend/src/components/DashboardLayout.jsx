import PrefetchLink from "./PrefetchLink";
import { NavLink, Outlet, useNavigate, useLocation, Navigate } from "react-router-dom";
import { api, clearSession, getProfile, getToken, setSession } from "../api";
import { useEffect, useState } from "react";
import { can, roleOf } from "../permissions";
import RoleBadge from "./RoleBadge";
import SiteFooter from "./SiteFooter";

const NAV_GROUPS = [
  ["Main", [{to:"/qa", end:true, label:"My workspace", area:"home", icon:"dashboard"}, {to:"/qa/dashboard",label:"Dashboard",area:"dashboard",icon:"dashboard"}]],
  ["Records", [{to:"/qa/feedback-log",label:"Feedback",area:"feedback",icon:"feedback"},{to:"/qa/alerts",label:"Interventions",area:"alerts",icon:"interventions"},{to:"/qa/history",label:"History",area:"history",icon:"history"},{to:"/qa/concerns",label:"Student concerns",area:"concerns",icon:"feedback"}]],
  ["Oversight", [{to:"/qa/analytics",label:"Analytics",area:"analytics",icon:"analytics"},{to:"/qa/reports",label:"Make a report",area:"reports",icon:"analytics"},{to:"/qa/audit",label:"Audit trail",area:"audit",icon:"history"}]],
  ["Administration", [{to:"/qa/users",label:"Users",area:"users",icon:"profile"},{to:"/qa/settings",label:"Settings",area:"settings",icon:"settings"},{to:"/qa/backup",label:"Backup & restore",area:"backup",icon:"settings"}]],
  ["Help & account", [{to:"/qa/faqs",label:"FAQs",area:"help",icon:"feedback"},{to:"/qa/about",label:"About",area:"help",icon:"survey"},{to:"/qa/profile",label:"My profile",area:"profile",icon:"profile"}]],
];

const ICONS = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.2" />
      <rect x="14" y="3" width="7" height="7" rx="1.2" />
      <rect x="3" y="14" width="7" height="7" rx="1.2" />
      <rect x="14" y="14" width="7" height="7" rx="1.2" />
    </>
  ),
  feedback: (
    <path d="M21 12a8 8 0 01-11.6 7.1L4 20l1-4.6A8 8 0 1121 12z" />
  ),
  analytics: (
    <>
      <path d="M4 19V5" />
      <path d="M4 19h16" />
      <rect x="7" y="11" width="3" height="8" rx="0.6" />
      <rect x="12" y="7" width="3" height="12" rx="0.6" />
      <rect x="17" y="13" width="3" height="6" rx="0.6" />
    </>
  ),
  interventions: (
    <>
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
      <path d="M10.29 4.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 4.86a2 2 0 00-3.42 0z" />
    </>
  ),
  history: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  profile: (
    <>
      <circle cx="12" cy="8" r="3.2" />
      <path d="M5.5 19a6.5 6.5 0 0113 0" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 01-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 01-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 01-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 010-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 012.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 014 0v.1a1.7 1.7 0 001.1 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 012.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 010 4h-.1a1.7 1.7 0 00-1.5 1z" />
    </>
  ),
  survey: (
    <>
      <path d="M14 3h7v7" />
      <path d="M10 14L21 3" />
      <path d="M21 14v6a1 1 0 01-1 1H4a1 1 0 01-1-1V4a1 1 0 011-1h6" />
    </>
  ),
  logout: (
    <>
      <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </>
  ),
};

function NavIcon({ name }) {
  const inner = ICONS[name];
  if (!inner) return null;
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {inner}
    </svg>
  );
}

export default function DashboardLayout() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState(getProfile());
  const [ready,setReady] = useState(false);
  const [menuOpen,setMenuOpen] = useState(false);
  const location = useLocation();
  const role = roleOf(profile);
  const item = NAV_GROUPS.flatMap(([,items])=>items).find(i=>i.to===location.pathname);


  useEffect(() => {
    setMenuOpen(false);
    let active = true;
    if (!getToken()) { navigate("/qa/login", {replace:true}); return; }
    api.me().then(data=>{if(active){setProfile(data);setSession(getToken(),data);setReady(true);}}).catch(()=>{clearSession();navigate("/qa/login",{replace:true});});
    return ()=>{active=false;};
  }, [navigate, location.pathname]);

  async function logout() {
    try { await api.logout(); } finally {clearSession();navigate("/qa/login");}
  }
  if (!ready) return <p className="ops-page" role="status">Checking your access…</p>;
  if (item && !can(role,item.area)) return <Navigate to="/qa" replace />;

  const initial = (profile.display_name || "Administrator").charAt(0).toUpperCase();

  return (
    <div className="dash-shell">
      <aside className="dash-sidebar">
        <div className="dash-brand">
          <div className={`dash-avatar role-${role}`} aria-hidden="true">{initial}</div>
          <div>
            <strong>{profile.display_name || "Administrator"}</strong>
            <small><RoleBadge role={role}/><span className="sidebar-unit">Quality Assurance</span></small>
          </div>
        </div>
        <button type="button" className="nav-toggle" aria-expanded={menuOpen} aria-controls="staff-navigation" onClick={()=>setMenuOpen(!menuOpen)}>{menuOpen ? "Close navigation" : "Open navigation"}</button>
        <nav id="staff-navigation" className={`dash-sidenav${menuOpen ? " is-open" : ""}`}>
          <div className="dash-sidenav-main">
            {NAV_GROUPS.map(([group,items])=>{
              const visible=items.filter(i=>can(role,i.area));
              return visible.length ? <section className="nav-group" key={group}><h2>{group}</h2>{visible.map(item=><PrefetchLink navigation key={item.to} to={item.to} end={item.end} className={({isActive})=>`dash-sidenav-item${isActive?" is-active":""}`}><NavIcon name={item.icon}/><span>{item.label}</span></PrefetchLink>)}</section>:null;
            })}
          </div>
          <div className="dash-sidenav-footer">
            <NavLink to="/" className="dash-sidenav-item dash-sidenav-item--survey">
              <NavIcon name="survey" />
              <span>Student survey page</span>
            </NavLink>
            <button type="button" className="dash-sidenav-item dash-sidenav-item--logout" onClick={logout}>
              <NavIcon name="logout" />
              <span>Log out</span>
            </button>
          </div>
        </nav>
      </aside>

      <div className="dash-body">
        <main className="dash-main">
          <Outlet />
        </main>
        <SiteFooter />
      </div>
    </div>
  );
}

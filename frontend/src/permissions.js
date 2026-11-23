// Insertion order is the displayed hierarchy.
export const ROLE_NAMES = {executive_director: "Executive Director", admin: "Administrator", assistant: "Staff", viewer: "Read-Only Viewer"};
export const roleOf = (profile) => ({qa: "executive_director", super_admin: "executive_director", department_head: "viewer"}[profile?.role] || profile?.role);
export const can = (role, area) => {
  if (role === "executive_director") return true;
  if (role === "admin") return area !== "restore";
  if (["home", "profile", "reports", "help"].includes(area)) return Boolean(ROLE_NAMES[role]);
  return role === "assistant" && ["dashboard", "feedback", "analytics", "alerts", "history"].includes(area);
};
export const ROLE_DESCRIPTIONS = {
  executive_director: "Highest authority. Manage all modules and accounts, approve interventions, review audits, and authorize data restoration.",
  admin: "Second in authority. Carry out delegated survey and account administration, prepare reports and drafts, manage concerns, and track approved actions. The Director approves interventions and manages Director accounts and restoration.",
  assistant: "View feedback, dashboards, analytics, interventions, history, and reports. Cannot change operational records or manage accounts and settings.",
  viewer: "View aggregate reports, help, and your own profile. Student identities and operational records are restricted."
};

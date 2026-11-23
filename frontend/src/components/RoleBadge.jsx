import { ROLE_NAMES, roleOf } from "../permissions";

export default function RoleBadge({ role }) {
  const normalized = roleOf({ role });
  return <span className={`role-badge role-${normalized}`}>{ROLE_NAMES[normalized] || "Staff"}</span>;
}

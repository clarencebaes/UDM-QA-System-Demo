const names = { users:"user account", alerts:"intervention", survey_settings:"survey settings", survey_cycles:"survey semester", thresholds:"alert threshold", intervention_rules:"recommendation rule", college_headcounts:"college enrollment", colleges:"college", student_concerns:"student concern", session:"staff session", aggregate_report:"evaluation report", application_data:"application backup" };
const fields = { username:"Username", role:"Role", is_active:"Status", display_name:"Display name", department_id:"Service area", status:"Workflow status", note:"Recommendation", quad_note:"QUAD remarks", completion_note:"Action taken", start_date:"Survey start", end_date:"Survey end", active_cycle_id:"Selected semester", min_trigger_count:"Minimum trigger count", service_area_scope:"Combined service-area scope", min_negative_count:"Minimum negative count", min_constructive_count:"Minimum constructive count", alert_window_days:"Alert window in days", default_goal:"Default goal", include_constructive:"Include constructive comments", headcount:"Enrolled students", recommendation:"Suggested recommendation", diagnosed_pattern:"Reported concern", min_count:"Minimum count", window_days:"Window in days", academic_year:"Academic year", semester:"Semester", staff_note:"Staff remarks", student_status:"Student status", intervention_status:"Intervention stage", account_security:"Account access" };
const values = { viewer:"Read-Only Viewer", assistant:"Staff", admin:"Administrator", executive_director:"Executive Director", super_admin:"Super Admin", new:"New alert", acknowledged:"Awaiting approval", "in-progress":"Approved / in progress", resolved:"Resolved / completed", reviewing:"In review", open:"Open", short_term:"Short term", long_term:"Long term" };
export function auditTarget(target = "") {
  const [table, id] = target.split(":");
  const label=names[table] || table.replaceAll("_", " ");
  return `${label.charAt(0).toUpperCase()+label.slice(1)}${id ? ` #${id}` : ""}`;
}
export function auditAction(action = "") {
  return ({ create:"Created", update:"Updated", delete:"Deleted", login:"Signed in", logout:"Signed out", login_failed:"Sign-in failed", access_denied:"Access denied", report_preview:"Previewed report", backup_created:"Downloaded encrypted backup", restore_completed:"Restored application data", concern_submitted:"Submitted a student concern", concern_deleted:"Deleted student concern", historical_period_assigned:"Assigned historical survey semester", historical_student_status_assigned:"Assigned confirmed historical student status", submit:"Submitted an evaluation" })[action] || action.replaceAll("_", " ").replace(/^./,c=>c.toUpperCase());
}
function readable(value, field, lookups = {}) {
  if (value == null || value === "") return "Not set";
  if (typeof value === "boolean") return field === "is_active" ? value ? "Activated" : "Deactivated" : value ? "Yes" : "No";
  if (field === "department_id") return lookups.departments?.find(d=>d.id===value)?.name || `Service area #${value}`;
  if (field === "active_cycle_id") return lookups.cycles?.find(c=>c.id===value)?.label || `Survey semester #${value}`;
  return values[value] || String(value);
}
export function auditChanges(event, lookups = {}) {
  let detail;
  try { detail = JSON.parse(event.detail); } catch { return [event.detail || `${auditAction(event.action)} ${auditTarget(event.target)}.`]; }
  if (!detail || typeof detail !== "object" || Array.isArray(detail)) return [String(detail || "No additional details recorded.")];
  return Object.entries(detail).map(([field, change]) => {
    const label = fields[field] || field.replaceAll("_", " ");
    if (change && typeof change === "object" && ("before" in change || "after" in change)) {
      const before = (change.before || []).map(v => readable(v,field,lookups)).join(", ") || "Not recorded";
      const after = (change.after || []).map(v => readable(v,field,lookups)).join(", ") || "Not set";
      return `${label}: ${before} → ${after}.`;
    }
    if (field === "colleges") return `Colleges: ${change.length ? change.join(", ") : "All colleges"}.`;
    if (field === "cycle_id") return `Evaluation period: ${change ? readable(change,"active_cycle_id",lookups) : "All semesters"}.`;
    if (field === "department_id") return `Service area: ${change ? readable(change,field,lookups) : "All service areas"}.`;
    return `${label}: ${readable(change,field)}.`;
  });
}

"""Write history in the same transaction as the business change; never copy secrets."""
import json
from sqlalchemy import event, inspect, func, case, or_
from sqlalchemy.orm import Session
from app.models import AuditEvent

SAFE_FIELDS = {"username", "role", "is_active", "display_name", "department_id", "status", "note", "quad_note",
               "completion_note", "start_date", "end_date", "active_cycle_id", "min_trigger_count",
               "min_negative_count", "min_constructive_count", "service_area_scope", "alert_window_days", "default_goal", "include_constructive", "headcount", "recommendation",
               "diagnosed_pattern", "min_count", "window_days", "academic_year", "semester", "staff_note"}
TRACKED = {"users", "alerts", "survey_settings", "survey_cycles", "thresholds", "intervention_rules",
           "college_headcounts", "colleges", "student_concerns"}

def record(db, actor, action, target, detail=""):
    db.add(AuditEvent(actor=actor, action=action, target=target, detail=detail))

@event.listens_for(Session, "before_flush")
def track_changes(db, context, instances):
    if db.info.get("skip_audit") or not db.info.get("actor"):
        return
    for obj in list(db.new) + list(db.dirty) + list(db.deleted):
        table = getattr(obj, "__tablename__", "")
        if table not in TRACKED:
            continue
        action = "delete" if obj in db.deleted else "create" if obj in db.new else "update"
        changes = {}
        for attr in inspect(obj).attrs:
            if attr.key in SAFE_FIELDS and attr.history.has_changes():
                changes[attr.key] = {"before": list(attr.history.deleted), "after": list(attr.history.added)}
        if action == "update" and not changes:
            if table != "users" or not db.is_modified(obj):
                continue
            changes = {"account_security": "Credentials or session access updated"}
        record(db, db.info["actor"], action, f"{table}:{getattr(obj, 'id', None) or getattr(obj, 'username', None) or getattr(obj, 'reference', None) or getattr(obj, 'code', 'new')}", json.dumps(changes, default=str))


def audit_search_clause(term):
    action_names={"create":"Created","update":"Updated","delete":"Deleted","login":"Signed in","logout":"Signed out","login_failed":"Sign-in failed","access_denied":"Access denied","report_preview":"Previewed report","backup_created":"Downloaded encrypted backup","restore_completed":"Restored application data","concern_submitted":"Submitted a student concern","concern_deleted":"Deleted student concern"}
    target_names={"users":"User account","alerts":"Intervention","survey_settings":"Survey settings","survey_cycles":"Survey semester","thresholds":"Alert threshold","intervention_rules":"Recommendation rule","college_headcounts":"College enrollment","colleges":"College","student_concerns":"Student concern","session":"Staff session","aggregate_report":"Evaluation report","application_data":"Application backup"}
    readable_action=case(action_names,value=AuditEvent.action,else_=func.replace(AuditEvent.action,"_"," "))
    readable_target=case(*[(AuditEvent.target.startswith(key+":"),func.replace(AuditEvent.target,key+":",label+" #")) for key,label in target_names.items()],else_=case(target_names,value=AuditEvent.target,else_=func.replace(AuditEvent.target,"_"," ")))
    columns=(AuditEvent.actor,AuditEvent.action,AuditEvent.target,AuditEvent.detail,readable_action,readable_target)
    return or_(*[func.lower(column).contains(term.strip().lower(),autoescape=True) for column in columns])

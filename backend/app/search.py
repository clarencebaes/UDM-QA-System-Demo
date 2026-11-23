"""Bounded staff search with server-side permission checks for every source."""
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import or_, cast, String
from sqlalchemy.orm import Session
from app.audit import audit_search_clause
from app.auth import get_current_user
from app.database import get_db
from app.access import authorize, role_of
from app.models import User, StudentConcern, AuditEvent, Alert, Aspect, Department, College, SurveyCycle, InterventionRule
from app.services.admin_reads import feedback_page

router = APIRouter(prefix="/api/qa")
MODULES = [
    ("Dashboard", "Participation, ratings and survey overview", "/qa/dashboard", "dashboard"),
    ("Feedback", "Student evaluations, comments and ratings", "/qa/feedback-log", "feedback"),
    ("Interventions", "Recommendations, approvals and action progress", "/qa/alerts", "alerts"),
    ("History", "Completed interventions and action taken", "/qa/history", "alerts"),
    ("Student concerns", "Survey access, submission, information and privacy concerns", "/qa/concerns", "concerns"),
    ("Analytics", "College, service area and aspect charts", "/qa/analytics", "dashboard"),
    ("Reports", "Semester evaluation reports and completed interventions", "/qa/reports", "reports"),
    ("Users", "Staff accounts, roles and access", "/qa/users", "users"),
    ("Audit trail", "Recorded changes and recent activity", "/qa/audit", "audit"),
    ("Settings", "Semester, survey dates, colleges and alert thresholds", "/qa/settings", "settings"),
    ("Backup & restore", "Download encrypted backup and restore", "/qa/backup", "backup"),
    ("My profile", "Username and password", "/qa/profile", "me"),
    ("FAQs", "Help using your account", "/qa/faqs", "me"),
    ("About", "Capstone project purpose", "/qa/about", "me"),
]

def permitted(user, resource):
    try:
        authorize(user, f"/api/qa/{resource}", "POST" if resource == "reports" else "GET")
        return True
    except HTTPException:
        return False

@router.get("/search")
def search(q: str = Query(min_length=2, max_length=120), cycle_id: int | None = Query(default=None, ge=1),
           college: str = "all", user=Depends(get_current_user), db: Session=Depends(get_db)):
    term = q.strip()
    if len(term) < 2: raise HTTPException(422, "Enter at least two characters.")
    def matches(column):
        if db.get_bind().dialect.name == "mysql": column = cast(column, String).collate("utf8mb4_unicode_ci")
        return column.contains(term, autoescape=True)
    groups=[]
    def add(label, total, items, url):
        if total: groups.append({"label":label,"total":total,"items":items,"url":url})
    links=[{"title":name,"description":description,"url":url} for name,description,url,resource in MODULES
           if permitted(user,resource) and term.casefold() in f"{name} {description}".casefold()]
    add("Pages",len(links),links,"/qa")
    if permitted(user,"feedback"):
        try:
            if cycle_id: db.info["read_cycle"]=cycle_id
            result=feedback_page(db,search=term,college=college,page_size=6,comments_only=False)
            params={"search":term,"college":college,"comments_only":"false"}
            if cycle_id: params["cycle_id"]=cycle_id
            url="/qa/feedback-log?"+urlencode(params)
            add("Evaluations",result["total"],[{"title":f"{f.department.name} · {(f.submission.college if f.submission else f.respondent.college if f.respondent else 'College unavailable')}",
                "description":f.comment or "Rating-only evaluation", "url":url+f"&feedback_id={f.id}"} for f in result["items"]],url)
        finally: db.info.pop("read_cycle",None)
    if permitted(user,"alerts"):
        rows=db.query(Alert).join(Aspect).outerjoin(Department).filter(or_(matches(Aspect.name),matches(Department.name),matches(Alert.note),matches(Alert.quad_note),matches(Alert.completion_note),matches(Alert.status)))
        add("Interventions",rows.count(),[{"title":f"{'All reported aspects' if a.service_area_scope else a.aspect.name} · {a.department.name if a.department else 'All service areas'}", "description":a.completion_note or a.quad_note or a.note or "Needs a recommendation", "url":f"/qa/alerts?action_id={a.id}"} for a in rows.order_by(Alert.updated_at.desc()).limit(6)],"/qa/alerts")
    if permitted(user,"concerns"):
        rows=db.query(StudentConcern).filter(or_(*[matches(c) for c in (StudentConcern.reference,StudentConcern.student_number,StudentConcern.email,StudentConcern.message,StudentConcern.category,StudentConcern.staff_note)]))
        add("Student concerns",rows.count(),[{"title":c.reference,"description":c.message,"url":f"/qa/concerns?search={c.reference}"} for c in rows.order_by(StudentConcern.created_at.desc()).limit(6)],"/qa/concerns?"+urlencode({"search":term}))
    if permitted(user,"users"):
        role_names={"viewer":"read-only viewer","assistant":"staff","admin":"administrator","executive_director":"executive director","super_admin":"executive director"}
        roles=[r for r,name in role_names.items() if term.casefold() in name]
        rows=db.query(User).filter(or_(matches(User.username),matches(User.display_name),User.role.in_(roles)))
        add("Users",rows.count(),[{"title":u.display_name,"description":f"{u.username} · {role_names.get(u.role,u.role)}", "url":"/qa/users?"+urlencode({"search":u.username})} for u in rows.order_by(User.display_name).limit(6)],"/qa/users?"+urlencode({"search":term}))
    if permitted(user,"audit"):
        rows=db.query(AuditEvent).filter(audit_search_clause(term))
        add("Audit trail",rows.count(),[{"title":e.actor,"description":e.action.replace("_"," ").capitalize(),"url":f"/qa/audit?event_id={e.id}"} for e in rows.order_by(AuditEvent.id.desc()).limit(6)],"/qa/audit?"+urlencode({"search":term}))
    if permitted(user,"settings"):
        items=[]
        for c in db.query(College).filter(or_(matches(College.code),matches(College.name))).limit(6):
            items.append({"title":f"{c.code} · {c.name}","description":"College settings", "url":"/qa/settings"})
        for c in db.query(SurveyCycle).filter(or_(matches(SurveyCycle.academic_year),matches(SurveyCycle.semester))).limit(6):
            items.append({"title":f"{c.academic_year} · {c.semester} semester","description":"Survey cycle", "url":"/qa/settings"})
        for r in db.query(InterventionRule).join(Aspect).filter(or_(matches(Aspect.name),matches(InterventionRule.diagnosed_pattern),matches(InterventionRule.recommendation))).limit(6):
            items.append({"title":r.aspect.name,"description":r.recommendation,"url":"/qa/settings"})
        add("Settings",len(items),items[:12],"/qa/settings")
    return {"query":term,"groups":groups,"total":sum(g["total"] for g in groups)}

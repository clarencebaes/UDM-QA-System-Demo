"""Aggregate report builder: one filter scope, no student identifiers or raw comments."""
from datetime import datetime, timezone
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from app.auth import get_current_user
from app.database import get_db
from app.models import Feedback, Respondent, SurveySubmission, SurveyCycle, Department, FeedbackLabel, Aspect, InterventionRule, Alert
from app.services.feedback_text import has_substantive_comment, has_comment, no_substantive_feedback
from app.services.aspect_labels import effective_aspect_links
from app.services.text_dimensions import polarity_sql, constructive_clause
from app.audit import record

router = APIRouter(prefix="/api/qa")

class ReportIn(BaseModel):
    cycle_id: int | None = None  # None = all periods; 0 = legacy
    colleges: list[str] = Field(default_factory=list, max_length=50)
    department_id: int | None = None
    student_status: Literal["all", "regular", "irregular"] = "all"
    language: Literal["all", "english", "tagalog", "taglish", "unclassified"] = "all"
    intervention_status: Literal["all", "awaiting", "approved", "completed"] = "all"

@router.post("/reports")
def report(body: ReportIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    cycle = db.get(SurveyCycle, body.cycle_id) if body.cycle_id else None
    if body.cycle_id and not cycle: raise HTTPException(404, "Survey cycle not found.")
    college = func.coalesce(SurveySubmission.college, Respondent.college)
    q = (db.query(Feedback).outerjoin(SurveySubmission, Feedback.submission_id == SurveySubmission.id)
         .outerjoin(Respondent, Feedback.respondent_id == Respondent.id)
         .join(Department, Feedback.department_id == Department.id)
         .outerjoin(FeedbackLabel, FeedbackLabel.feedback_id == Feedback.id))
    if body.cycle_id == 0: q = q.filter(Feedback.submission_id.is_(None))
    elif body.cycle_id: q = q.filter(func.coalesce(SurveySubmission.cycle_id, Feedback.cycle_id) == body.cycle_id)
    if body.colleges: q = q.filter(college.in_(body.colleges))
    if body.department_id: q = q.filter(Feedback.department_id == body.department_id)
    if body.student_status != "all": q = q.filter(func.coalesce(SurveySubmission.student_status, Feedback.student_status) == body.student_status)
    if body.language != "all":
        from app.services.text_dimensions import language_sql
        q = q.filter(has_substantive_comment(), language_sql() == ("undetermined" if body.language == "unclassified" else body.language))
    from app.services.evaluation_analytics import evaluation_analytics
    analytics = evaluation_analytics(q)
    from app.services.text_dimensions import text_dimensions
    analytics.update(text_dimensions(q))
    total, respondents, submissions = q.with_entities(func.count(Feedback.id), func.count(func.distinct(Feedback.respondent_id)), func.count(func.distinct(Feedback.submission_id))).one()
    comments,written_entries,no_comment_entries = q.with_entities(*[func.coalesce(func.sum(case((predicate,1),else_=0)),0) for predicate in (has_substantive_comment(),has_comment(),no_substantive_feedback())]).one()
    by_college = [{"college": c or "Unknown", "respondents": n, "evaluations": e, "completed_submissions": s}
        for c, n, e, s in q.with_entities(college, func.count(func.distinct(Feedback.respondent_id)), func.count(Feedback.id), func.count(func.distinct(Feedback.submission_id))).group_by(college).order_by(college)]
    ratings=[{key:row[key] for key in ("service_area","evaluations","rated_answers","mean")} for row in analytics["star_ratings"]]
    rating_key=lambda row:(row["mean"] is None,-(row["mean"] or 0),row["service_area"])
    ratings.sort(key=rating_key)
    analytics["star_ratings"].sort(key=rating_key)
    sentiment = {name: n for name, n in q.filter(has_substantive_comment()).with_entities(FeedbackLabel.sentiment, func.count(Feedback.id)).group_by(FeedbackLabel.sentiment) if name in {"positive", "negative", "constructive", "neutral"}}
    unclassified = comments - sum(sentiment.values())
    links = effective_aspect_links()
    concern_q = q.join(links, links.c.feedback_id == Feedback.id).join(Aspect, Aspect.id == links.c.aspect_id).filter(has_substantive_comment(), FeedbackLabel.sentiment.in_(["negative", "constructive"]))
    aspect_analysis = [dict(aspect=name,positive=int(pos or 0),negative=int(neg or 0),constructive=int(con or 0),neutral=int(neu or 0))
        for name,pos,neg,con,neu in q.join(links,links.c.feedback_id==Feedback.id).join(Aspect,Aspect.id==links.c.aspect_id).filter(has_substantive_comment()).with_entities(Aspect.name,
            *[func.sum(case((condition,1),else_=0)) for condition in (polarity_sql()=="positive",polarity_sql()=="negative",constructive_clause(),polarity_sql()=="neutral")]).group_by(Aspect.id,Aspect.name).order_by(Aspect.name)]
    rules = {r.aspect_id: r.recommendation for r in db.query(InterventionRule).filter_by(is_active=True)}
    concerns = []
    for area_id, area, aspect_id, aspect, n, people in concern_q.with_entities(Department.id, Department.name, Aspect.id, Aspect.name, func.count(func.distinct(Feedback.id)), func.count(func.distinct(Feedback.respondent_id))).group_by(Department.id, Department.name, Aspect.id, Aspect.name).order_by(func.count(func.distinct(Feedback.id)).desc()):
        concerns.append({"service_area": area, "aspect": aspect, "comments": n, "respondents": people,
                         "suggestion": rules.get(aspect_id, "QUAD should review the evidence and draft a suitable action."), "department_id": area_id, "aspect_id": aspect_id})
    # Actions lack a historical college/cycle link. Show them in a separately identified
    # campus-wide register, never misrepresent them as results for the selected semester.
    def action_out(a):
        return {"aspect": "All reported aspects" if a.service_area_scope else a.aspect.name, "service_area": a.department.name if a.department else "All service areas",
                "recommendation": re.sub(r"^\[(Short term|Long term)\]\s*", "", a.note.strip()),
                "goal": "Long term" if a.note.startswith("[Long term]") else "Short term",
                "remarks": a.quad_note, "status": a.status,
                "approved_at": a.confirmed_at, "completed_at": a.completed_at, "action_taken": a.completion_note}
    action_query=db.query(Alert).filter(Alert.note.isnot(None))
    if body.department_id: action_query=action_query.filter(Alert.department_id.in_([body.department_id]) | Alert.department_id.is_(None))
    actions=[action_out(a) for a in action_query.order_by(Alert.updated_at.desc()) if a.note.strip()]

    completed = db.query(Alert).filter(Alert.status == "resolved", Alert.completed_at.isnot(None), Alert.note.isnot(None))
    if body.department_id: completed=completed.filter(Alert.department_id.in_([body.department_id]) | Alert.department_id.is_(None))
    completed_interventions=[action_out(a) for a in completed.order_by(Alert.completed_at.desc()) if a.note.strip()]
    stages = {"new": "awaiting", "acknowledged": "awaiting", "in-progress": "approved", "resolved": "completed"}
    if body.intervention_status != "all":
        actions = [a for a in actions if stages.get(a["status"]) == body.intervention_status]
    intervention_summary = {stage: sum(stages.get(a["status"]) == stage for a in actions) for stage in ("awaiting", "approved", "completed")}
    label = f"{cycle.academic_year} · {cycle.semester} semester" if cycle else "2026-2027 · 1st semester (earlier evaluations)" if body.cycle_id == 0 else "All periods"
    record(db, user.username, "report_preview", "aggregate_report", body.model_dump_json())
    db.commit()
    return {**analytics,"generated_at": datetime.now(timezone.utc), "prepared_by": user.display_name, "period": label,
            "schedule": {"start_date": cycle.start_date, "end_date": cycle.end_date} if cycle else None,
            "filters": body.model_dump(), "respondents": respondents, "completed_submissions": submissions,
            "evaluations": total, "comments": comments, "written_comments":written_entries, "no_substantive_comments":no_comment_entries,
            "unclassified_comments":unclassified, "unclassified_entries":unclassified, "sentiment": {**sentiment,"unclassified":unclassified}, "by_college": by_college,
            "ratings": ratings, "aspect_analysis": aspect_analysis, "concerns": concerns, "actions": actions,
            "intervention_summary": intervention_summary,
            "completed_interventions": completed_interventions,
            "methodology": "Student self-reported evaluations; ratings use a five-point scale. Means use answered rating questions. Respondents are distinct students in the selection; completed submissions count the new atomic survey receipts. Earlier evaluations are included in their assigned semester; completed receipts are counted only where issued. Concern counts include Negative and Constructive comments with assigned aspects; a comment can contribute to multiple aspects. These are review indicators, not verified causes. Enrollment response rates are omitted because historical cycle headcounts are not available.",
            "action_scope": "These recorded actions cover the campus across all semesters. They are not assigned to a college or semester. The service-area selection applies where recorded."}

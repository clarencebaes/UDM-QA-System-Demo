"""Consistent optional period scope for existing evaluation read endpoints."""
from datetime import date, datetime, time, timedelta
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session, with_loader_criteria
from app.models import Feedback, SurveySubmission, Respondent

SCOPED_PATHS = {"/api/qa/dashboard", "/api/qa/feedback", "/api/qa/feedback-page", "/api/qa/feedback-options", "/api/qa/most-commented"}

def feedback_college():
    return func.coalesce(SurveySubmission.college, Respondent.college)

def set_scope(db, request):
    if request.method != "GET" or request.url.path not in SCOPED_PATHS:
        return
    try:
        cycle = request.query_params.get("cycle_id")
        if cycle not in (None, ""):
            cycle = int(cycle)
            if cycle < 0: raise ValueError()
            db.info["read_cycle"] = cycle
        for key in ("answered_from", "answered_through"):
            value = request.query_params.get(key)
            if value:
                day = date.fromisoformat(value)
                if key == "answered_through": day += timedelta(days=1)
                db.info[key] = datetime.combine(day, time.min) - timedelta(hours=8)
        if db.info.get("answered_from") and db.info.get("answered_through") and db.info["answered_from"] >= db.info["answered_through"]:
            raise ValueError()
    except ValueError:
        raise HTTPException(422, "Invalid semester or submission date range.")

@event.listens_for(Session, "do_orm_execute")
def scope_reads(state):
    if not state.is_select: return
    info = state.session.info
    conditions = []
    if "read_cycle" in info:
        cycle = info["read_cycle"]
        conditions.append(Feedback.submission_id.is_(None) if cycle == 0 else
            (Feedback.cycle_id == cycle) | Feedback.submission_id.in_(select(SurveySubmission.id).where(SurveySubmission.cycle_id == cycle)))
    if "answered_from" in info: conditions.append(Feedback.created_at >= info["answered_from"])
    if "answered_through" in info: conditions.append(Feedback.created_at < info["answered_through"])
    for condition in conditions:
        state.statement = state.statement.options(with_loader_criteria(Feedback, condition, include_aliases=True))

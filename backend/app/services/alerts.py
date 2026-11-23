from app.services.text_dimensions import polarity_sql, constructive_clause
"""One active recommendation per service area, from distinct recent comments."""
from datetime import datetime, timedelta
from sqlalchemy import func, or_, case
from app.models import Alert, Feedback, FeedbackLabel, SurveySettings, Threshold
from app.services.feedback_text import has_substantive_comment


def service_area_evidence(db, now=None):
    now = now or datetime.utcnow()
    config = db.query(SurveySettings).first()
    thresholds = db.query(Threshold).order_by(Threshold.id).all()
    threshold = thresholds[0] if thresholds else None
    minimum = config.min_trigger_count if config else threshold.min_count if threshold else 3
    negative_min = (config.min_negative_count if config else None) or minimum
    constructive_min = (config.min_constructive_count if config else None) or minimum
    days = config.alert_window_days if config else threshold.window_days if threshold else 14
    enabled = not thresholds or any(t.include_constructive for t in thresholds)
    since = now - timedelta(days=days)
    rows = (db.query(Feedback.department_id,func.count(Feedback.id),
            func.sum(case((polarity_sql()=="negative",1),else_=0)),
            func.sum(case((constructive_clause(),1),else_=0)))
            .join(FeedbackLabel, FeedbackLabel.feedback_id == Feedback.id)
            .filter(has_substantive_comment(), Feedback.created_at >= since, Feedback.created_at <= now,
                    or_(polarity_sql()=="negative",constructive_clause()))
            .group_by(Feedback.department_id).all())
    groups = {area:dict(negative=int(negative),constructive=int(constructive),total=int(total)) for area,total,negative,constructive in rows}
    for item in groups.values():
        item.update(min_negative_count=negative_min, min_constructive_count=constructive_min,
                    window_days=days, include_constructive=enabled)
        item["eligible"] = item["negative"] >= negative_min or (enabled and item["constructive"] >= constructive_min)
        item["level"] = "high" if item["negative"] >= negative_min*2 or (enabled and item["constructive"] >= constructive_min*2) else "medium"
    return groups, since


def sync_service_area_alerts(db, now=None):
    # The settings row serializes concurrent survey submissions/settings refreshes.
    db.query(SurveySettings).with_for_update().first()
    groups, since = service_area_evidence(db, now)
    changed = False
    for area, counts in groups.items():
        active = (db.query(Alert).filter(Alert.department_id == area, Alert.status.in_(["new", "acknowledged", "in-progress"]))
                  .order_by(Alert.created_at.desc(), Alert.id.desc()).first())
        if active:
            active.negative_count, active.constructive_count = counts["negative"], counts["constructive"]
            changed = True
            continue
        if not counts["eligible"]:
            continue
        latest_completed = db.query(func.max(Alert.completed_at)).filter(or_(Alert.department_id == area, Alert.department_id.is_(None)), Alert.status == "resolved").scalar()
        q = (db.query(FeedbackLabel).join(Feedback, Feedback.id == FeedbackLabel.feedback_id)
             .filter(Feedback.department_id == area, Feedback.created_at >= since, has_substantive_comment(),
                     or_(polarity_sql()=="negative",constructive_clause()) if counts["include_constructive"] else polarity_sql()=="negative"))
        latest = q.order_by(Feedback.created_at.desc(), Feedback.id.desc()).first()
        latest_time = q.with_entities(func.max(Feedback.created_at)).scalar()
        if not latest or not latest.aspect_id or (latest_completed and latest_time <= latest_completed):
            continue
        db.add(Alert(aspect_id=latest.aspect_id, department_id=area, service_area_scope=True, negative_count=counts["negative"],
                     constructive_count=counts["constructive"], recommendation="", status="new"))
        changed = True
    if changed:
        db.commit()
    return groups, since


def evaluate_thresholds(db, aspect_id):
    sync_service_area_alerts(db)
    q = db.query(Alert).filter(Alert.status.in_(["new", "acknowledged", "in-progress"]), Alert.department_id.isnot(None))
    if aspect_id is not None:
        q = q.filter(Alert.aspect_id == aspect_id)
    return q.order_by(Alert.created_at.desc(), Alert.id.desc()).first()

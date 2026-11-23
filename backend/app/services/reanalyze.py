"""Idempotent versioned analysis refresh. Raw answers and approved actions stay intact."""
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
import json
from app.models import Feedback, FeedbackLabel, FeedbackAspectRun, Aspect
from app.audit import record
from ml.polarity_v4 import VERSION, analyze

def refresh_analysis(db):
    from app.services.classify import questions_for_feedback
    from ml.feedback_semantics import GENERAL_ASPECT_CODE
    general=db.query(Aspect).filter_by(code=GENERAL_ASPECT_CODE).first()
    count=0
    last_id=0
    while True:
        rows=db.query(Feedback).options(joinedload(Feedback.department),joinedload(Feedback.label),selectinload(Feedback.aspect_run).selectinload(FeedbackAspectRun.tags)).filter(Feedback.id>last_id,or_(Feedback.analysis_version.is_(None),Feedback.analysis_version!=VERSION)).order_by(Feedback.id).limit(100).all()
        if not rows: break
        for row in rows:
            decision=analyze(row.comment,questions_for_feedback(row))
            row.detected_language=decision["language"]
            row.analysis_version=VERSION
            label=row.label
            if decision["label"] is None:
                if label: db.delete(label)
            else:
                if label is None:
                    tagged=row.aspect_run.tags if row.aspect_run else []
                    aspect_id=row.aspect_id or (tagged[0].aspect_id if tagged else general.id if general else None)
                    if aspect_id is None: raise ValueError("Seed the aspect catalog before refreshing analysis")
                    label=FeedbackLabel(feedback_id=row.id,aspect_id=aspect_id,aspect_source="student" if row.aspect_id else "model",aspect_confidence=1.0 if row.aspect_id else 0.0)
                    db.add(label)
                label.sentiment=decision["label"];label.polarity=decision["polarity"]
                label.is_constructive=decision["is_constructive"];label.analysis_reason=decision["reason"]
                label.sentiment_confidence=decision["model_probability"]
            count+=1
        last_id=rows[-1].id
        record(db,"system analysis","analysis_refreshed","feedback",json.dumps({"analysis_version":VERSION,"evaluations":len(rows)}))
        db.commit()
    return count

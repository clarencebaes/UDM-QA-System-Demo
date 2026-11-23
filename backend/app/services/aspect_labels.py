"""Versioned topic assignments, independent of the three sentiment labels."""
from sqlalchemy import exists, select, union_all
from app.models import Feedback, FeedbackLabel, FeedbackAspectRun, FeedbackAspectTag


def effective_aspect_links():
    # An explicit N/A run has no tags and suppresses the legacy forced topic.
    current = select(FeedbackAspectTag.feedback_id.label("feedback_id"), FeedbackAspectTag.aspect_id.label("aspect_id"))
    legacy = select(FeedbackLabel.feedback_id, FeedbackLabel.aspect_id).where(
        ~exists().where(FeedbackAspectRun.feedback_id == FeedbackLabel.feedback_id))
    return union_all(current, legacy).subquery("effective_aspect_links")


def aspect_matches(aspect_id):
    links = effective_aspect_links()
    return exists(select(1).select_from(links).where(links.c.feedback_id == Feedback.id, links.c.aspect_id == aspect_id))


def aspect_ids(db, feedback_id):
    links = effective_aspect_links()
    return [a for a, in db.query(links.c.aspect_id).filter(links.c.feedback_id == feedback_id).all()]


def display_aspects(item):
    if item.aspect_run is not None:
        return [tag.aspect.name for tag in sorted(item.aspect_run.tags, key=lambda t: t.aspect_id) if tag.aspect]
    return [item.label.aspect.name] if item.label and item.label.aspect else []

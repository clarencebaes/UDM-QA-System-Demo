"""Separate polarity, feedback type and language counts under the caller's scope."""
from sqlalchemy import case, func, or_
from app.models import Feedback, FeedbackLabel
from app.services.feedback_text import has_substantive_comment

COMMENT_CATEGORIES = ("positive", "negative", "constructive", "neutral", "unclassified")

def category_sql():
    """One display category per comment; polarity/type remain separate ML fields."""
    return case((FeedbackLabel.sentiment.in_(COMMENT_CATEGORIES[:-1]), FeedbackLabel.sentiment), else_="unclassified")

def polarity_sql():
    # An old Constructive label does not establish Neutral polarity.
    return func.coalesce(FeedbackLabel.polarity,case((FeedbackLabel.sentiment.in_(["positive","negative","neutral"]),FeedbackLabel.sentiment),else_=None))

def constructive_clause():
    return or_(FeedbackLabel.is_constructive.is_(True),FeedbackLabel.sentiment=="constructive")

def language_sql():
    return case((Feedback.detected_language.in_(["english", "tagalog", "taglish"]),
                 Feedback.detected_language), else_="undetermined")

def text_dimensions(q):
    polarity=polarity_sql()
    source=q.filter(has_substantive_comment())
    language=language_sql()
    polarities={key:0 for key in ("positive","negative","neutral")}
    languages={key:0 for key in ("english","tagalog","taglish","undetermined")}
    conditions=[polarity==key for key in polarities]+[language==key for key in languages]+[constructive_clause()]
    values=list(map(int,source.with_entities(*[func.coalesce(func.sum(case((condition,1),else_=0)),0) for condition in conditions]).one()))
    polarities.update(zip(polarities,values[:3]));languages.update(zip(languages,values[3:7]));constructive=values[7]
    return dict(polarity_counts=polarities,language_counts=languages,feedback_types={"constructive":constructive})

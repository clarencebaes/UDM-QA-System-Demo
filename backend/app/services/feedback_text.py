"""Shared SQL definition of written feedback (not a rating-only response)."""
import re
import string
from sqlalchemy import and_, func, not_, or_
from app.models import Feedback


def comment_text():
    value = Feedback.comment
    for whitespace in ("\t", "\r", "\n"):
        value = func.replace(value, whitespace, " ")
    return func.trim(value)


def has_comment():
    return func.length(comment_text()) > 0

# Exact whole-answer placeholders only. "No hot water" and "None of the
# computers work" remain real feedback. Short answers such as OK stay ambiguous.
_PLACEHOLDER = r"^\s*(?:n\s*[/.-]?\s*a\.?|none|no\s+comments?|not\s+applicable|nothing(?:\s+to\s+add)?)\s*[.!?]*\s*$"
_PUNCTUATION = "^[" + re.escape(string.punctuation + "–—…“”‘’") + r"\s]+$"


def is_no_substantive_feedback(text):
    text = (text or "").strip().lower()
    return bool(text and (re.fullmatch(_PLACEHOLDER, text) or re.fullmatch(_PUNCTUATION, text)))


def no_substantive_feedback():
    text = func.lower(comment_text())
    return and_(has_comment(), or_(text.regexp_match(_PLACEHOLDER), text.regexp_match(_PUNCTUATION)))


def has_substantive_comment():
    return and_(has_comment(), not_(no_substantive_feedback()))

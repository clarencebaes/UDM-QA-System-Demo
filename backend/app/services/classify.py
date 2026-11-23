from __future__ import annotations

import re

import joblib
from sqlalchemy.orm import Session

from app.models import Aspect, Feedback, FeedbackLabel
from ml.train import MODEL_DIR, train_and_save
from ml.features import count_suggestion_cues
from app.services.aspect_model import load_aspect_model, assign_aspects
from app.services.sentiment_model import load_sentiment_model, predict_sentiment
from ml.polarity_v4 import ARTIFACT, load as load_polarity

_sentiment_model = None
_aspect_model = None


def models_exist() -> bool:
    return ARTIFACT.exists() and (
        MODEL_DIR / "aspect_nb.joblib"
    ).exists()


def load_models(force_train: bool = False) -> None:
    global _sentiment_model, _aspect_model
    if force_train or not (MODEL_DIR / "aspect_nb.joblib").exists():
        train_and_save()
    if force_train or not ARTIFACT.exists():
        from ml.train_polarity_v4 import train
        train()
    _aspect_model = joblib.load(MODEL_DIR / "aspect_nb.joblib")
    load_aspect_model()
    load_sentiment_model()
    _sentiment_model = load_polarity()["model"]


def _confidence(model, text: str, label: str) -> float:
    if not hasattr(model, "predict_proba"):
        return 0.0
    proba = model.predict_proba([text])[0]
    classes = list(model.classes_)
    if label not in classes:
        return float(max(proba))
    return float(proba[classes.index(label)])


def _has_suggestion(text: str) -> bool:
    return count_suggestion_cues(text) > 0 or bool(re.search(r"\bi hope\b", text, re.IGNORECASE))

def questions_for_feedback(item):
    from app.service_areas import SERVICE_AREAS
    return next((area["questions"] for area in SERVICE_AREAS if item.department and (area["code"]==item.department.code or area["name"].casefold()==item.department.name.casefold())), ())


def classify_feedback(db: Session, item: Feedback) -> FeedbackLabel | None:
    if _sentiment_model is None or _aspect_model is None:
        load_models()

    text = (item.comment or "").strip()
    # Aspect inference is independent of whether a sentiment can be assigned.
    assign_aspects(db, item)
    from ml.polarity_v4 import VERSION
    context=questions_for_feedback(item)
    decision = predict_sentiment(text, _sentiment_model, context)
    item.detected_language=decision["language"]
    item.analysis_version=VERSION

    # Missing, unsupported and uncertain text has no sentiment label. Preserve
    # the original submission and any independently identifiable aspect tags.
    if decision["label"] is None:
        stale = (
            db.query(FeedbackLabel)
            .filter(FeedbackLabel.feedback_id == item.id)
            .first()
        )
        if stale is not None:
            db.delete(stale)
        db.commit()
        return None

    # ── Sentiment ──
    # Use the three-class NB model with semantic rules; short approval such as
    # "OK" is meaningful. Confidence remains the underlying model probability.
    sent = decision["label"]
    sent_conf = decision["model_probability"]
    if item.aspect_id:
        aspect_id = item.aspect_id
        source = "student"
        aspect = db.get(Aspect, aspect_id)
        aspect_code = aspect.code if aspect else str(_aspect_model.predict([text])[0])
        aspect_conf = 1.0
    else:
        aspect_code = str(_aspect_model.predict([text])[0])
        aspect_conf = _confidence(_aspect_model, text, aspect_code)
        aspect = db.query(Aspect).filter(Aspect.code == aspect_code).first()
        if aspect is None:
            raise ValueError(f"Predicted aspect code {aspect_code!r} is not configured; no arbitrary aspect assigned.")
        aspect_id = aspect.id
        source = "model"

    existing = db.query(FeedbackLabel).filter(FeedbackLabel.feedback_id == item.id).first()
    if existing:
        existing.aspect_id = aspect_id
        existing.sentiment = sent
        existing.polarity = decision["polarity"]
        existing.is_constructive = decision["is_constructive"]
        existing.analysis_reason = decision["reason"]
        existing.aspect_confidence = aspect_conf
        existing.sentiment_confidence = sent_conf
        existing.aspect_source = source
        db.commit()
        db.refresh(existing)
        return existing

    label = FeedbackLabel(
        feedback_id=item.id,
        aspect_id=aspect_id,
        sentiment=sent,
        polarity=decision["polarity"],
        is_constructive=decision["is_constructive"],
        analysis_reason=decision["reason"],
        aspect_confidence=aspect_conf,
        sentiment_confidence=sent_conf,
        aspect_source=source,
    )
    db.add(label)
    db.commit()
    db.refresh(label)
    return label

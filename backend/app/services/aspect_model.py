"""Multi-label aspect inference; never edits the original Feedback or legacy label."""
import joblib
from app.models import Aspect, FeedbackAspectRun, FeedbackAspectTag
from ml.train import MODEL_DIR
from ml.aspect_taxonomy import ASPECT_CODES
from ml.feedback_semantics import unsupported_feedback, is_general_feedback, GENERAL_ASPECT_CODE

ARTIFACT = MODEL_DIR / "aspect_v2.joblib"
_bundle = None


def model_status():
    return {"aspect_model_version": runtime_version() if _bundle else "legacy-v1",
            "aspect_count": len(_bundle["aspect_codes"])+1 if _bundle else 5,
            "trained_aspect_count": len(_bundle["aspect_codes"]) if _bundle else 5,
            "aspect_model_experimental": bool(_bundle)}


def runtime_version():
    return _bundle["version"] + "+general-v1"


def load_aspect_model():
    global _bundle
    _bundle = joblib.load(ARTIFACT) if ARTIFACT.exists() else None
    if _bundle is not None:
        if tuple(_bundle["aspect_codes"]) != ASPECT_CODES or len(_bundle.get("thresholds", [])) != len(ASPECT_CODES):
            raise ValueError("Incompatible nine-aspect artifact; keep the previous deployment")


def infer_aspects(text):
    if _bundle is None:
        return None
    text = text or ""
    if unsupported_feedback(text):
        return []
    if is_general_feedback(text):
        return [(GENERAL_ASPECT_CODE, 0.0)]  # routing rule, not fabricated model confidence
    features = _bundle["pipeline"].named_steps["features"].transform([text])
    if features.nnz == 0:
        return []
    scores = _bundle["pipeline"].named_steps["clf"].predict_proba(features)[0]
    thresholds = _bundle.get("thresholds", [_bundle["threshold"]] * len(scores))
    assigned = [(code, float(score)) for code, score, threshold in zip(_bundle["aspect_codes"], scores, thresholds)
                if score >= threshold]
    return assigned or [(GENERAL_ASPECT_CODE, 0.0)]


def assign_aspects(db, item):
    if not (item.comment or "").strip():
        return False
    inferred = infer_aspects(item.comment)
    if inferred is None:
        return False
    definitions = {a.code: a.id for a in db.query(Aspect).all()}
    if any(code not in definitions for code, _ in inferred):
        raise ValueError("Aspect catalog must be configured before inference")
    run = db.get(FeedbackAspectRun, item.id)
    if run is None:
        run = FeedbackAspectRun(feedback_id=item.id, model_version=runtime_version(), status="assigned")
        db.add(run)
    else:
        run.tags.clear()
        db.flush()
    run.model_version = runtime_version()
    run.status = "assigned" if inferred else "not_applicable"
    for code, score in inferred:
        run.tags.append(FeedbackAspectTag(aspect_id=definitions[code], score=score))
    db.commit()
    # Refresh the relationship when the same Feedback object is serialized next.
    db.expire(item, ["aspect_run"])
    return True

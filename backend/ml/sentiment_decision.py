"""Shared inference used by experiments and the live API."""
from ml.feedback_semantics import policy_decision


def decide(model, text):
    decision = policy_decision(text)
    if decision["reason"] in ("unsupported_or_no_evaluation", "ambiguous_general_feedback"):
        return {**decision, "model_probability": 0.0, "model_label": None}
    probabilities = [float(p) for p in model.predict_proba([text])[0]]
    classes = list(map(str, model.classes_))
    learned = classes[max(range(len(probabilities)), key=probabilities.__getitem__)]
    label = decision["label"] or learned
    ordered = sorted(probabilities)
    if decision["label"] is None and (ordered[-1] < 0.55 or ordered[-1]-ordered[-2] < 0.10):
        return {**decision, "label": None, "reason": "uncertain_model_prediction", "model_label": learned,
                "model_probability": ordered[-1], "model_margin": ordered[-1]-ordered[-2]}
    return {**decision, "label": label, "model_label": learned,
            "model_probability": probabilities[classes.index(label)],
            "model_margin": ordered[-1]-ordered[-2]}

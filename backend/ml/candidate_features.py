"""Experimental features only. Never used by the production joblib pipelines."""
import re
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.base import BaseEstimator, TransformerMixin
from ml.features import build_pipeline, normalize_text, _polarity, NEGATION_WORDS


def polarity_v2(text):
    positive = negative = 0
    # Conjunctions terminate negation scope; hindi sira remains positive,
    # while hindi nagagamit AND sira retains both negative observations.
    for clause in re.split(r"[.;!?,]+|\b(?:and|but|pero|at|kaya|though|although)\b", str(text), flags=re.I):
        tokens = normalize_text(clause).split()
        for i, token in enumerate(tokens):
            polarity = 1 if token in {"nagagamit", "magamit", "usable", "working"} else _polarity(token)
            if any(t in NEGATION_WORDS for t in tokens[max(0, i-5):i]):
                polarity = -polarity
            positive += polarity > 0
            negative += polarity < 0
    return positive, negative


class CandidatePolarity(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = []
        for text in X:
            pos, neg = polarity_v2(text)
            norm = normalize_text(text)
            sarcasm = bool(re.search(r"\bbilis\b.*\b(?:magpahintay|paghihintay)\b", norm))
            continuation = bool(re.search(r"\bcontinue (?:providing|ensuring|organizing)\b", norm))
            rows.append([bool(pos), bool(neg), min(pos, 3)/3, min(neg, 3)/3, sarcasm, continuation])
        return csr_matrix(np.asarray(rows, dtype=float) * 1.5)


def candidate_pipeline(choice):
    pipeline = build_pipeline(choice)
    if choice == "svm":
        pipeline.named_steps["clf"].estimator.set_params(random_state=42)
    features = pipeline.named_steps["features"]
    features.transformer_list = [(name, CandidatePolarity() if name == "polarity" else value)
                                 for name, value in features.transformer_list]
    return pipeline

"""New feature/model version; no changes to the v1 joblib feature implementation."""
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from ml.features import normalize_text
import re
from pathlib import Path
import hashlib


def code_fingerprint():
    root = Path(__file__).parent
    return hashlib.sha256(b"".join((root/name).read_bytes().replace(b"\r\n",b"\n")
        for name in ("sentiment_v3.py","feedback_semantics.py","features.py","sentiment_decision.py"))).hexdigest()
from ml.feedback_semantics import sentiment_evidence, improvement_request, general_sentiment


def normalize_sentiment_v3(text):
    normalized = normalize_text(text)
    return re.sub(r"\b(?:female|male|woman|women|man|men|babae|babaeng|lalaki|lalaking|tomboy|lgbt|lgbtq)\b", "person", normalized)


class SemanticFeaturesV3(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = []
        for text in X:
            e = sentiment_evidence(text)
            pos, neg = len(e["positive"]), len(e["negative"])
            rows.append([bool(pos), bool(neg), min(pos,3)/3, min(neg,3)/3,
                         improvement_request(text), general_sentiment(text) == "positive",
                         general_sentiment(text) == "negative"])
        return csr_matrix(np.asarray(rows, dtype=float)*1.5)


def build_candidate(cv):
    features = FeatureUnion([
        ("word",TfidfVectorizer(preprocessor=normalize_sentiment_v3,ngram_range=(1,2),sublinear_tf=True)),
        ("char",TfidfVectorizer(preprocessor=normalize_sentiment_v3,analyzer="char_wb",ngram_range=(2,5),sublinear_tf=True)),
        ("semantics",SemanticFeaturesV3())])
    estimator = Pipeline([("features",features),("clf",LinearSVC(class_weight="balanced",random_state=42))])
    # Feature vocabulary is fitted separately inside each grouped calibration fold.
    return CalibratedClassifierCV(estimator=estimator,cv=cv,ensemble=False)

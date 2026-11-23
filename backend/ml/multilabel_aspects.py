"""Aspect-only text features and balanced binary ComplementNB estimators."""
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.naive_bayes import ComplementNB
from ml.features import build_pipeline


class BalancedComplementAspects(ClassifierMixin, BaseEstimator):
    def __init__(self, alpha=0.3):
        self.alpha = alpha

    def fit(self, X, y):
        y = np.asarray(y)
        self.estimators_ = []
        self.classes_ = np.arange(y.shape[1])
        for i in self.classes_:
            target = y[:, i]
            positive = int(target.sum())
            negative = len(target) - positive
            if not positive or not negative:
                raise ValueError("Each aspect needs positive and negative training examples")
            weights = np.where(target == 1, len(target)/(2*positive), len(target)/(2*negative))
            model = ComplementNB(alpha=self.alpha).fit(X, target, sample_weight=weights)
            self.estimators_.append(model)
        return self

    def predict_proba(self, X):
        return np.column_stack([model.predict_proba(X)[:, 1] for model in self.estimators_])

    def predict(self, X):
        return (self.predict_proba(X) >= 0.5).astype(int)


def balanced_aspect_pipeline():
    pipeline = build_pipeline("cnb")
    # Aspect topics should not be dominated by sentiment/suggestion cue features.
    features = pipeline.named_steps["features"]
    features.transformer_list = [(name, value) for name, value in features.transformer_list if name in ("word", "char")]
    pipeline.set_params(clf=BalancedComplementAspects())
    return pipeline

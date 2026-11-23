"""Text normalization, cue-word features and the model pipeline.

Works for English, Filipino and Taglish input. Raw text goes in, a label
comes out: the saved pipeline does its own normalization, so the backend
can call model.predict_proba([comment]) directly.

Used by ml/train.py:

    from ml.features import build_pipeline
    model = build_pipeline("logreg").fit(texts, labels)

Sentiment and aspect are trained as two separate models so each one has
more data per class than a single 15-class model would.
"""

from __future__ import annotations

import re

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

# ---------------------------------------------------------------------------
# 1. Normalization
# ---------------------------------------------------------------------------

# Common texting shortcuts -> standard word. Negation words are kept on
# purpose (hindi, wala, walang): removing them would flip the meaning.
SHORTCUTS = {
    "d": "hindi", "di": "hindi", "hnd": "hindi", "ndi": "hindi", "hndi": "hindi",
    "wla": "wala", "wlang": "walang", "nmn": "naman", "nman": "naman",
    "lng": "lang", "tlga": "talaga", "tlg": "talaga",
    "tlaga": "talaga", "tlgang": "talagang", "pls": "please", "plz": "please",
    "plss": "please", "u": "you", "ur": "your", "thx": "thanks", "tnx": "thanks",
    "ty": "thank you", "sna": "sana", "dpt": "dapat", "pwd": "pwede",
    "pde": "pwede", "ksi": "kasi", "kc": "kasi", "mbilis": "mabilis",
    "mbagal": "mabagal", "ngyon": "ngayon", "ngaun": "ngayon", "sya": "siya",
    "dto": "dito", "ung": "yung", "yng": "yung", "grbe": "grabe",
    "hrs": "hours", "hr": "hour", "mins": "minutes", "min": "minute",
}

EMOJI_POS = "😊😀😃😄🙂😍🥰👍👏🙏❤💯✨"
EMOJI_NEG = "😡😠😤😞😢😭👎🤬😩😫"

_REPEAT = re.compile(r"([^\W\d_])\1{2,}")  # tagaaaal -> tagal, sooo -> so
_PUNCT = re.compile(r"[^\w\s]")
_SPACES = re.compile(r"\s+")
_WORD = re.compile(r"\w+")


def normalize_text(text: str) -> str:
    """Lowercase, map emojis, squash repeated letters, expand shortcuts.

    Hyphens become spaces so "mag-extend" -> "mag extend" and
    "i-update" -> "i update".
    """
    t = str(text).lower()
    for ch in EMOJI_POS:
        t = t.replace(ch, " emojipos ")
    for ch in EMOJI_NEG:
        t = t.replace(ch, " emojineg ")
    t = t.replace("'", "").replace("’", "")
    t = t.replace("-", " ")
    t = _REPEAT.sub(r"\1", t)
    t = _PUNCT.sub(" ", t)
    t = _WORD.sub(lambda m: SHORTCUTS.get(m.group(0), m.group(0)), t)
    return _SPACES.sub(" ", t).strip()


# ---------------------------------------------------------------------------
# 2. Cue words for "constructive" (complaint + suggestion)
# ---------------------------------------------------------------------------

SUGGESTION_PATTERNS = [
    r"\bsana\b", r"\bdapat\b", r"\bpwede\b", r"\bpwedeng\b",
    r"\bmas (?:okay|ok|mabuti|mainam|maganda|better)\b",
    r"\bkung pwede\b", r"\bsa susunod\b", r"\bnext time\b", r"\bin the future\b",
    r"\bsuggest\w*\b", r"\bsuhestiyon\b", r"\bsuhestyon\b", r"\bmungkahi\b",
    r"\brecommend\w*\b", r"\bplease\b", r"\bshould\b", r"\bhopefully\b",
    r"\bwould (?:help|be better|be nice|be good|be great)\b",
    r"\bbetter if\b", r"\bit d be\b", r"\bmaybe\b", r"\bconsider\w*\b",
    r"\bimprove\w*\b", r"\bpalitan\b", r"\bdagdagan\b", r"\bmagdagdag\b",
    r"\bayusin\b", r"\blinisin\b", r"\bpalawigin\b", r"\bi update\b",
    r"\bmag (?:add|extend|open|install|post|provide)\b", r"\bwish\b",
    r"\bkailangan na\b", r"\bpagbutihin\b", r"\bmaglagay\b",
]
_SUGGESTION_RE = re.compile("|".join(SUGGESTION_PATTERNS))

NEGATION_WORDS = {
    "hindi", "wala", "walang", "ayaw", "not", "no", "never", "nobody",
    "without", "cannot", "cant", "dont", "doesnt", "didnt", "isnt", "wasnt",
}


def count_suggestion_cues(text: str) -> int:
    return len(_SUGGESTION_RE.findall(normalize_text(text)))


def has_suggestion_cue(text: str) -> bool:
    return count_suggestion_cues(text) > 0


class CueFeatures(BaseEstimator, TransformerMixin):
    """Dense feature block: suggestion cues, negation and question mark.

    Columns: has_suggestion_cue, suggestion_cue_count (capped at 3),
    has_negation, negation_count (capped at 3), is_question.
    `weight` scales them so they are not drowned out by thousands of
    TF-IDF columns.
    """

    def __init__(self, weight: float = 1.5):
        self.weight = weight

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = []
        for text in X:
            norm = normalize_text(text)
            n_cue = len(_SUGGESTION_RE.findall(norm))
            n_neg = sum(1 for w in norm.split() if w in NEGATION_WORDS)
            rows.append([
                1.0 if n_cue else 0.0,
                min(n_cue, 3) / 3.0,
                1.0 if n_neg else 0.0,
                min(n_neg, 3) / 3.0,
                1.0 if "?" in str(text) else 0.0,
            ])
        return csr_matrix(np.asarray(rows, dtype=float) * self.weight)


# ---------------------------------------------------------------------------
# 3. Polarity lexicon (positive / negative words, English + Filipino)
# ---------------------------------------------------------------------------
# With only a few hundred training rows, the model cannot learn that
# "unacceptable", "madumi" or "very accessible" carry sentiment unless it
# happens to see them. A small lexicon gives it that knowledge up front.
# Extend these lists with words you see in the real survey comments.
POS_WORDS = {
    "fast", "quick", "quickly", "immediate", "immediately", "efficient", "excellent",
    "great", "good", "nice", "helpful", "friendly", "polite", "patient", "kind",
    "clear", "easy", "convenient", "accessible", "comfortable", "accommodating",
    "approachable", "professional", "respectful", "welcome", "impressive",
    "consistent", "tidy", "clean", "safe", "thanks", "thank", "salamat",
    "mabilis", "mabait", "magalang", "malinis", "maayos", "maganda", "madali",
    "madaling", "komportable", "maliwanag", "maikli", "ligtas", "magaling",
    "tinulungan", "tinuruan", "naintindihan", "emojipos",
}
NEG_WORDS = {
    "slow", "delayed", "unacceptable", "terrible", "poor", "dirty", "broken",
    "damaged", "leaking", "leak", "rude", "dismissive", "unhelpful", "ignored",
    "confusing", "confused", "unclear", "vague", "outdated", "contradictory",
    "incomplete", "late", "limited", "impossible", "inaccessible", "closed",
    "unsafe", "neglected", "missing", "hot", "dark", "hassle", "stress",
    "stressful", "waited", "long", "flicker", "unbearable", "unbearably",
    "matagal", "mabagal", "mahaba", "mahirap", "madumi", "sira", "basag",
    "bastos", "masungit", "magaspang", "magulo", "malabo", "nalito", "nakakalito",
    "mainit", "madilim", "sarado", "tumutulo", "baha", "maamoy", "mabaho",
    "sayang", "grabe", "kulang", "pahirapan", "nakakainis", "nakakatakot",
    "emojineg",
}
# Tagalog roots: "ang bait", "ang linis", "ang tagal" without the ma- prefix.
POS_ROOTS = ("bait", "linis", "ganda", "galing", "bilis", "ayos", "tulong")
NEG_ROOTS = ("dumi", "tagal", "bagal", "gulo", "sira", "init", "baho", "hirap")

_FLIP_ONLY = NEGATION_WORDS  # "hindi (naman) matagal" -> positive
_CLAUSE_BREAK = re.compile(r"[.;!?,]+")
_FLIP_WINDOW = 5


def _polarity(token: str) -> int:
    if token in POS_WORDS:
        return 1
    if token in NEG_WORDS:
        return -1
    if token.endswith(POS_ROOTS) and len(token) > 3:
        return 1
    if token.endswith(NEG_ROOTS) and len(token) > 3:
        return -1
    return 0


def polarity_counts(text: str) -> tuple[int, int]:
    """Count positive and negative words after negation flipping.

    "hindi mabilis" counts as negative; "hindi na ako naghintay ng
    matagal" and "no long queue" count as positive. Negation only reaches
    back within the same clause (split at . , ; ! ?).
    """
    pos = neg = 0
    for clause in _CLAUSE_BREAK.split(str(text)):
        tokens = normalize_text(clause).split()
        for i, tok in enumerate(tokens):
            p = _polarity(tok)
            if p == 0:
                continue
            window = tokens[max(0, i - _FLIP_WINDOW):i]
            if any(w in _FLIP_ONLY for w in window):
                p = -p
            if p > 0:
                pos += 1
            else:
                neg += 1
    return pos, neg


class PolarityFeatures(BaseEstimator, TransformerMixin):
    """Dense feature block: lexicon-based positive/negative evidence.

    Columns: has_pos, has_neg, pos_count (cap 3), neg_count (cap 3).
    """

    def __init__(self, weight: float = 1.5):
        self.weight = weight

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        rows = []
        for text in X:
            pos, neg = polarity_counts(text)
            rows.append([
                1.0 if pos else 0.0,
                1.0 if neg else 0.0,
                min(pos, 3) / 3.0,
                min(neg, 3) / 3.0,
            ])
        return csr_matrix(np.asarray(rows, dtype=float) * self.weight)


# ---------------------------------------------------------------------------
# 4. Model pipeline
# ---------------------------------------------------------------------------

MODEL_CHOICES = ("logreg", "svm", "cnb")


def build_pipeline(model: str = "logreg", cue_weight: float = 1.5) -> Pipeline:
    """TF-IDF (word 1-2 grams + char 2-5 grams) + cue + polarity features + classifier.

    model: "logreg" (good probabilities), "svm" (calibrated LinearSVC) or
           "cnb" (ComplementNB, the closest to your original Naive Bayes plan).
    """
    features = FeatureUnion([
        ("word", TfidfVectorizer(
            preprocessor=normalize_text, ngram_range=(1, 2), sublinear_tf=True)),
        ("char", TfidfVectorizer(
            preprocessor=normalize_text, analyzer="char_wb",
            ngram_range=(2, 5), sublinear_tf=True)),
        ("cues", CueFeatures(weight=cue_weight)),
        ("polarity", PolarityFeatures(weight=cue_weight)),
    ])
    if model == "logreg":
        clf = LogisticRegression(C=10, max_iter=3000, class_weight="balanced")
    elif model == "svm":
        clf = CalibratedClassifierCV(LinearSVC(class_weight="balanced"), cv=3)
    elif model == "cnb":
        clf = ComplementNB(alpha=0.3)
    else:
        raise ValueError(f"unknown model {model!r}; choose from {MODEL_CHOICES}")
    return Pipeline([("features", features), ("clf", clf)])


# ---------------------------------------------------------------------------
# 5. Inference helpers
# ---------------------------------------------------------------------------

def predict_with_review(model: Pipeline, texts: list[str], threshold: float = 0.55) -> list[dict]:
    """Predict with a confidence score.

    Predictions below `threshold` are flagged needs_review=True so a person
    can label them and add them to the training data (cheap active learning).
    """
    probs = model.predict_proba(texts)
    classes = model.classes_
    out = []
    for text, p in zip(texts, probs):
        top = int(np.argmax(p))
        out.append({
            "text": text,
            "label": str(classes[top]),
            "confidence": float(p[top]),
            "needs_review": bool(p[top] < threshold),
        })
    return out


_CLAUSE_SPLIT = re.compile(
    r"[.;!?]+|\bpero\b|\bbut\b|\bhowever\b|\bngunit\b|\bsubalit\b|\bkaso\b",
    flags=re.IGNORECASE,
)


def split_clauses(text: str) -> list[str]:
    """Split a long comment at 'pero / but / however' and sentence ends so each
    part can be classified on its own (comments often mention 2+ aspects)."""
    parts = [p.strip(" ,") for p in _CLAUSE_SPLIT.split(text)]
    return [p for p in parts if len(p.split()) >= 2]


def predict_clauses(sentiment_model: Pipeline, aspect_model: Pipeline,
                    text: str, threshold: float = 0.55) -> list[dict]:
    """Classify each clause of a comment: aspect + sentiment + confidence."""
    clauses = split_clauses(text) or [text]
    sent = predict_with_review(sentiment_model, clauses, threshold)
    asp = predict_with_review(aspect_model, clauses, threshold)
    return [
        {
            "clause": c,
            "aspect": a["label"], "aspect_confidence": a["confidence"],
            "sentiment": s["label"], "sentiment_confidence": s["confidence"],
            "needs_review": a["needs_review"] or s["needs_review"],
        }
        for c, s, a in zip(clauses, sent, asp)
    ]

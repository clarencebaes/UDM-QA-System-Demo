"""Legacy training command: writes/replaces production model files.

For the proposed nine-aspect transition, use ml.aspect_transition instead.
This loader and its five-aspect seed are intentionally unchanged.

Run from the backend folder:

    python -m ml.train

What changed from the Multinomial Naive Bayes version:
  * Features: TF-IDF word 1-2 grams + character 2-5 grams (handles Taglish
    spelling, typos and Tagalog affixes) + constructive cue words
    (sana, dapat, please, should...) + a positive/negative word lexicon
    with negation flipping. See ml/features.py.
  * Model: for each task, the best of LogisticRegression / calibrated SVM /
    ComplementNB by 5-fold cross-validated macro F1. ComplementNB is still
    a Naive Bayes model.
  * No oversampling by duplication. Class balance is handled inside the
    models (class_weight="balanced" / ComplementNB).
  * load_rows() now merges the seed with training_comments.csv, so edits
    to ml/training_seed.py are never ignored and real comments you append
    to the CSV are kept.
  * The saved files keep the SAME names the backend already loads:
    sentiment_nb.joblib and aspect_nb.joblib. They are full pipelines:
    raw comment text in, predict()/predict_proba() out. The names say "nb"
    only for backward compatibility.
"""

from __future__ import annotations

import csv
from pathlib import Path

import joblib
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline

from ml.features import MODEL_CHOICES, build_pipeline
from ml.training_seed import all_examples

ROOT = Path(__file__).resolve().parents[1]
DATA_CSV = ROOT / "data" / "training_comments.csv"
MODEL_DIR = ROOT / "ml" / "models"
EVAL_PATH = ROOT.parent / "docs" / "model-evaluation.txt"


def write_csv(rows: list[tuple[str, str, str, str]]) -> None:
    DATA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with DATA_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["text", "aspect_code", "sentiment", "language"])
        w.writerows(rows)


def load_rows() -> list[tuple[str, str, str, str]]:
    """Seed rows + any extra rows already in training_comments.csv.

    Seed rows come first and win on duplicate text, so correcting a label
    in ml/training_seed.py takes effect on the next training run. Rows you
    appended to the CSV (real survey comments) are kept.
    """
    rows = list(all_examples())
    seen = {r[0].strip().lower() for r in rows}
    if DATA_CSV.exists():
        with DATA_CSV.open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                text = (r.get("text") or "").strip()
                if not text or text.lower() in seen:
                    continue
                if not r.get("sentiment"):
                    continue
                rows.append((text, r.get("aspect_code") or "", r["sentiment"], r.get("language", "")))
                seen.add(text.lower())
    return rows


def pick_and_fit(texts: list[str], labels: list[str], name: str) -> tuple[Pipeline, str]:
    """Report a held-out score and CV scores, pick the best model, refit on all rows."""
    lines = [f"=== {name} ==="]

    # 1. Same style of report as before: stratified 25% held-out split.
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.25, random_state=42, stratify=labels
    )

    # 2. 5-fold CV is steadier than one split on a few hundred rows.
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores: dict[str, float] = {}
    for choice in MODEL_CHOICES:
        pred = cross_val_predict(build_pipeline(choice), texts, labels, cv=cv)
        scores[choice] = f1_score(labels, pred, average="macro", zero_division=0)
    best = max(scores, key=scores.get)
    lines.append("5-fold CV macro F1: " + ", ".join(f"{k}={v:.3f}" for k, v in scores.items()))
    lines.append(f"chosen model: {best}")

    held = build_pipeline(best).fit(X_train, y_train)
    lines.append(f"\nheld-out 25% ({len(X_test)} comments):")
    lines.append(classification_report(y_test, held.predict(X_test), digits=3, zero_division=0))

    saved = build_pipeline(best).fit(texts, labels)  # final model uses every row
    return saved, "\n".join(lines) + "\n"


def train_and_save() -> str:
    rows = load_rows()
    write_csv(rows)
    texts = [r[0] for r in rows]
    sentiments = [r[2] for r in rows]

    # Sentiment learns from every labeled comment (generic ones like
    # "very good" are valid sentiment evidence).
    sent_model, sent_report = pick_and_fit(texts, sentiments, "Sentiment model")

    # Aspect learns only from comments that actually express a facet
    # (aspect_code != ""). Generic comments carry no facet signal.
    facet_rows = [r for r in rows if r[1]]
    aspect_model, aspect_report = pick_and_fit(
        [r[0] for r in facet_rows], [r[1] for r in facet_rows], "Aspect model"
    )

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(sent_model, MODEL_DIR / "sentiment_nb.joblib")
    joblib.dump(aspect_model, MODEL_DIR / "aspect_nb.joblib")

    summary = (
        f"Training rows: {len(rows)} ({len(facet_rows)} with an aspect)\n"
        f"Saved: {MODEL_DIR / 'sentiment_nb.joblib'}\n"
        f"Saved: {MODEL_DIR / 'aspect_nb.joblib'}\n\n"
        f"{sent_report}\n{aspect_report}\n"
        "Note: these scores come from invented seed text and are optimistic. Judge\n"
        "the model on real, separately labeled student comments (python -m ml.evaluate).\n"
    )
    EVAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVAL_PATH.write_text(summary, encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(train_and_save())

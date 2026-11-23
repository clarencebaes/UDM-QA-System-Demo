"""Explicit experimental release requested by the author; never overwrites v1 models.

The annotations are provisional, sparse classes are accepted by explicit waiver,
and evaluation is a diagnostic, not verified independent capstone evidence.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np

from ml.aspect_taxonomy import ASPECT_CODES, taxonomy_document
from ml.aspect_transition import read_review, families, candidate_pipeline, indicator, metrics, checked_output
from ml.review_workflow import digest, key, snapshot
from ml.train import MODEL_DIR
from ml.multilabel_aspects import balanced_aspect_pipeline
from sklearn.metrics import f1_score


def release(review_path, out, acknowledge_provisional=False, allow_sparse=()):
    if not acknowledge_provisional or "communication_clarity" not in allow_sparse:
        raise ValueError("Experimental release requires explicit provisional-label and sparse-class acknowledgment")
    review = read_review(review_path)
    rows = [r for r in review["records"] if r["include_in_training"] and r["aspect_codes"]]
    groups = families(rows)
    unique = {}
    for row, group in zip(rows, groups):
        k = key(row["text"])
        if k in unique and set(unique[k]["aspect_codes"]) != set(row["aspect_codes"]):
            raise ValueError("Conflicting annotations must not be silently resolved")
        unique.setdefault(k, {**row, "family": group})
    rows = list(unique.values())
    # Assign groups before fitting or seeing any predictions. No score-based search.
    assigned = {}
    for group in set(groups):
        content = "\n".join(sorted(key(r["text"]) for r in rows if r["family"] == group))
        bucket = int(hashlib.sha256(content.encode()).hexdigest()[:8], 16) % 10
        assigned[group] = "holdout" if bucket == 0 else "validation" if bucket == 1 else "train"
    for code in ASPECT_CODES:
        containing = sorted({r["family"] for r in rows if code in r["aspect_codes"]})
        if not containing:
            raise ValueError("Cannot release a model without training evidence for " + code)
        if not any(assigned[g] == "train" for g in containing):
            assigned[containing[0]] = "train"  # coverage allocation, before evaluation
    for row in rows:
        row["split"] = assigned[row["family"]]
    training = [r for r in rows if r["split"] == "train"]
    counts = Counter(c for r in training for c in r["aspect_codes"])
    for code in ASPECT_CODES:
        if counts[code] < 3 and code not in allow_sparse:
            raise ValueError("Sparse training category needs explicit waiver: " + code)
    out = checked_output(out)
    hashes = snapshot(out)
    (out / "frozen-split.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    model = balanced_aspect_pipeline().fit([r["text"] for r in training], indicator(training))
    validation = [r for r in rows if r["split"] == "validation"]
    thresholds = np.full(len(ASPECT_CODES), 0.5)
    if validation:
        probabilities = model.predict_proba([r["text"] for r in validation])
        truth = indicator(validation)
        for i in range(len(ASPECT_CODES)):
            if 0 < truth[:, i].sum() < len(validation):
                thresholds[i] = max(np.arange(0.3, 0.81, 0.05), key=lambda t: (f1_score(truth[:, i], probabilities[:, i] >= t, zero_division=0), t))
    baseline = joblib.load(out / "baseline" / "aspect_nb.joblib")
    report = {"status": "experimental-author-authorized", "independently_verified_ground_truth": False,
              "limitation": "Assistant-proposed annotations, unverified baseline respondent independence, and sparse categories. Not capstone accuracy evidence.",
              "training_unique_comments": len(training), "training_aspect_counts": dict(counts),
              "sparse_class_waivers": list(allow_sparse), "threshold": 0.5,
              "review_sha256": digest(review_path), "per_aspect_thresholds": dict(zip(ASPECT_CODES, thresholds.tolist())),
              "selection_policy": "Balanced ComplementNB with topic-only features; thresholds selected on validation only. The previously inspected holdout is now exploratory, not untouched independent evidence."}
    for split in ("validation", "holdout"):
        use = [r for r in rows if r["split"] == split]
        if not use:
            report[split] = {"n": 0, "not_evaluable": True}
            continue
        text = [r["text"] for r in use]
        truth_counts = Counter(c for r in use for c in r["aspect_codes"])
        report[split] = {
            "candidate": metrics(use, (model.predict_proba(text) >= thresholds).astype(int)),
            "legacy_diagnostic": metrics(use, indicator([{"aspect_codes": [str(p)]} for p in baseline.predict(text)])),
            "categories_without_positive_evaluation_examples": [c for c in ASPECT_CODES if not truth_counts[c]],
            "comparison_limit": "Legacy predicts one of five topics; the candidate predicts zero or several of nine."}
    version = "quad-aspects-v2-balanced-" + hashlib.sha256((report["review_sha256"] + json.dumps(thresholds.tolist()) + "balanced-text-v1").encode()).hexdigest()[:12]
    unsupported = [hashlib.sha256(key(r["text"]).encode()).hexdigest()
                   for r in review["records"] if not r["aspect_codes"]]
    artifact = {"version": version, "taxonomy": taxonomy_document(), "aspect_codes": ASPECT_CODES,
                "pipeline": model, "threshold": 0.5, "thresholds": thresholds.tolist(), "unsupported_text_hashes": sorted(set(unsupported)),
                "status": report["status"], "review_sha256": report["review_sha256"]}
    joblib.dump(artifact, out / "aspect_v2.joblib")
    (out / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert hashes == {name: digest(MODEL_DIR / name) for name in hashes}
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--review", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--acknowledge-provisional-labels", action="store_true")
    p.add_argument("--allow-sparse", nargs="*", default=[])
    args = p.parse_args()
    print(release(args.review, args.out, args.acknowledge_provisional_labels, args.allow_sparse))

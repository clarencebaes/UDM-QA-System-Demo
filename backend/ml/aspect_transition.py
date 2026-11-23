"""Offline v2 aspect staging/comparison. No database access or model promotion.

python -m ml.aspect_transition stage --input <raw-export.json> --out experiments/<new-folder>
python -m ml.aspect_transition audit --review experiments/<folder>/review.json
python -m ml.aspect_transition experiment --review <review.json> --out experiments/<new-folder>
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import classification_report, f1_score, hamming_loss, multilabel_confusion_matrix
from sklearn.multiclass import OneVsRestClassifier

from ml.aspect_taxonomy import ASPECT_CODES, TAXONOMY_VERSION, taxonomy_document
from app.services.feedback_text import is_no_substantive_feedback
from ml.features import build_pipeline
from ml.review_workflow import digest, key, similar, snapshot
from ml.train import MODEL_DIR, ROOT, load_rows

EXPERIMENT_ROOT = ROOT / "experiments"


def text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checked_output(path):
    path = Path(path).resolve()
    if not path.is_relative_to(EXPERIMENT_ROOT.resolve()) or path == EXPERIMENT_ROOT.resolve():
        raise ValueError("Outputs must be a new directory under backend/experiments")
    if path.exists():
        raise ValueError("Output already exists; never overwrite an experiment")
    return path


def source_records(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    records = data.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Expected a nonempty records list from the read-only survey export")
    seen = set()
    for row in records:
        if not isinstance(row.get("text"), str) or str(row.get("id")) in seen or row.get("id") is None:
            raise ValueError("Source needs unique record IDs and original text strings")
        seen.add(str(row["id"]))
    return records


def stage(source, out):
    source = Path(source).resolve()
    rows = source_records(source)
    out = checked_output(out)
    source_digest = digest(source)
    snapshot(out)
    review = {"taxonomy_version": TAXONOMY_VERSION, "source_path": str(source),
              "source_sha256": source_digest, "threshold": 0.5,
              "status": "provisional", "records": []}
    # Only allowlisted fields are copied. No student numbers/emails are exported.
    for row in rows:
        review["records"].append({
            "id": str(row["id"]), "text": row["text"], "text_sha256": text_hash(row["text"]),
            "respondent": row.get("respondent", ""), "source": row.get("source", ""),
            "service_area": row.get("service_area", ""), "college": row.get("college", ""),
            "legacy_prediction": row.get("current_aspect_code", ""),
            "aspect_codes": [], "evidence": [], "no_aspect_reason": "",
            "annotation_note": "", "annotator": "", "approved": "no",
            "include_in_training": False, "split": "", "genuine_independent": "no",
            "baseline_group_unseen": "unknown"})
    (out / "taxonomy.json").write_text(json.dumps(taxonomy_document(), indent=2), encoding="utf-8")
    (out / "review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    assert digest(source) == source_digest
    return out / "review.json"


def read_review(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("taxonomy_version") != TAXONOMY_VERSION:
        raise ValueError("Unknown taxonomy version")
    source = Path(data["source_path"])
    if digest(source) != data["source_sha256"]:
        raise ValueError("Original export changed; stop and investigate")
    originals = {str(r["id"]): r for r in source_records(source)}
    rows = data["records"]
    if len(rows) != len(originals) or {r["id"] for r in rows} != set(originals):
        raise ValueError("Review must retain every original record exactly once")
    for row in rows:
        original = originals[row["id"]]
        if row["text"] != original["text"] or row["text_sha256"] != text_hash(original["text"]):
            raise ValueError("Original comment text changed: " + row["id"])
        for field in ("source", "respondent", "service_area", "college"):
            if row.get(field, "") != original.get(field, ""):
                raise ValueError("Source identity changed: " + row["id"])
        labels = row["aspect_codes"]
        if not isinstance(labels, list) or len(labels) != len(set(labels)) or set(labels) - set(ASPECT_CODES):
            raise ValueError("Unknown or repeated aspect: " + row["id"])
        if not isinstance(row.get("include_in_training"), bool):
            raise ValueError("include_in_training must be a JSON boolean")
        for span in row.get("evidence", []):
            start, end = span.get("start"), span.get("end")
            if (span.get("aspect_code") not in labels or type(start) is not int or type(end) is not int
                    or not 0 <= start < end <= len(row["text"])
                    or row["text"][start:end] != span.get("quote")):
                raise ValueError("Evidence must point to unchanged source text: " + row["id"])
    return data


def families(rows):
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    keys = [key(r["text"]) for r in rows]
    for i, row in enumerate(rows):
        for j, other in enumerate(rows[:i]):
            same_person = row.get("respondent") and row["respondent"] == other.get("respondent")
            same_source = row.get("source") and row["source"] == other.get("source")
            if same_person or same_source or similar(keys[i], keys[j]):
                parent[find(i)] = find(j)
    return [find(i) for i in range(len(rows))]


def audit(review_path):
    data = read_review(review_path)
    rows = data["records"]
    selected = [r for r in rows if r["include_in_training"]]
    unique = {}
    conflicts = []
    for row in selected:
        k = key(row["text"])
        if k in unique and set(unique[k]["aspect_codes"]) != set(row["aspect_codes"]):
            conflicts.append([unique[k]["id"], row["id"]])
        unique.setdefault(k, row)
    counts = Counter(code for row in unique.values() for code in row["aspect_codes"])
    grouped = families(selected)
    return {"taxonomy_version": TAXONOMY_VERSION, "raw_records": len(rows),
            "selected_records": len(selected), "unique_selected_texts": len(unique),
            "provisional_selected_records": sum(r.get("approved") != "yes" for r in selected),
            "unassigned_split_records": sum(not r.get("split") for r in selected),
            "duplicate_label_conflicts": conflicts,
            "aspect_unique_counts": {code: counts[code] for code in ASPECT_CODES},
            "minimum_positive_shortfall": {code: max(0, 5 - counts[code]) for code in ASPECT_CODES},
            "coverage_note": "Five positives per aspect is only the 3/1/1 execution lower bound, not evidence of adequate sample size or independent groups.",
            "source_families": len(set(grouped)),
            "multi_aspect_unique_comments": sum(len(r["aspect_codes"]) > 1 for r in unique.values()),
            "no_aspect_unique_comments": sum(not r["aspect_codes"] for r in unique.values()),
            "production_changed": False}


def validated_rows(review_path):
    data = read_review(review_path)
    if data.get("threshold") != 0.5:
        raise ValueError("This preregistered candidate uses a fixed 0.5 threshold; no holdout tuning")
    rows = [r for r in data["records"] if r["include_in_training"]]
    if not rows:
        raise ValueError("No included training/evaluation annotations")
    for row in rows:
        if row.get("approved") != "yes" or not row.get("annotator", "").strip():
            raise ValueError("Included annotations require explicit approval and an identified annotator")
        if len(row["text"].strip()) < 3 or is_no_substantive_feedback(row["text"]):
            raise ValueError("Placeholders and unusably short text must remain excluded")
        if "\ufffd" in row["text"]:
            raise ValueError("Recover encoding-damaged originals before using them")
        if not row.get("source") or not row.get("respondent"):
            raise ValueError("Source and respondent groups are required")
        if row.get("split") not in ("train", "validation", "holdout"):
            raise ValueError("Freeze train/validation/holdout assignment before evaluation")
        if not row["aspect_codes"] and not row.get("no_aspect_reason", "").strip():
            raise ValueError("Explicitly justify a no-aspect annotation; blank is not automatically negative training data")
        supported = {s["aspect_code"] for s in row["evidence"]}
        if set(row["aspect_codes"]) - supported:
            raise ValueError("Each aspect needs an exact supporting source span")
    grouped = families(rows)
    for group in set(grouped):
        if len({r["split"] for r, g in zip(rows, grouped) if g == group}) != 1:
            raise ValueError("Respondent/source/near-duplicate family crosses splits")
    unique = {}
    for row in rows:
        k = key(row["text"])
        if k in unique and set(row["aspect_codes"]) != set(unique[k]["aspect_codes"]):
            raise ValueError("Conflicting duplicate annotations")
        unique.setdefault(k, row)
    rows = list(unique.values())  # repeated submissions never weight the classifier
    legacy_keys = [key(r[0]) for r in load_rows()]
    for row in rows:
        if row["split"] != "train":
            if row.get("genuine_independent") != "yes" or row.get("baseline_group_unseen") != "yes":
                raise ValueError("Evaluation needs verified independent, unseen baseline groups")
            if any(similar(key(row["text"]), k) for k in legacy_keys):
                raise ValueError("Evaluation text overlaps legacy training data")
    for split in ("train", "validation", "holdout"):
        subset = [r for r in rows if r["split"] == split]
        minimum = 3 if split == "train" else 1
        for code in ASPECT_CODES:
            pos = sum(code in r["aspect_codes"] for r in subset)
            if min(pos, len(subset) - pos) < minimum:
                raise ValueError(f"Insufficient positive/negative coverage for {code} in {split}")
    return rows


def indicator(rows):
    return np.asarray([[int(code in r["aspect_codes"]) for code in ASPECT_CODES] for r in rows])


def candidate_pipeline():
    pipeline = build_pipeline("cnb")
    pipeline.set_params(clf=OneVsRestClassifier(pipeline.named_steps["clf"]))
    return pipeline


def metrics(rows, predicted):
    truth = indicator(rows)
    return {"n": len(rows), "labels": ASPECT_CODES,
            "macro_f1": f1_score(truth, predicted, average="macro", zero_division=0),
            "micro_f1": f1_score(truth, predicted, average="micro", zero_division=0),
            "exact_match": float(np.mean(np.all(truth == predicted, axis=1))),
            "hamming_loss": hamming_loss(truth, predicted),
            "per_aspect": classification_report(truth, predicted, target_names=ASPECT_CODES, output_dict=True, zero_division=0),
            "confusion_matrices_tn_fp_fn_tp": multilabel_confusion_matrix(truth, predicted).tolist(),
            "representative_misclassifications": [
                {"id": r["id"], "text": r["text"], "expected": r["aspect_codes"],
                 "predicted": [c for c, value in zip(ASPECT_CODES, p) if value]}
                for r, p, t in zip(rows, predicted, truth) if not np.array_equal(p, t)][:20]}


def experiment(review_path, out):
    frozen = Path(review_path).read_bytes()
    rows = validated_rows(review_path)  # fail before creating files or fitting
    if Path(review_path).read_bytes() != frozen:
        raise ValueError("Annotations changed during validation; retry with a frozen review")
    out = checked_output(out)
    hashes = snapshot(out)
    (out / "frozen-review.json").write_bytes(frozen)
    training = [r for r in rows if r["split"] == "train"]
    candidate = candidate_pipeline().fit([r["text"] for r in training], indicator(training))
    joblib.dump({"taxonomy": taxonomy_document(), "threshold": 0.5, "pipeline": candidate}, out / "candidate_aspects_v2.joblib")
    baseline = joblib.load(out / "baseline" / "aspect_nb.joblib")
    if set(map(str, baseline.classes_)) - set(ASPECT_CODES):
        raise ValueError("Baseline contains unknown classes; do not silently drop them from comparison")
    report = {"policy": "Fixed multi-label ComplementNB; no automatic deployment or sentiment retraining",
              "taxonomy_version": TAXONOMY_VERSION, "review_sha256": hashlib.sha256(frozen).hexdigest(),
              "comparison_limit": "Legacy classifier emits one of five aspects; it cannot emit the four new labels or multiple labels. Scores reflect this capability gap as well as prediction errors."}
    for split in ("validation", "holdout"):
        use = [r for r in rows if r["split"] == split]
        texts = [r["text"] for r in use]
        predicted = (candidate.predict_proba(texts) >= 0.5).astype(int)
        legacy = [{"aspect_codes": [str(p)]} for p in baseline.predict(texts)]
        report[split] = {"candidate": metrics(use, predicted), "legacy_diagnostic": metrics(use, indicator(legacy))}
    (out / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert hashes == {name: digest(MODEL_DIR / name) for name in hashes}
    return out / "comparison.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("stage"); p.add_argument("--input", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("audit"); p.add_argument("--review", type=Path, required=True)
    p = sub.add_parser("experiment"); p.add_argument("--review", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "stage": print(stage(args.input, args.out))
    elif args.action == "audit": print(json.dumps(audit(args.review), indent=2))
    else: print(experiment(args.review, args.out))


if __name__ == "__main__":
    main()

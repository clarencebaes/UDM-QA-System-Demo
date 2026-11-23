"""Offline taxonomy migration tests; fixtures never enter the survey or training corpus."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np

from ml.aspect_taxonomy import ASPECT_CODES, TAXONOMY_VERSION
from ml.aspect_transition import (EXPERIMENT_ROOT, audit, candidate_pipeline, checked_output,
    experiment, families, indicator, metrics, read_review, stage, text_hash, validated_rows)
from ml.training_seed import ASPECTS as LIVE_CODES


class AspectTransitionTests(unittest.TestCase):
    def setUp(self):
        EXPERIMENT_ROOT.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=EXPERIMENT_ROOT)
        self.root = Path(self.temp.name)
        self.source = self.root / "original.json"
        self.original = "  Mabagal ang release; masungit ang staff. 📝\n"
        self.source.write_text(json.dumps({"records": [dict(id=1, text=self.original,
            source="batch-A", respondent="person-A", service_area="Registrar", college="CCS",
            student_number="MUST_NOT_EXPORT", institutional_email="MUST_NOT_EXPORT")]}, ensure_ascii=False), encoding="utf-8")
        self.original_bytes = self.source.read_bytes()
        self.out = self.root / "staged"
        def fake_snapshot(path):
            path.mkdir()
            return {}
        with patch("ml.aspect_transition.snapshot", side_effect=fake_snapshot):
            self.review_path = stage(self.source, self.out)

    def tearDown(self):
        self.temp.cleanup()

    def edit(self, **values):
        data = json.loads(self.review_path.read_text(encoding="utf-8"))
        data["records"][0].update(values)
        self.review_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_versioned_taxonomy_does_not_change_production_five(self):
        self.assertEqual(len(ASPECT_CODES), 9)
        self.assertEqual(tuple(LIVE_CODES), ASPECT_CODES[:5])
        self.assertNotIn("digital_services", LIVE_CODES)

    def test_stage_preserves_all_text_and_defaults_to_provisional(self):
        data = read_review(self.review_path)
        row = data["records"][0]
        self.assertEqual(data["taxonomy_version"], TAXONOMY_VERSION)
        self.assertEqual(row["text"], self.original)
        self.assertEqual(row["text_sha256"], text_hash(self.original))
        self.assertEqual(row["aspect_codes"], [])
        self.assertEqual(row["approved"], "no")
        self.assertFalse(row["include_in_training"])
        self.assertNotIn("MUST_NOT_EXPORT", self.review_path.read_text(encoding="utf-8"))
        self.assertEqual(self.source.read_bytes(), self.original_bytes)

    def test_changed_source_or_review_text_is_rejected(self):
        self.edit(text=self.original.strip())
        with self.assertRaisesRegex(ValueError, "text changed"):
            read_review(self.review_path)
        self.edit(text=self.original)
        self.source.write_bytes(self.original_bytes + b" ")
        with self.assertRaisesRegex(ValueError, "export changed"):
            read_review(self.review_path)

    def test_multi_aspect_labels_require_real_evidence_spans(self):
        span = lambda code, quote: dict(aspect_code=code, quote=quote,
            start=self.original.index(quote), end=self.original.index(quote) + len(quote))
        evidence = [span("processing_time", "Mabagal ang release"), span("staff_responsiveness", "masungit ang staff")]
        self.edit(aspect_codes=["processing_time", "staff_responsiveness"], evidence=evidence,
                  include_in_training=True)
        self.assertEqual(audit(self.review_path)["multi_aspect_unique_comments"], 1)
        evidence[0]["quote"] = "invented summary"
        self.edit(evidence=evidence)
        with self.assertRaisesRegex(ValueError, "Evidence"):
            read_review(self.review_path)

    def test_unapproved_annotations_cannot_train_or_create_output(self):
        self.edit(include_in_training=True)
        out = self.root / "candidate"
        with self.assertRaisesRegex(ValueError, "approval"):
            experiment(self.review_path, out)
        self.assertFalse(out.exists())

    def test_no_aspect_is_explicit_and_independence_is_required(self):
        self.edit(include_in_training=True, approved="yes", annotator="Fixture reviewer", split="holdout")
        with self.assertRaisesRegex(ValueError, "no-aspect"):
            validated_rows(self.review_path)
        self.edit(no_aspect_reason="Fixture has no supported topic")
        with self.assertRaisesRegex(ValueError, "independent"):
            validated_rows(self.review_path)

    def test_groups_link_people_across_sources_and_near_duplicates(self):
        rows = [dict(text="slow queue", source="A", respondent="same-person"),
                dict(text="food prices", source="B", respondent="same-person"),
                dict(text="The laboratory has broken fans and chairs", source="C", respondent="other"),
                dict(text="The laboratory has broken fans and chairs!", source="D", respondent="third")]
        result = families(rows)
        self.assertEqual(result[0], result[1])
        self.assertEqual(result[2], result[3])
        self.assertNotEqual(result[0], result[2])

    def test_output_cannot_overwrite_production_or_existing_experiment(self):
        with self.assertRaisesRegex(ValueError, "experiments"):
            checked_output(Path(__file__).parent / "ml" / "models")
        with self.assertRaisesRegex(ValueError, "already exists"):
            checked_output(self.out)

    def test_legacy_overlap_is_refused_even_after_independence_claim(self):
        self.edit(include_in_training=True, approved="yes", annotator="Fixture reviewer",
                  split="holdout", no_aspect_reason="Fixture topic not assigned",
                  genuine_independent="yes", baseline_group_unseen="yes")
        with patch("ml.aspect_transition.load_rows", return_value=[(self.original, "", "negative", "tl")]):
            with self.assertRaisesRegex(ValueError, "overlaps legacy"):
                validated_rows(self.review_path)

    def test_approved_sparse_data_cannot_train(self):
        self.edit(include_in_training=True, approved="yes", annotator="Fixture reviewer",
                  split="train", no_aspect_reason="Fixture topic not assigned")
        with self.assertRaisesRegex(ValueError, "coverage"):
            validated_rows(self.review_path)

    def test_person_cannot_cross_splits_even_with_different_source_names(self):
        raw = json.loads(self.source.read_text(encoding="utf-8"))
        raw["records"].append({**raw["records"][0], "id": 2, "source": "batch-B", "text": "Another genuine fixture topic"})
        self.source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        with patch("ml.aspect_transition.snapshot", side_effect=lambda p: p.mkdir()):
            path = stage(self.source, self.root / "cross-split")
        data = json.loads(path.read_text(encoding="utf-8"))
        for row, split in zip(data["records"], ("train", "holdout")):
            row.update(include_in_training=True, approved="yes", annotator="Fixture reviewer",
                       split=split, no_aspect_reason="No topic in fixture")
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "crosses splits"):
            validated_rows(path)

    def test_duplicate_conflicts_are_reported_without_relabeling(self):
        # A second genuine source record remains present in the review.
        raw = json.loads(self.source.read_text(encoding="utf-8"))
        raw["records"].append({**raw["records"][0], "id": 2})
        self.source.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        with patch("ml.aspect_transition.snapshot", side_effect=lambda p: p.mkdir()):
            path = stage(self.source, self.root / "duplicates")
        data = json.loads(path.read_text(encoding="utf-8"))
        for row, code in zip(data["records"], ("processing_time", "staff_responsiveness")):
            row.update(aspect_codes=[code], include_in_training=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(audit(path)["duplicate_label_conflicts"], [["1", "2"]])

    def test_multilabel_pipeline_serialization_and_metrics(self):
        # Invented unit-test fixtures, never survey examples or performance evidence.
        rows = [dict(id=str(i), text=f"fixture topic {code} report", aspect_codes=[code])
                for i, code in enumerate(ASPECT_CODES)]
        rows.append(dict(id="multi", text="fixture topic processing_time staff_responsiveness report",
                         aspect_codes=["processing_time", "staff_responsiveness"]))
        model = candidate_pipeline().fit([r["text"] for r in rows], indicator(rows))
        path = self.root / "candidate.joblib"
        joblib.dump(model, path)
        predicted = model.predict_proba([r["text"] for r in rows])
        np.testing.assert_allclose(predicted, joblib.load(path).predict_proba([r["text"] for r in rows]))
        self.assertEqual(predicted.shape, (10, 9))
        perfect = metrics(rows, indicator(rows))
        self.assertEqual(perfect["macro_f1"], 1)
        self.assertEqual(len(perfect["confusion_matrices_tn_fp_fn_tp"]), 9)

    def test_complete_experiment_writes_only_separate_candidate(self):
        from sklearn.dummy import DummyClassifier
        from ml.review_workflow import digest
        from ml.train import MODEL_DIR
        # Artificial runner fixtures verify file handling, not model performance.
        raw = []
        for split, repeats in (("train", 3), ("validation", 1), ("holdout", 1)):
            for index, code in enumerate(ASPECT_CODES):
                for repeat in range(repeats):
                    record_id = str(len(raw) + 1)
                    raw.append(dict(id=record_id, text=f"{split[0]} topic{index} case{repeat}",
                                    source=f"fixture-{record_id}", respondent=f"person-{record_id}"))
        source = self.root / "runner-source.json"
        source.write_text(json.dumps({"records": raw}), encoding="utf-8")
        with patch("ml.aspect_transition.snapshot", side_effect=lambda p: p.mkdir()):
            review_path = stage(source, self.root / "runner-review")
        data = json.loads(review_path.read_text(encoding="utf-8"))
        for row in data["records"]:
            index = int(row["text"].split()[1].removeprefix("topic"))
            code = ASPECT_CODES[index]
            row.update(aspect_codes=[code], approved="yes", annotator="Fixture annotator",
                       include_in_training=True, genuine_independent="yes", baseline_group_unseen="yes",
                       split={"t": "train", "v": "validation", "h": "holdout"}[row["text"][0]],
                       evidence=[dict(aspect_code=code, start=0, end=len(row["text"]), quote=row["text"])])
        review_path.write_text(json.dumps(data), encoding="utf-8")
        hashes = {name: digest(MODEL_DIR / name) for name in ("aspect_nb.joblib", "sentiment_nb.joblib")}
        def fake_snapshot(path):
            (path / "baseline").mkdir(parents=True)
            dummy = DummyClassifier(strategy="constant", constant="processing_time").fit(["fixture"], ["processing_time"])
            joblib.dump(dummy, path / "baseline" / "aspect_nb.joblib")
            return hashes
        with patch("ml.aspect_transition.snapshot", side_effect=fake_snapshot), patch("ml.aspect_transition.load_rows", return_value=[]):
            report_path = experiment(review_path, self.root / "separate-candidate")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["holdout"]["candidate"]["n"], 9)
        self.assertIn("comparison_limit", report)
        self.assertEqual((report_path.parent / "frozen-review.json").read_bytes(), review_path.read_bytes())
        artifact = joblib.load(report_path.parent / "candidate_aspects_v2.joblib")
        self.assertEqual(artifact["taxonomy"]["version"], TAXONOMY_VERSION)
        self.assertEqual(hashes, {name: digest(MODEL_DIR / name) for name in hashes})


if __name__ == "__main__":
    unittest.main()

"""Offline safety/feature regressions. No production writes or retraining."""
import unittest
from unittest.mock import patch
from ml.candidate_features import polarity_v2, CandidatePolarity
from ml.features import polarity_counts
from ml.review_workflow import normalized, groups, validate_experiment, key, similar

class ReviewWorkflowTests(unittest.TestCase):
    def test_negation_scope_is_versioned(self):
        text="ung mga PC hindi nagagamit and sira ung ibang parts kaya hindi nagagamit lalo na kapag kailangan."
        self.assertEqual(polarity_counts(text),(1,0))  # preserve baseline behavior
        self.assertEqual(polarity_v2(text),(0,3))
        self.assertEqual(polarity_v2("hindi sira"),(1,0))
        self.assertEqual(polarity_v2("hindi mabilis"),(0,1))
    def test_sarcasm_and_continuation(self):
        values=CandidatePolarity().transform(["ang bilis magpahintay", "Continue providing efficient service"]).toarray()
        self.assertGreater(values[0,4],0)
        self.assertGreater(values[1,5],0)
    def test_blank_aspect_and_provisional_default(self):
        r=normalized(dict(text="Ang mahal ng pagkain",sentiment="Negative",aspect=""),"source",1)
        self.assertEqual(r["aspect_code"],"")
        self.assertEqual(r["approved"],"no")
        self.assertEqual(r["genuine_independent"],"no")
        with self.assertRaisesRegex(ValueError,"approved"): validate_experiment([r])
    def test_unknown_aspect_and_exclusion(self):
        r=normalized(dict(text="price",sentiment="Unclear / Exclude",aspect="Food Price",include_in_training="No"),"source",1)
        self.assertIn("unknown aspect",r["issues"])
        self.assertIn("explicit exclusion",r["issues"])
    def test_source_and_near_duplicate_families(self):
        rows=[dict(text="The staff are really friendly and helpful",source="A",respondent="1"),
              dict(text="The staff are really friendly and helpful!",source="B",respondent="2"),
              dict(text="broken computers",source="B",respondent="3")]
        self.assertEqual(len(set(groups(rows))),1)
        self.assertTrue(similar(key(rows[0]["text"]),key(rows[1]["text"])))
    def test_cross_split_refused(self):
        rows=[]
        for split in ("train","holdout"):
            r=normalized(dict(text="different text "+split,sentiment="Negative"),"batch",1)
            r.update(approved="yes",split=split)
            rows.append(r)
        with self.assertRaisesRegex(ValueError,"crosses splits"):validate_experiment(rows)
    def test_baseline_overlap_refused(self):
        r=normalized(dict(text="broken computer",sentiment="Negative"),"new batch",1)
        r.update(approved="yes",split="holdout",genuine_independent="yes",baseline_group_unseen="yes")
        with patch("ml.review_workflow.load_rows",return_value=[("broken computer","facility_conditions","negative","en")]):
            with self.assertRaisesRegex(ValueError,"overlaps baseline"):validate_experiment([r])
    def test_candidate_serialization(self):
        import tempfile
        from pathlib import Path
        import joblib
        from ml.candidate_features import candidate_pipeline
        texts = [f"{label} example {i} staff computer queue" for label in ("positive", "negative", "constructive") for i in range(4)]
        labels = [label for label in ("positive", "negative", "constructive") for i in range(4)]
        for choice in ("svm", "cnb"):
            candidate = candidate_pipeline(choice).fit(texts, labels)
            with tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/"candidate.joblib"
                joblib.dump(candidate,path)
                self.assertEqual(list(candidate.predict(texts)),list(joblib.load(path).predict(texts)))

    def test_missing_independence_refused(self):
        r=normalized(dict(text="feedback",sentiment="Negative"),"batch",1)
        r.update(approved="yes",split="holdout")
        with self.assertRaisesRegex(ValueError,"independent"):validate_experiment([r])

if __name__=="__main__": unittest.main()

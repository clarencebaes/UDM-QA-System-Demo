"""Multi-aspect API/count regressions using an isolated database."""
from unittest.mock import patch
import unittest
from app.models import (Aspect, Feedback, FeedbackLabel, Respondent, FeedbackAspectRun,
                        FeedbackAspectTag, Threshold, Alert)
from app.services.dashboard import aggregate_dashboard
from app.services.admin_reads import feedback_page, intervention_view
from app.services.aspect_model import assign_aspects
from app.seed import seed_aspect_catalog
import verify_college_analytics as fixtures


class LiveAspectTests(fixtures.CollegeAnalyticsTests):
    def test_versioned_sentiment_migration_backs_up_and_preserves_raw_records(self):
        import tempfile
        import json
        from pathlib import Path
        from ml.relabel_versioned import migrate, restore, records, fingerprint
        self.seed_multi()
        with self.Session() as db, tempfile.TemporaryDirectory() as folder:
            before=fingerprint(records(db,Feedback))
            labels_before=fingerprint(records(db,FeedbackLabel))
            tags_before=fingerprint(records(db,FeedbackAspectTag))
            old_id=db.query(FeedbackLabel).filter_by(feedback_id=1).one().id
            backup=Path(folder)/'before.json'
            result=migrate(db,backup)
            self.assertTrue(result['raw_unchanged'])
            self.assertEqual(before,fingerprint(records(db,Feedback)))
            self.assertEqual(db.query(FeedbackLabel).filter_by(feedback_id=1).one().id,old_id)
            self.assertIsNone(db.query(FeedbackLabel).filter_by(feedback_id=3).first())
            self.assertEqual(db.query(FeedbackLabel).filter_by(feedback_id=5).one().sentiment,'positive')
            self.assertTrue(json.loads(backup.read_text(encoding='utf-8'))['tables']['feedback_labels'])
            with self.assertRaises(ValueError):migrate(db,backup)
            restore(db,backup)
            self.assertEqual(labels_before,fingerprint(records(db,FeedbackLabel)))
            self.assertEqual(tags_before,fingerprint(records(db,FeedbackAspectTag)))
            self.assertEqual(before,fingerprint(records(db,Feedback)))

    def seed_multi(self):
        with self.Session() as db:
            db.add_all([Aspect(id=3, code="staff_responsiveness", name="Staff Support", description=""),
                        Aspect(id=4, code="affordability_value", name="Affordability", description=""),
                        Aspect(id=5, code="general_service_feedback", name="General Service Feedback", description="")])
            r = Respondent(student_number="00-00-002", institutional_email="fixture@udm.edu.ph", college="CAS")
            db.add(r); db.flush()
            for i, text, sentiment, legacy, tags in [
                (1,"Rude staff and slow release", "negative",1,[1,3]),
                (2,"Please fix the fan", "constructive",2,[2]),
                (3,"N/A", "negative",2,[]),
                (4,"The food costs too much",None,2,[4]),
                (5,"Good", "positive",2,[5])]:
                f=Feedback(id=i,department_id=1,respondent_id=r.id,comment=text,rating=3,consent=True)
                db.add(f);db.flush()
                if sentiment:db.add(FeedbackLabel(feedback_id=i,aspect_id=legacy,sentiment=sentiment,aspect_source="model"))
                run=FeedbackAspectRun(feedback_id=i,model_version="fixture-v2",status="assigned" if tags else "not_applicable")
                run.tags=[FeedbackAspectTag(aspect_id=a,score=.8) for a in tags]
                db.add(run)
            for a in (1,2,3):
                db.add(Threshold(aspect_id=a,min_count=1,window_days=14,include_constructive=True))
                db.add(Alert(aspect_id=a,negative_count=0,constructive_count=0,recommendation="",status="new"))
            db.commit()

    def test_multi_aspect_counts_do_not_duplicate_students_comments_or_flags(self):
        self.seed_multi()
        with self.Session() as db:
            d=aggregate_dashboard(db)
            self.assertEqual((d["unique_respondents"],d["written_comments"],d["total_comments"]),(1,5,4))
            self.assertEqual((d["positive"],d["negative"],d["constructive"]),(1,1,1))
            self.assertEqual(sum(a["negative"] for a in d["by_aspect"]),2)
            self.assertEqual(sum(a["positive"] for a in d["by_aspect"]),1)
            view=intervention_view(db)
            self.assertEqual(view["feedback_total"],2)
            self.assertEqual(view["feedback_group_total"],3)
            self.assertEqual(sum(p["count"] for p in view["pairs"]),3)
            self.assertEqual(intervention_view(db,college="CAS")["feedback_group_total"],3)
            self.assertEqual(feedback_page(db,aspect="Staff Support")["total"],1)
        response=self.client.get("/api/qa/interventions").json()
        self.assertEqual(len(response["feedback"]),2)
        self.assertTrue(all(", " not in row["aspect"] for row in response["feedback"]))

    def test_unclassified_sentiment_can_have_an_aspect_and_unsupported_is_na(self):
        self.seed_multi()
        page=self.client.get("/api/qa/feedback-page?aspect=Affordability&sentiment=unclassified").json()
        self.assertEqual(page["total"],1)
        row=page["items"][0]
        self.assertIsNone(row["sentiment"])
        self.assertEqual(row["aspects"],["Affordability"])
        for record_id in (3,):
            row=self.client.get(f"/api/qa/feedback/{record_id}").json()
            self.assertEqual(row["aspect"],"N/A")
            self.assertEqual(row["aspects"],[])
        self.assertEqual(self.client.get("/api/qa/feedback-page?aspect=N/A").json()["total"],1)
        row=self.client.get("/api/qa/feedback/1").json()
        self.assertEqual(len(row["aspects"]),2)

    def test_reassignment_only_changes_versioned_aspect_tables(self):
        self.seed_multi()
        with self.Session() as db:
            f=db.get(Feedback,1)
            before=(f.comment,f.rating,f.respondent_id,f.label.sentiment,f.label.aspect_id)
            with patch("app.services.aspect_model._bundle",{"version":"new-fixture"}), patch("app.services.aspect_model.infer_aspects",return_value=[("facility_conditions",.9)]):
                assign_aspects(db,f);assign_aspects(db,f)
            self.assertEqual((f.comment,f.rating,f.respondent_id,f.label.sentiment,f.label.aspect_id),before)
            self.assertEqual([t.aspect_id for t in f.aspect_run.tags],[2])
            self.assertEqual(db.query(FeedbackAspectTag).filter_by(feedback_id=1).count(),1)

    def test_catalog_is_additive_and_preserves_existing_rules_and_thresholds(self):
        with self.Session() as db:
            db.add(Threshold(aspect_id=1,min_count=8,window_days=12,include_constructive=False));db.commit()
            seed_aspect_catalog(db);db.commit();seed_aspect_catalog(db);db.commit()
            self.assertEqual(db.query(Aspect).count(),10)
            self.assertEqual(db.query(Threshold).count(),10)
            self.assertEqual(db.get(Aspect,1).code,"processing_time")
            self.assertEqual(db.query(Threshold).filter_by(aspect_id=1).one().min_count,8)

    def test_real_release_model_handles_known_complaints_and_na(self):
        import joblib
        from app.services.aspect_model import ARTIFACT, infer_aspects
        with patch("app.services.aspect_model._bundle", joblib.load(ARTIFACT)):
            for text in ("N/A", "none", "tt", "Thank you", "漢字漢字漢字"):
                self.assertEqual(infer_aspects(text),[])
            for text in ("Good", "Great", "Okay", "OK", "Very poor", "Excellent service", "sakto lang mej lang"):
                self.assertEqual([c for c,_ in infer_aspects(text)],["general_service_feedback"])
            pc="ung mga PC hindi nagagamit and sira ung ibang parts kaya hindi nagagamit lalo na kapag kailangan."
            self.assertEqual([c for c,_ in infer_aspects(pc)],["facility_conditions"])
            multi="hindi sila accommodating minsan kasi nasisigawan nila ang mga students kapag may kailangan, and mabagal din mag process ng mga document request"
            self.assertEqual({c for c,_ in infer_aspects(multi)}, {"processing_time","staff_responsiveness"})
            self.assertEqual([c for c,_ in infer_aspects("Ang mahal ng pagkain.")],["affordability_value"])


if __name__ == "__main__":unittest.main()

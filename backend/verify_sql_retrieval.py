"""Aggregation parity, pagination beyond 500 records and unchanged alert semantics."""
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import unittest
import json
import subprocess
from sqlalchemy import event
from app.main import dashboard
from app.models import Alert, Aspect, Department, Feedback, FeedbackLabel, Respondent, Threshold, User
from app.services.dashboard import aggregate_dashboard
from app.services.admin_reads import intervention_view
import verify_college_analytics as fixtures


class SqlRetrievalTests(fixtures.CollegeAnalyticsTests):
    def seed_history(self):
        with self.Session() as db:
            people = [Respondent(student_number=f"00-00-{i:03d}", institutional_email=f"sql-test-{i}@udm.edu.ph",college="CAS" if i%2 else "CCS") for i in range(1,9)]
            db.add_all(people)
            db.flush()
            now = datetime.utcnow().replace(microsecond=0)
            for i in range(640):
                f = Feedback(department_id=1 if i%2 else 2,respondent_id=people[i%8].id,
                    comment="Synthetic comment " + str(i) if i%5 else "",rating=1+i%5,
                    created_at=now-timedelta(days=i%20), consent=True)
                db.add(f);db.flush()
                if i%5:
                    db.add(FeedbackLabel(feedback_id=f.id,aspect_id=1 if i%2 else 2,
                        sentiment=("positive","negative","constructive")[i%3],aspect_source="model"))
            db.commit()

    def test_sql_matches_previous_dashboard_counts(self):
        self.seed_history()
        # Local ignored snapshot created from the pre-change commit. It is an
        # optional reference; the assertions below also cover the public contract.
        snapshot = Path("experiments/sql-retrieval/baseline_main.py")
        if snapshot.exists():
            spec=importlib.util.spec_from_file_location("baseline_dashboard",snapshot)
            old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        else:
            old=None
        for college in (None,"CAS","CCS","CHS"):
            for start in (None,datetime.utcnow()-timedelta(days=7)):
                with self.Session() as db:
                    actual=dashboard(user=User(username="test"),db=db,start_date=start,college=college)
                    if old:
                        expected=old.dashboard(user=User(username="test"),db=db,start_date=start,college=college)
                        self.assertEqual(actual.total_feedback,expected.total_feedback)
                        for key in ("unique_respondents","positive","negative","constructive","unlabeled","overall_enrolled","overall_response_rate","by_day","by_college","by_aspect","by_department"):
                            a,b=getattr(actual,key),getattr(expected,key)
                            if key=="by_department":
                                a=[{k:v for k,v in r.items() if k!="comments"} for r in a]
                            if isinstance(a,list):
                                def old_fields(row):
                                    if hasattr(row,"model_dump"): row=row.model_dump()
                                    return {k:v for k,v in row.items() if k not in {"neutral","neutral_pct"}} if isinstance(row,dict) else row
                                a=[old_fields(r) for r in a];b=[old_fields(r) for r in b]
                                a=sorted(a,key=str);b=sorted(b,key=str)
                            self.assertEqual(a,b,key)
                    if college is None and start is None:
                        self.assertEqual(actual.total_feedback,640)
                        self.assertEqual(actual.unlabeled,128)
                        self.assertEqual(actual.unique_respondents,8)
                        self.assertEqual(sum(r.comments for r in actual.by_college),512)
                    # Splitting card resources must retain the same numbers.
                    summary=aggregate_dashboard(db,start_date=start,college=college,section="summary")
                    charts=aggregate_dashboard(db,start_date=start,college=college,section="charts")
                    self.assertEqual(summary["total_feedback"],actual.total_feedback)
                    self.assertEqual(charts["by_aspect"],actual.by_aspect)
                    self.assertEqual(summary["by_college"],[r.model_dump() for r in actual.by_college])

    def test_page_counts_and_search_cover_history_beyond_500(self):
        self.seed_history()
        first=self.client.get("/api/qa/feedback-page?page=1&page_size=10").json()
        self.assertEqual((first["total"],len(first["items"])),(512,10))
        last=self.client.get("/api/qa/feedback-page?page=52&page_size=10").json()
        self.assertEqual((last["page"],len(last["items"])),(52,2))
        self.assertTrue(set(r["id"] for r in first["items"]).isdisjoint(r["id"] for r in last["items"]))
        filtered=self.client.get("/api/qa/feedback-page?college=CAS&sentiment=negative").json()
        self.assertGreater(filtered["total"],10)
        self.assertTrue(all(r["college"]=="CAS" and r["sentiment"]=="negative" for r in filtered["items"]))
        self.assertEqual(filtered["counts"]["all"],256)
        search=self.client.get("/api/qa/feedback-page?search=00-00-001").json()
        self.assertTrue(all(r["student_number"]=="00-00-001" for r in search["items"]))
        self.assertEqual(self.client.get("/api/qa/feedback-page?search=%25").json()["total"],0)
        self.assertEqual(self.client.get("/api/qa/feedback-page?page=999").json()["page"],52)
        self.assertEqual(self.client.get("/api/qa/feedback-page?page_size=1000").status_code,422)
        most=self.client.get("/api/qa/most-commented").json()
        self.assertEqual(sum(r["count"] for r in most["items"]),512)
        self.assertTrue(all(len(r["comments"])<=2 for r in most["items"]))
        options=self.client.get("/api/qa/feedback-options").json()
        self.assertEqual(options["colleges"],["CAS","CCS"])

    def test_summary_does_not_hydrate_feedback_history(self):
        self.seed_history()
        loaded=[]
        def on_load(session,instance):
            if isinstance(instance,Feedback):loaded.append(instance.id)
        event.listen(self.Session.class_,"loaded_as_persistent",on_load)
        try:
            with self.Session() as db:
                result=aggregate_dashboard(db)
                self.assertEqual(result["total_feedback"],640)
        finally:
            event.remove(self.Session.class_,"loaded_as_persistent",on_load)
        self.assertEqual(loaded,[])

    def test_intervention_totals_use_full_campus_window_before_college_filter(self):
        self.seed_history()
        with self.Session() as db:
            now=datetime.utcnow()
            db.add_all([Threshold(aspect_id=1,min_count=3,window_days=14,include_constructive=True),
                Threshold(aspect_id=2,min_count=3,window_days=14,include_constructive=False),
                Alert(aspect_id=1,negative_count=0,constructive_count=0,recommendation="",status="new"),
                Alert(aspect_id=2,negative_count=0,constructive_count=0,recommendation="",status="resolved")])
            db.commit()
            view=intervention_view(db,now=now)
            self.assertEqual(len({p["service_area"] for p in view["pairs"]}),len(view["pairs"]))
            self.assertGreater(view["feedback_total"],10)
            self.assertEqual(len(view["feedback"]),2)
            self.assertTrue(all(row.label.sentiment=="negative" for row in view["feedback"]))
            for pair in view["pairs"]:
                self.assertEqual(pair["count"],pair["negative"]+pair["constructive"])
                self.assertTrue(pair["negative"]>=3 or pair["constructive"]>=3)
            self.assertEqual(view["feedback_total"],sum(p["negative"] for p in view["pairs"]))

            selected=intervention_view(db,college="CAS",now=now)
            self.assertEqual(selected["aspects"],view["aspects"])
            self.assertLessEqual(selected["feedback_total"],view["feedback_total"])
            self.assertTrue(all(row.respondent and row.respondent.college=="CAS" for row in selected["feedback"]))
            db.query(Threshold).filter(Threshold.aspect_id==1).update({"min_count":10000});db.commit()
            self.assertEqual(intervention_view(db,now=now)["feedback_total"],0)


if __name__=="__main__":unittest.main()

"""Selected-area evidence, grouped counts, uncertain review and QUAD notes."""
from datetime import datetime,timedelta
import unittest
from app.models import Alert,Aspect,Department,Feedback,FeedbackLabel,Threshold
from app.services.admin_reads import intervention_view,selected_area_detail
import verify_college_analytics as fixtures


class InterventionContextTests(fixtures.CollegeAnalyticsTests):
    def seed_comments(self):
        with self.Session() as db:
            now=datetime.utcnow()
            for department,text,sentiment,days in ((1,"The registrar is slow and late.","negative",0),
                (1,"Please reduce the waiting for documents.","constructive",0),
                (1,"Slow document release.","negative",0),
                (2,"Lab requests take too long.","negative",0),
                (1,"Slow old comment must not appear.","negative",30)):
                f=Feedback(department_id=department,comment=text,consent=True,created_at=now-timedelta(days=days))
                db.add(f);db.flush();db.add(FeedbackLabel(feedback_id=f.id,aspect_id=1,sentiment=sentiment,aspect_source="model"))
            db.add_all([Threshold(aspect_id=1,min_count=2,window_days=14,include_constructive=True),
                Alert(aspect_id=1,department_id=1,negative_count=3,constructive_count=1,recommendation="",status="new")]);db.commit()

    def test_selected_area_changes_evidence_and_counts_without_relabeling(self):
        self.seed_comments()
        with self.Session() as db:
            registrar=selected_area_detail(db,"Registrar","processing_time")
            self.assertEqual((registrar["count"],registrar["negative"],registrar["constructive"]),(3,2,1))
            self.assertEqual(next(item["count"] for item in registrar["mentioned_terms"] if item["term"]=="slow"),2)
            self.assertTrue(all("old comment" not in row["text"] for row in registrar["examples"]))
            lab=selected_area_detail(db,"Laboratory","processing_time")
            self.assertEqual(lab["count"],1)
            self.assertNotEqual(lab["examples"],registrar["examples"])
            overview=intervention_view(db)
            self.assertEqual(overview["feedback_total"],2)
            self.assertEqual(overview["feedback_group_total"],1)
            self.assertEqual(sum(pair["count"] for pair in overview["pairs"]),3)
            self.assertEqual(overview["aspects"][0]["count"],3)
            db.query(Threshold).update({"include_constructive":False});db.commit()
            self.assertEqual(selected_area_detail(db,"Registrar","processing_time")["count"],3)
        result=self.client.get("/api/qa/intervention-detail",params={"department":"Registrar","aspect_code":"processing_time"})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()["service_area"],"Registrar")

    def test_settings_changes_recompute_threshold_visibility_and_preserve_draft(self):
        self.seed_comments()
        with self.Session() as db:
            alert=db.query(Alert).first()
            alert.note="[Short term] Keep the existing draft"
            alert.quad_note="Follow up Friday"
            db.commit()
        path="/api/qa/survey-settings"
        def update(**body):
            response=self.client.patch(path,json=body)
            self.assertEqual(response.status_code,200,response.text)
        update(min_trigger_count=5)
        with self.Session() as db:
            self.assertEqual(intervention_view(db)["pairs"],[])
            self.assertEqual(db.query(Threshold).first().min_count,5)
        update(min_negative_count=3,min_constructive_count=1)
        with self.Session() as db:
            view=intervention_view(db)
            self.assertEqual(view["feedback_total"],2)
            self.assertTrue(all(p["level"]==view["aspects"][0]["level"] for p in view["pairs"]))
        update(include_constructive=False)
        with self.Session() as db:self.assertEqual(intervention_view(db)["pairs"],[])
        update(min_negative_count=2)
        with self.Session() as db:
            self.assertEqual(intervention_view(db)["feedback_total"],2)
            alert=db.query(Alert).one()
            self.assertEqual(alert.note,"[Short term] Keep the existing draft")
            self.assertEqual(alert.quad_note,"Follow up Friday")
            self.assertEqual(alert.constructive_count,1)
        update(alert_window_days=45,include_constructive=True,min_negative_count=3,min_constructive_count=2)
        with self.Session() as db:
            self.assertEqual(intervention_view(db)["feedback_total"],3)
            self.assertEqual(db.query(Alert).count(),1)

    def test_settings_do_not_recreate_completed_alert_without_new_feedback(self):
        self.seed_comments()
        with self.Session() as db:alert_id=db.query(Alert).one().id
        approval=self.client.patch(f"/api/qa/alerts/{alert_id}",json={"status":"in-progress","note":"[Short term] Review document release"})
        self.assertEqual(approval.status_code,200,approval.text)
        response=self.client.patch(f"/api/qa/alerts/{alert_id}",json={"status":"resolved","completion_note":"Document release process reviewed."})
        self.assertEqual(response.status_code,200,response.text)
        with self.Session() as db:
            db.query(FeedbackLabel).filter(FeedbackLabel.feedback_id.in_(db.query(Feedback.id).filter(Feedback.department_id==2))).delete(synchronize_session=False)
            db.commit()
        response=self.client.patch("/api/qa/survey-settings",json={"min_trigger_count":1})
        self.assertEqual(response.status_code,200,response.text)
        with self.Session() as db:
            self.assertEqual(db.query(Alert).count(),1)
            self.assertEqual(intervention_view(db)["pairs"],[])
            row=Feedback(department_id=1,comment="A new slow release after completion",consent=True,
                         created_at=datetime.utcnow())
            db.add(row);db.flush()
            db.add(FeedbackLabel(feedback_id=row.id,aspect_id=1,sentiment="negative",aspect_source="model"))
            db.commit()
            from app.services.alerts import evaluate_thresholds
            new_alert=evaluate_thresholds(db,1)
            self.assertIsNotNone(new_alert)
            self.assertNotEqual(new_alert.id,alert_id)

    def test_quad_note_persists_through_draft_approval_completion_and_get(self):
        self.seed_comments()
        with self.Session() as db:alert_id=db.query(Alert).first().id
        path=f"/api/qa/alerts/{alert_id}"
        result=self.client.patch(path,json={"status":"acknowledged","note":"[Short term] Improve document turnaround","quad_note":"Follow up with Registrar on Friday.","department_id":1})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()["quad_note"],"Follow up with Registrar on Friday.")
        self.assertEqual(self.client.patch(path,json={"status":"in-progress"}).status_code,200)
        completed=self.client.patch(path,json={"status":"resolved","completion_note":"Queue reviewed"}).json()
        self.assertEqual(completed["quad_note"],"Follow up with Registrar on Friday.")
        self.assertEqual(completed["completion_note"],"Queue reviewed")
        history=self.client.get("/api/qa/alerts?status=resolved").json()
        self.assertEqual(history[0]["quad_note"],completed["quad_note"])
        self.assertEqual(self.client.patch(path,json={"quad_note":""}).json()["quad_note"],"")
        self.assertEqual(self.client.patch(path,json={"quad_note":"x"*4001}).status_code,422)

    def test_unclassified_written_comments_exclude_placeholders(self):
        with self.Session() as db:
            db.add_all([Feedback(department_id=1,comment="OK",consent=True),
                Feedback(department_id=1,comment="The equipment needs a closer inspection",consent=True),
                Feedback(department_id=1,comment="N/A",consent=True)])
            db.commit()
        result=self.client.get("/api/qa/feedback-page?sentiment=uncertain").json()
        self.assertEqual(result["total"],2)
        self.assertTrue(all(item["review_status"]=="unclassified" for item in result["items"]))
        excluded=self.client.get("/api/qa/feedback-page?sentiment=no_substantive").json()
        self.assertEqual(excluded["total"],2)
        self.assertEqual(self.client.get("/api/qa/feedback-page").json()["total"],2)


if __name__=="__main__":unittest.main()

"""Regressions for the user-requested service-area workflow and complete analytics."""
from datetime import datetime, timedelta
from app.models import (Alert, AuditEvent, Feedback, FeedbackLabel, Threshold, Respondent,
                        SurveySubmission, SurveyCycle, FeedbackAspectRun, FeedbackAspectTag)
from app.migrations import assign_existing_student_status
from app.services.admin_reads import intervention_view
from verify_college_analytics import CollegeAnalyticsTests

class ServiceAreaRevisionTests(CollegeAnalyticsTests):
    def test_default_suggestion_rewording_preserves_custom_rules_and_saved_actions(self):
        from app.models import InterventionRule
        from app.intervention_templates import LEGACY_RECOMMENDATIONS, CONCISE_RECOMMENDATIONS
        from app.migrations import shorten_default_recommendations
        original=LEGACY_RECOMMENDATIONS["processing_time"]
        with self.Session() as db:
            db.add_all([InterventionRule(aspect_id=1,diagnosed_pattern="Delay reports",recommendation=original),InterventionRule(aspect_id=2,diagnosed_pattern="Custom concern",recommendation="Keep this custom action exactly as written.")])
            db.add(Alert(aspect_id=1,department_id=1,negative_count=3,recommendation="",note="[Short term] "+original,status="acknowledged"));db.commit()
        shorten_default_recommendations(self.engine);shorten_default_recommendations(self.engine)
        with self.Session() as db:
            self.assertEqual(db.query(InterventionRule).filter_by(aspect_id=1).one().recommendation,CONCISE_RECOMMENDATIONS["processing_time"])
            self.assertEqual(db.query(InterventionRule).filter_by(aspect_id=2).one().recommendation,"Keep this custom action exactly as written.")
            self.assertEqual(db.query(Alert).one().note,"[Short term] "+original)
            self.assertEqual(db.query(AuditEvent).filter_by(action="default_recommendations_shortened").count(),1)

    def test_progress_report_includes_saved_actions_without_evaluation_matches(self):
        with self.Session() as db:
            db.add(Alert(aspect_id=1,department_id=1,negative_count=3,recommendation="",note="[Short term] Post clear processing times.",status="in-progress",confirmed_at=datetime.utcnow(),quad_note="Staff are reviewing the queue."));db.commit()
        result=self.client.post("/api/qa/reports",json={"colleges":["CCS"]})
        self.assertEqual(result.status_code,200,result.text)
        report=result.json()
        self.assertEqual(report["evaluations"],0)
        self.assertEqual(report["intervention_summary"]["approved"],1)
        self.assertEqual(report["actions"][0]["remarks"],"Staff are reviewing the queue.")
        self.assertIn("not assigned to a college or semester",report["action_scope"])

    def test_legacy_service_area_totals_report_saved_records_without_filling_gaps(self):
        from app.models import Department
        with self.Session() as db:
            db.add(Department(id=3,code="health",name="Health Service",is_active=True))
            students=[Respondent(student_number=f"26-01-{i:03d}",institutional_email=f"coverage{i}@udm.edu.ph",college="CAS") for i in (1,2)]
            db.add_all(students);db.flush()
            db.add_all([Feedback(department_id=1,respondent_id=students[0].id,comment="",rating=4,consent=True),Feedback(department_id=1,respondent_id=students[1].id,comment="",rating=5,consent=True),Feedback(department_id=3,respondent_id=students[0].id,comment="",rating=5,consent=True)]);db.commit()
        report=self.client.post("/api/qa/reports",json={}).json()
        self.assertEqual(report["respondents"],2)
        self.assertEqual({r["service_area"]:r["evaluations"] for r in report["star_ratings"]},{"Registrar":2,"Health Service":1})
        with self.Session() as db:self.assertEqual(db.query(Feedback).count(),3)

    def test_independent_constructive_boundary_updates_one_service_entry(self):
        with self.Session() as db:
            db.add(Threshold(aspect_id=1,min_count=3,window_days=14,include_constructive=True))
            for i in range(5):
                f=Feedback(department_id=1,comment=f"Please improve the queue and waiting area number {i}.",consent=True)
                db.add(f);db.flush()
                db.add(FeedbackLabel(feedback_id=f.id,aspect_id=1,sentiment="constructive"))
                db.add(FeedbackAspectRun(feedback_id=f.id,model_version="synthetic",status="assigned"))
                db.add_all([FeedbackAspectTag(feedback_id=f.id,aspect_id=1),FeedbackAspectTag(feedback_id=f.id,aspect_id=2)])
            db.commit()
        def configure(**fields):
            response=self.client.patch("/api/qa/survey-settings",json=fields)
            self.assertEqual(response.status_code,200,response.text)
        configure(min_negative_count=99,min_constructive_count=5)
        with self.Session() as db:
            result=intervention_view(db)
            self.assertEqual(len(result["pairs"]),1)
            row=result["pairs"][0];original_id=row["alert_id"]
            self.assertEqual((row["negative"],row["constructive"],row["level"]),(0,5,"medium"))
            self.assertEqual(len(row["aspect_names"]),2)
            self.assertTrue(db.get(Alert,original_id).service_area_scope)
            self.assertEqual(result["feedback_total"],0) # flag preview is negative-only
        configure(min_constructive_count=6)
        with self.Session() as db:self.assertEqual(intervention_view(db)["pairs"],[])
        with self.Session() as db:
            f=Feedback(department_id=1,comment="Please add another queue counter.",consent=True)
            db.add(f);db.flush();db.add(FeedbackLabel(feedback_id=f.id,aspect_id=2,sentiment="constructive"));db.commit()
            result=intervention_view(db)
            self.assertEqual(len(result["pairs"]),1)
            self.assertEqual(result["pairs"][0]["alert_id"],original_id)
            self.assertEqual(result["pairs"][0]["constructive"],6)
            self.assertEqual(db.query(Alert).filter(Alert.department_id==1).count(),1)
        configure(min_constructive_count=3)
        with self.Session() as db:self.assertEqual(intervention_view(db)["pairs"][0]["level"],"high")

    def test_recent_negative_preview_and_threshold_expiry(self):
        with self.Session() as db:
            db.add(Threshold(aspect_id=1,min_count=1,window_days=14,include_constructive=True))
            for text,days,sentiment in [("Old delayed queue",30,"negative"),("Yesterday delayed queue",1,"negative"),("New delayed queue",0,"negative"),("Please improve queue",0,"constructive")]:
                f=Feedback(department_id=1,comment=text,consent=True,created_at=datetime.utcnow()-timedelta(days=days))
                db.add(f);db.flush();db.add(FeedbackLabel(feedback_id=f.id,aspect_id=1,sentiment=sentiment))
            db.commit()
            view=intervention_view(db)
            self.assertEqual(view["feedback_total"],2)
            self.assertEqual([f.comment for f in view["feedback"]],["New delayed queue","Yesterday delayed queue"])
            self.assertEqual(len(view["pairs"]),1)

    def test_all_star_questions_and_confirmed_historical_status(self):
        with self.Session() as db:
            db.add(SurveyCycle(id=1,academic_year="2026-2027",semester="1st"))
            people=[Respondent(student_number=f"26-01-{i:03d}",institutional_email=f"rating{i}@udm.edu.ph",college="CAS") for i in (1,2)]
            db.add_all(people);db.flush()
            submission=SurveySubmission(cycle_id=1,respondent_id=people[1].id,reference="synthetic-rating",receipt_hash="rating",request_key="rating",payload_hash="rating",student_number=people[1].student_number,institutional_email=people[1].institutional_email,college="CAS",student_status="irregular",consent_version="2026-10-29")
            db.add(submission);db.flush()
            db.add_all([Feedback(department_id=1,respondent_id=people[0].id,cycle_id=1,comment="",rating_1=1,rating_2=3,rating_3=5,consent=True),
                Feedback(department_id=2,respondent_id=people[0].id,cycle_id=1,comment="",rating=4,consent=True),
                Feedback(department_id=1,respondent_id=people[1].id,submission_id=submission.id,cycle_id=1,comment="",rating_1=5,rating_2=5,rating_3=5,consent=True)])
            db.commit()
        assign_existing_student_status(self.engine);assign_existing_student_status(self.engine)
        with self.Session() as db:
            self.assertEqual(db.query(AuditEvent).filter_by(action="historical_student_status_assigned").count(),1)
            self.assertEqual(db.query(SurveySubmission).one().student_status,"irregular")
        report=self.client.post("/api/qa/reports",json={"cycle_id":1}).json()
        self.assertEqual({r["status"]:r["respondents"] for r in report["student_status"]},{"regular":1,"irregular":1})
        stars={r["service_area"]:r for r in report["star_ratings"]}
        self.assertEqual(stars["Registrar"]["stars"],{"1":1,"2":0,"3":1,"4":0,"5":4})
        self.assertEqual(stars["Laboratory"]["rated_answers"],1)
        self.assertEqual(report["comments"],0)
        self.assertEqual(self.client.post("/api/qa/reports",json={"student_status":"regular"}).json()["respondents"],1)
        self.assertEqual(self.client.post("/api/qa/reports",json={"student_status":"irregular"}).json()["respondents"],1)

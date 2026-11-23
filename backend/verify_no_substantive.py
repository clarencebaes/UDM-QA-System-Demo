"""No-substantive is a review status, never a fourth sentiment label."""
import unittest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import case
from app.models import Alert, Department, Feedback, FeedbackLabel, Respondent, Threshold
from app.services.dashboard import aggregate_dashboard
from app.services.admin_reads import feedback_page, intervention_view
from app.services.feedback_text import is_no_substantive_feedback, no_substantive_feedback
from app.services.classify import classify_feedback
import verify_college_analytics as fixtures


class NoSubstantiveTests(fixtures.CollegeAnalyticsTests):
    def test_exact_placeholder_rules_match_sql_and_preserve_real_feedback(self):
        examples={"N/A":True,"n. a.":True,"NA":True,"none":True,"None.":True,
          "no comment":True,"No comments!":True,"not applicable":True,"nothing to add":True,
          "---":True,"...":True,"?!":True,"—":True,"":False," ":False,"OK":False,
          "No":False,"Good":False,"Bad":False,"No hot water":False,
          "None of the computers work":False,"N/A but the waiting room is dirty":False}
        with self.Session() as db:
            for text,expected in examples.items():
                item=Feedback(department_id=1,comment=text,consent=True)
                db.add(item);db.flush()
                actual=db.query(case((no_substantive_feedback(),1),else_=0)).select_from(Feedback).filter(Feedback.id==item.id).scalar()
                self.assertEqual(bool(actual),expected,text)
                self.assertEqual(is_no_substantive_feedback(text),expected,text)

    def test_existing_labels_are_preserved_but_excluded_from_counts_and_triggers(self):
        with self.Session() as db:
            student=Respondent(student_number="00-00-001",institutional_email="review-test@udm.edu.ph",college="CAS")
            db.add(student);db.flush()
            for text,sentiment in (("N/A","negative"),("None","positive"),("---",None),("OK",None),("Needs human review",None),("Good service","positive")):
                row=Feedback(department_id=1,respondent_id=student.id,comment=text,consent=True,rating=5)
                db.add(row);db.flush()
                if sentiment:db.add(FeedbackLabel(feedback_id=row.id,aspect_id=1,sentiment=sentiment,aspect_source="model"))
            db.add_all([Threshold(aspect_id=1,min_count=1,window_days=14,include_constructive=True),
                Alert(aspect_id=1,negative_count=1,constructive_count=0,recommendation="",status="new")]);db.commit()
            result=aggregate_dashboard(db)
            self.assertEqual((result["unique_respondents"],result["written_comments"],result["total_comments"]),(1,6,3))
            self.assertEqual((result["no_substantive_comments"],result["positive"],result["negative"]),(3,1,0))
            self.assertEqual(result["unclassified_comments"],2)
            page=feedback_page(db,sentiment="no_substantive")
            self.assertEqual(page["total"],2)
            self.assertEqual(page["counts"],dict(all=3,positive=1,negative=0,neutral=0,constructive=0,unclassified=2))
            self.assertEqual(feedback_page(db,sentiment="unclassified")["total"],2)
            self.assertEqual(feedback_page(db,search="Unclassified")["total"],2)
            self.assertEqual(feedback_page(db,search="unclassified written")["total"],2)
            self.assertEqual(feedback_page(db,search="Positive")["total"],1)
            self.assertEqual(intervention_view(db)["feedback_total"],0)
            self.assertEqual(db.query(FeedbackLabel).count(),3)
        response=self.client.get("/api/qa/feedback-page?sentiment=no_substantive")
        self.assertEqual(response.status_code,200,response.text)
        self.assertTrue(all(row["review_status"]=="unclassified" and row["sentiment"] is None for row in response.json()["items"]))
        report=self.client.post("/api/qa/reports",json={}).json()
        self.assertEqual((report["comments"],report["no_substantive_comments"],report["unclassified_comments"],report["unclassified_entries"]),(3,3,2,2))
        self.assertEqual(report["unclassified_entries"],response.json()["counts"]["unclassified"])


    def test_new_placeholder_is_not_sent_to_sentiment_or_aspect_predictors(self):
        with self.Session() as db:
            row=Feedback(department_id=1,comment="No comment",consent=True)
            db.add(row);db.commit()
            with patch("app.services.classify._sentiment_model") as sentiment, patch("app.services.classify._aspect_model") as aspect:
                self.assertIsNone(classify_feedback(db,row))
                sentiment.predict.assert_not_called();aspect.predict.assert_not_called()
            self.assertEqual(db.query(FeedbackLabel).count(),0)

    def test_flagged_pages_cover_all_items_and_retain_campus_eligibility(self):
        with self.Session() as db:
            now=datetime.utcnow()
            for i in range(5):
                row=Feedback(department_id=1,comment=f"Genuine complaint {i}",consent=True,created_at=now)
                db.add(row);db.flush();db.add(FeedbackLabel(feedback_id=row.id,aspect_id=1,sentiment="negative",aspect_source="model"))
            db.add_all([Threshold(aspect_id=1,min_count=3,window_days=14,include_constructive=True),Alert(aspect_id=1,negative_count=5,constructive_count=0,recommendation="",status="new")]);db.commit()
            ids=[]
            for page in (1,2,3):
                view=intervention_view(db,now=now,page=page)
                self.assertEqual(view["feedback_total"],5)
                self.assertEqual(view["feedback_page"],page)
                self.assertEqual(view["aspects"][0]["count"],5)
                ids.extend(row.id for row in view["feedback"])
            self.assertEqual(len(set(ids)),5)
            self.assertEqual(intervention_view(db,now=now,page=999)["feedback_page"],3)


if __name__=="__main__":unittest.main()

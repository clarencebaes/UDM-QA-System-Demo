"""Students, per-area evaluations, written comments and classifications differ."""
import unittest
from app.models import Department, Feedback, FeedbackLabel, Respondent
from app.service_areas import SERVICE_AREAS
from app.services.dashboard import aggregate_dashboard
from app.services.admin_reads import feedback_page
import verify_college_analytics as fixtures


class CommentAccountingTests(fixtures.CollegeAnalyticsTests):
    def test_two_students_answering_31_areas_count_as_two_responses(self):
        with self.Session() as db:
            existing={d.code:d for d in db.query(Department).all()}
            for area in SERVICE_AREAS:
                if area["code"] not in existing:
                    db.add(Department(code=area["code"],name=area["name"],is_active=True))
            db.flush()
            areas=db.query(Department).all()
            self.assertEqual(len(areas),16)
            students=[Respondent(student_number="00-00-001",institutional_email="metrics-one@udm.edu.ph",college="CCS"),
                      Respondent(student_number="00-00-002",institutional_email="metrics-two@udm.edu.ph",college="CBM")]
            db.add_all(students);db.flush()
            index=0
            for student in students:
                for area in areas:
                    if area.code=="laboratory" and student.college=="CBM":continue
                    text="Excellent service" if index<5 else "ok" if index==5 else "Needs review" if index==6 else ""
                    item=Feedback(respondent_id=student.id,department_id=area.id,comment=text,rating=5,consent=True)
                    db.add(item);db.flush()
                    if index<5:db.add(FeedbackLabel(feedback_id=item.id,aspect_id=1,sentiment="positive",aspect_source="model"))
                    index+=1
            db.commit()
            result=aggregate_dashboard(db)
            self.assertEqual(result["total_feedback"],31)
            self.assertEqual(result["unique_respondents"],2)
            self.assertEqual((result["total_comments"],result["classified_comments"],result["unclassified_comments"]),(7,5,2))
            self.assertEqual((result["short_unclassified_comments"],result["pending_classification_comments"]),(1,1))
            self.assertEqual(sum(r["positive"]+r["negative"]+r["constructive"] for r in result["by_aspect"]),5)
            self.assertEqual(feedback_page(db)["total"],7)
            unclassified=feedback_page(db,sentiment="unclassified")
            self.assertEqual(unclassified["total"],2)
            self.assertTrue(all(r.label is None for r in unclassified["items"]))
            selected=aggregate_dashboard(db,college="CCS")
            self.assertEqual((selected["unique_respondents"],selected["total_feedback"]),(1,16))
            other=aggregate_dashboard(db,college="CBM")
            self.assertEqual((other["unique_respondents"],other["total_feedback"]),(1,15))

    def test_all_comments_include_unlinked_and_historical_records_but_not_whitespace(self):
        with self.Session() as db:
            legacy=Department(code="retired-test-area",name="Historical service",is_active=False)
            db.add(legacy);db.flush()
            db.add_all([Feedback(department_id=legacy.id,comment="Legacy comment",consent=True),
                        Feedback(department_id=1,comment=" \n\t ",consent=True)])
            db.commit()
            result=aggregate_dashboard(db)
            self.assertEqual(result["total_comments"],1)
            self.assertEqual(result["unassigned_comments"],1)
            self.assertEqual(result["unique_respondents"],0)
            self.assertEqual(feedback_page(db)["total"],1)
            response=self.client.get("/api/qa/feedback-page?sentiment=unclassified")
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()["total"],1)

    def test_evaluation_config_is_public_and_preserves_applicability(self):
        response=self.client.get("/api/evaluation-config")
        self.assertEqual(response.status_code,200,response.text)
        payload=response.json()
        self.assertEqual(len(payload["colleges"]),7)
        lab=next(a for a in payload["departments"] if a["code"]=="laboratory")
        self.assertEqual(set(lab["applicable_colleges"]),{"CCS","CHS","CAS","CCJ","CED"})
        self.assertNotIn("student_number",str(payload))


if __name__=="__main__":unittest.main()

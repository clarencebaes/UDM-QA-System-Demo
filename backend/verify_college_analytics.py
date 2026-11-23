"""College persistence and analytics scope regressions using isolated SQLite."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import get_current_user
from app.colleges import configured_colleges, seed_colleges
from app.database import Base, get_db
from app.main import app
from app.models import Aspect, CollegeHeadcount, Department, Feedback, FeedbackLabel, Respondent, User


class CollegeAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.legacy_gate = patch("app.main.settings.legacy_submission_api", True)
        self.legacy_gate.start()
        self.addCleanup(self.legacy_gate.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="quad-college-regression-")
        self.url = "sqlite:///" + (Path(self.temp.name) / "test.db").as_posix()
        self.engine = self.make_engine() if hasattr(self, "make_engine") else create_engine(self.url)
        if hasattr(self, "make_engine"):
            self.url = self.engine.url.render_as_string(hide_password=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            seed_colleges(db)
            db.add_all([Department(id=1, code="registrar", name="Registrar", is_active=True),
                        Department(id=2, code="laboratory", name="Laboratory", is_active=True),
                        Aspect(id=1, code="processing_time", name="Processing Time"),
                        Aspect(id=2, code="facility_conditions", name="Facility Conditions")])
            db.commit()
        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: User(username="test-admin", role="qa")
        self.classifier = patch("app.main.classify_feedback", return_value=None)
        self.classifier.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.classifier.stop()
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp.cleanup()

    def submit(self, college, unique=1):
        return self.client.post("/api/feedback", json=dict(department_id=1, college=college,
            student_number=f"00-00-{unique:03d}", institutional_email=f"college-test-{unique}@udm.edu.ph", consent=True, rating=5))

    def test_added_college_validates_feedback_and_headcounts(self):
        response = self.client.post("/api/colleges", json={"code": " new ", "name": "New College"})
        # Code length is limited before normalization, so use the configured field shape.
        self.assertEqual(response.status_code, 422)
        response = self.client.post("/api/colleges", json={"code": "new", "name": "New College"})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(self.client.post("/api/colleges", json={"code": "NEW2", "name": "Second College"}).status_code, 201)
        self.assertEqual(self.client.post("/api/colleges", json={"code": "DUP", "name": "new college"}).status_code, 400)
        self.assertEqual(self.submit("NEW").status_code, 200)
        response = self.client.put("/api/qa/headcounts", json={"items": [{"college": "NEW", "headcount": 54}]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(any(row["college"] == "NEW" and row["headcount"] == 54 for row in response.json()))

    def test_database_reopen_preserves_additions_and_removals(self):
        self.assertEqual(self.client.post("/api/colleges", json={"code": "NEW", "name": "New College"}).status_code, 201)
        self.assertEqual(self.client.delete("/api/colleges/CBM").status_code, 204)
        self.engine.dispose()
        reopened = create_engine(self.url)
        with sessionmaker(bind=reopened)() as db:
            seed_colleges(db)
            db.commit()
            codes = {row["code"] for row in configured_colleges(db)}
            self.assertIn("NEW", codes)
            self.assertNotIn("CBM", codes)
        reopened.dispose()
        self.assertEqual(self.submit("NEW").status_code, 200)
        self.assertEqual(self.submit("CBM", unique=2).status_code, 422)

    def test_removal_retains_historical_responses_and_can_be_reactivated(self):
        self.assertEqual(self.submit("CAS").status_code, 200)
        self.assertEqual(self.client.delete("/api/colleges/CAS").status_code, 204)
        dashboard = self.client.get("/api/qa/dashboard").json()
        self.assertEqual(dashboard["unique_respondents"], 1)
        self.assertEqual(next(row for row in dashboard["by_college"] if row["college"] == "CAS")["responses"], 1)
        self.assertEqual(self.client.post("/api/colleges", json={"code": "CAS", "name": "Arts and Sciences"}).status_code, 201)
        self.assertEqual(self.client.post("/api/colleges", json={"code": "CAS", "name": "Duplicate"}).status_code, 400)

    def test_unknown_headcounts_are_rejected_before_any_change(self):
        response = self.client.put("/api/qa/headcounts", json={"items": [
            {"college": "CAS", "headcount": 54}, {"college": "ZZZ", "headcount": 3}]})
        self.assertEqual(response.status_code, 422)
        with self.Session() as db:
            self.assertEqual(db.query(CollegeHeadcount).count(), 0)

    def test_college_filter_scopes_every_dashboard_aggregate(self):
        with self.Session() as db:
            for unique, college, department, aspect, sentiment in (
                (1, "CAS", 1, 1, "positive"), (2, "CCS", 2, 2, "negative")):
                respondent = Respondent(student_number=f"00-00-{unique:03d}", institutional_email=f"analytics-{unique}@udm.edu.ph", college=college)
                db.add(respondent); db.flush()
                feedback = Feedback(respondent_id=respondent.id, department_id=department, comment="Synthetic test comment", consent=True, rating=5)
                db.add(feedback); db.flush()
                db.add(FeedbackLabel(feedback_id=feedback.id, aspect_id=aspect, sentiment=sentiment, aspect_source="model"))
                db.add(CollegeHeadcount(college=college, headcount=100))
            db.commit()
        all_rows = self.client.get("/api/qa/dashboard").json()
        self.assertEqual(all_rows["total_feedback"], 2)
        response = self.client.get("/api/qa/dashboard?college=cas")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual((data["total_feedback"], data["positive"], data["negative"], data["unique_respondents"]), (1, 1, 0, 1))
        self.assertEqual(data["overall_enrolled"], 100)
        self.assertEqual(data["overall_response_rate"], 1)
        self.assertEqual([row["service_area"] for row in data["by_service_area"]], ["Registrar"])
        self.assertTrue(all(row["negative"] == 0 for row in data["by_aspect"]))
        self.assertEqual(self.client.get("/api/qa/dashboard?college=CHS").json()["total_feedback"], 0)


if __name__ == "__main__":
    unittest.main()

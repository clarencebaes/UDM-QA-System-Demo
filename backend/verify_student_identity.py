"""Shape-only student identity validation; uses synthetic identifiers and SQLite."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.colleges import validate_student_number
from app.database import Base, get_db
from app.main import app
from app.models import Department, Feedback, Respondent, SurveySettings

CASES = json.loads((Path(__file__).resolve().parents[1]/"tests"/"fixtures"/"student-identity.json").read_text(encoding="utf-8"))

class IdentityPolicyTests(unittest.TestCase):
    def test_shared_cases(self):
        for item in CASES:
            with self.subTest(value=item["value"]):
                if item["valid"]:
                    self.assertEqual(validate_student_number(item["value"]),item["normalized"])
                else:
                    with self.assertRaises(ValueError): validate_student_number(item["value"])

class SubmissionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.legacy_gate = patch("app.main.settings.legacy_submission_api", True)
        self.legacy_gate.start()
        self.addCleanup(self.legacy_gate.stop)
        self.engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session=sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add_all([Department(id=1,code="REG",name="Registrar",is_active=True),
                        Department(id=2,code="LIB",name="Library",is_active=True),
                        SurveySettings(is_active=True)])
            db.commit()
        def override_db():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db]=override_db
        self.classifier=patch("app.main.classify_feedback",return_value=None)
        self.classifier.start()
        self.client=TestClient(app)
        self.payload=dict(student_number="01-18-007",institutional_email="identity-test@udm.edu.ph",college="CED",department_id=1,consent=True,rating=5,comment="")

    def tearDown(self):
        self.client.close()
        self.classifier.stop()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_accepts_number_without_year_or_college_interpretation(self):
        response=self.client.post("/api/feedback",json=self.payload)
        self.assertEqual(response.status_code,200,response.text)
        with self.Session() as db:
            respondent=db.query(Respondent).one()
            self.assertEqual(respondent.student_number,"01-18-007")
            self.assertEqual(respondent.college,"CED")

    def test_batch_keeps_separately_selected_college(self):
        items=[dict(self.payload,student_number="99-00-001",college="CAS",department_id=department) for department in (1,2)]
        response=self.client.post("/api/feedback/batch",json={"items":items})
        self.assertEqual(response.status_code,200,response.text)
        with self.Session() as db:
            self.assertEqual(db.query(Respondent).one().college,"CAS")
            self.assertEqual(db.query(Feedback).count(),2)

    def test_malformed_ids_and_invalid_college_still_rejected(self):
        for route in ("/api/feedback","/api/feedback/batch"):
            for changes in (dict(student_number="01-18-07"),dict(college="ZZZ")):
                body=dict(self.payload,**changes)
                response=self.client.post(route,json={"items":[body]} if route.endswith("batch") else body)
                self.assertEqual(response.status_code,422,response.text)
        with self.Session() as db:self.assertEqual(db.query(Respondent).count(),0)

    def test_duplicate_submission_protection_unchanged(self):
        with self.Session() as db:
            respondent=Respondent(student_number=self.payload["student_number"],institutional_email=self.payload["institutional_email"],college="CED")
            db.add(respondent);db.flush()
            db.add_all([Feedback(respondent_id=respondent.id,department_id=1,comment="",consent=True) for _ in range(16)])
            db.commit()
        response=self.client.post("/api/feedback/batch",json={"items":[self.payload]})
        self.assertEqual(response.status_code,400,response.text)
        self.assertIn("already submitted",response.json()["detail"])

if __name__=="__main__":unittest.main()

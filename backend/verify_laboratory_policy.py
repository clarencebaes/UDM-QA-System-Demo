"""Synthetic in-memory API regression checks; never submits to production."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Department, Feedback, Respondent, SurveySettings
from app.service_areas import SERVICE_AREAS, LABORATORY_COLLEGES


class LaboratoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.legacy_gate = patch("app.main.settings.legacy_submission_api", True)
        self.legacy_gate.start()
        self.addCleanup(self.legacy_gate.stop)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            for index, area in enumerate(SERVICE_AREAS, 1):
                db.add(Department(id=index, code=area["code"], name=area["name"], is_active=True))
            db.add(SurveySettings(is_active=True))
            db.commit()
        def override_db():
            with self.Session() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.classifier = patch("app.main.classify_feedback", return_value=None)
        self.classifier.start()
        self.client = TestClient(app)
        self.lab = next(i for i, area in enumerate(SERVICE_AREAS, 1) if area["code"] == "laboratory")

    def tearDown(self):
        self.client.close()
        self.classifier.stop()
        app.dependency_overrides.clear()
        self.engine.dispose()

    def payload(self, college="CBM", department=1, unique=1):
        return dict(student_number=f"00-00-{unique:03d}", institutional_email=f"lab-test-{unique}@udm.edu.ph",
                    college=college, department_id=department, consent=True, comment="",
                    rating=5, rating_1=5, rating_2=5, rating_3=5)

    def test_metadata_lists_exact_policy(self):
        rows = self.client.get("/api/departments").json()
        lab = next(row for row in rows if row["code"] == "laboratory")
        self.assertEqual(lab["applicable_colleges"], list(LABORATORY_COLLEGES))
        self.assertTrue(all(row["applicable_colleges"] is None for row in rows if row["code"] != "laboratory"))

    def test_all_five_colleges_can_submit_laboratory(self):
        for unique, college in enumerate(LABORATORY_COLLEGES, 1):
            with self.subTest(college=college):
                response = self.client.post("/api/feedback", json=self.payload(college, self.lab, unique))
                self.assertEqual(response.status_code, 200, response.text)

    def test_other_colleges_cannot_submit_lab_via_either_route(self):
        for college in ("CBM", "CPPG"):
            for route in ("/api/feedback", "/api/feedback/batch"):
                with self.subTest(college=college, route=route):
                    payload = self.payload(college, self.lab)
                    body = {"items": [self.payload(college), payload]} if route.endswith("batch") else payload
                    response = self.client.post(route, json=body)
                    self.assertEqual(response.status_code, 400, response.text)
        with self.Session() as db:
            self.assertEqual(db.query(Feedback).count(), 0)
            self.assertEqual(db.query(Respondent).count(), 0)

    def test_complete_fifteen_and_sixteen_area_batches_cannot_repeat(self):
        for unique, college in enumerate(("CBM", "CPPG", "CCS", "CHS", "CAS", "CCJ", "CED"), 1):
            ids = [i for i in range(1, 17) if i != self.lab or college in LABORATORY_COLLEGES]
            body = {"items": [self.payload(college, department, unique) for department in ids]}
            response = self.client.post("/api/feedback/batch", json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(len(response.json()), 16 if college in LABORATORY_COLLEGES else 15)
            self.assertEqual(self.client.post("/api/feedback/batch", json=body).status_code, 400)
            self.assertEqual(self.client.post("/api/feedback", json=body["items"][0]).status_code, 400)

    def test_partial_submission_cannot_repeat_areas_but_can_finish_remaining_areas(self):
        first = self.payload()
        self.assertEqual(self.client.post("/api/feedback", json=first).status_code, 200)
        self.assertEqual(self.client.post("/api/feedback/batch", json={"items": [first]}).status_code, 400)
        remaining = [self.payload(department=i) for i in range(2, 17) if i != self.lab]
        response = self.client.post("/api/feedback/batch", json={"items": remaining})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.post("/api/feedback", json=first).status_code, 400)
        with self.Session() as db:
            self.assertEqual(db.query(Feedback).count(), 15)

    def test_mixed_identity_and_duplicate_batch_areas_rejected_before_writing(self):
        for items in ([self.payload(), self.payload(unique=2, department=2)],
                      [self.payload(), self.payload()],
                      [self.payload(), self.payload(college="CAS", department=2)]):
            self.assertEqual(self.client.post("/api/feedback/batch", json={"items": items}).status_code, 400)
        with self.Session() as db:
            self.assertEqual(db.query(Respondent).count(), 0)
            self.assertEqual(db.query(Feedback).count(), 0)

    def test_college_cannot_change_after_partial_submission(self):
        self.assertEqual(self.client.post("/api/feedback", json=self.payload()).status_code, 200)
        response = self.client.post("/api/feedback", json=self.payload(college="CCS", department=self.lab))
        self.assertEqual(response.status_code, 400)
        with self.Session() as db:
            self.assertEqual(db.query(Respondent).one().college, "CBM")


if __name__ == "__main__":
    unittest.main()

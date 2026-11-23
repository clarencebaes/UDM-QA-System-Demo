"""Regression: one active alert per eligible service area."""
from datetime import datetime, timedelta, timezone
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base
from app.models import Alert, Aspect, Department, Feedback, FeedbackLabel, Threshold
from app.services.alerts import evaluate_thresholds, service_area_evidence
from app.services.admin_reads import intervention_view

class AlertScopeTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(Aspect(id=1,code="staff_responsiveness",name="Staff Responsiveness"))
        self.threshold=Threshold(aspect_id=1,min_count=3,window_days=14,include_constructive=True)
        self.db.add(self.threshold)
        for i,name in enumerate(("Registrar","Campus Security","Library"),1):
            self.db.add(Department(id=i,code=f"AREA{i}",name=name,is_active=True))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add(self, department, sentiment="negative", days=0):
        feedback=Feedback(department_id=department,comment="Staff concern",consent=True,created_at=datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(days=days))
        self.db.add(feedback)
        self.db.flush()
        self.db.add(FeedbackLabel(feedback_id=feedback.id,aspect_id=1,sentiment=sentiment,aspect_source="model"))
        self.db.commit()

    def test_three_areas_have_independent_thresholds_and_one_alert_each(self):
        for area in (1,2,3): self.add(area)
        self.assertIsNone(evaluate_thresholds(self.db,1))
        for area in (1,2,3):
            self.add(area);self.add(area)
        evaluate_thresholds(self.db,1)
        alerts=self.db.query(Alert).all()
        self.assertEqual({a.department_id for a in alerts},{1,2,3})
        self.assertTrue(all(a.negative_count==3 for a in alerts))
        evaluate_thresholds(self.db,1)
        self.assertEqual(self.db.query(Alert).count(),3)

    def test_constructive_toggle_controls_eligibility_without_losing_evidence(self):
        self.add(1);self.add(1)
        for _ in range(3):self.add(1,"constructive")
        alert=evaluate_thresholds(self.db,1)
        self.assertEqual((alert.negative_count,alert.constructive_count),(2,3))
        self.assertEqual(len(intervention_view(self.db)["pairs"]),1)
        self.threshold.include_constructive=False;self.db.commit()
        self.assertEqual(intervention_view(self.db)["pairs"],[])
        self.assertFalse(service_area_evidence(self.db)[0][1]["eligible"])
        self.db.refresh(alert)
        self.assertEqual((alert.negative_count,alert.constructive_count),(2,3))

    def test_expired_feedback_cannot_complete_trigger(self):
        self.add(1);self.add(1);self.add(1,days=15)
        self.assertIsNone(evaluate_thresholds(self.db,1))
        self.assertEqual(self.db.query(Alert).count(),0)

    def test_settings_change_reuses_open_alert_and_updates_counts(self):
        for _ in range(3):self.add(1)
        alert=evaluate_thresholds(self.db,1);first_id=alert.id
        self.threshold.min_count=4;self.db.commit()
        self.assertEqual(intervention_view(self.db)["pairs"],[])
        self.add(1)
        self.assertEqual(evaluate_thresholds(self.db,1).id,first_id)
        self.assertEqual(len(intervention_view(self.db)["pairs"]),1)
        self.assertEqual(self.db.query(Alert).count(),1)

if __name__=="__main__":unittest.main()

"""Guard against per-feedback SQL round trips in admin read endpoints."""
import unittest

from sqlalchemy import event

import verify_college_analytics as fixtures
from app.models import Feedback, FeedbackLabel, Respondent


class AdminLoadingTests(fixtures.CollegeAnalyticsTests):
    def test_read_query_count_stays_bounded_as_feedback_grows(self):
        def counts():
            result = {}
            for path in ("dashboard", "feedback"):
                statements = []
                def record(*args):
                    statements.append(args[2])
                event.listen(self.engine, "before_cursor_execute", record)
                try:
                    response = self.client.get(f"/api/qa/{path}")
                    self.assertEqual(response.status_code, 200, response.text)
                finally:
                    event.remove(self.engine, "before_cursor_execute", record)
                result[path] = len(statements)
            return result

        def add_rows(start, stop):
            with self.Session() as db:
                for i in range(start, stop):
                    respondent = Respondent(student_number=f"00-00-{i:03d}",
                        institutional_email=f"load-test-{i}@udm.edu.ph", college="CAS")
                    db.add(respondent)
                    db.flush()
                    feedback = Feedback(respondent_id=respondent.id, department_id=1,
                        comment="Synthetic performance fixture", consent=True, rating=5)
                    db.add(feedback)
                    db.flush()
                    db.add(FeedbackLabel(feedback_id=feedback.id, aspect_id=1,
                        sentiment="positive", aspect_source="model"))
                db.commit()

        add_rows(1, 3)
        small = counts()
        add_rows(3, 123)
        large = counts()
        print(f"Admin SQL counts: 2 rows={small}; 122 rows={large}")
        for path in small:
            self.assertLessEqual(large[path], small[path] + 2, path)
            # One bounded aggregate adds polarity/type/language summaries.
            self.assertLessEqual(large[path], 13, path)


if __name__ == "__main__":
    unittest.main()

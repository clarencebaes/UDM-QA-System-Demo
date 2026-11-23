"""Verification script for the backend fixes (run from the backend folder).

Exercises the code paths that were broken before the fix:
  * college validation (validate_college against COLLEGE_CODES)
  * /api/qa/thresholds, /api/qa/intervention-rules  (used to raise NameError)
  * /api/qa/alerts, /api/qa/feedback                  (used to raise NameError)
  * /api/qa/dashboard                                 (aspect name lookups)
  * /api/feedback                                     (college validation path)

Run:  python verify_fixes.py
"""

import os
import sys

os.environ.setdefault("JWT_SECRET", "verify-only-secret")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.colleges import validate_college  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Alert,
    Aspect,
    Department,
    Feedback,
    FeedbackLabel,
    InterventionRule,
    Respondent,
    SurveySettings,
    Threshold,
    User,
)

FAILS = []
PASSES = []


def check(name, condition, extra=""):
    if condition:
        PASSES.append(name)
        print(f"  PASS  {name}")
    else:
        FAILS.append(f"{name} {extra}")
        print(f"  FAIL  {name} {extra}")

def main():
    from app.main import settings
    settings.legacy_submission_api = True
    # in-memory SQLite so the test needs no MySQL
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSession()
    db.add_all([
        Aspect(id=1, code="PROC", name="Processing Time"),
        Aspect(id=2, code="STAFF", name="Staff Responsiveness"),
        Department(id=1, code="REG", name="Registrar", is_active=True),
        User(id=1, username="qa", password_hash=hash_password("pw123456"),
             display_name="QA", role="qa"),
        Threshold(id=1, aspect_id=1, min_count=3, window_days=14, include_constructive=False),
        InterventionRule(id=1, aspect_id=1, diagnosed_pattern="Slow", recommendation="Add staff"),
        SurveySettings(id=1, start_date=None, end_date=None, is_active=True),
    ])
    db.commit()

    client = TestClient(app)

    print("\n[1] College validation unit checks")
    try:
        got = validate_college("cas")
        check("validate_college('cas') -> 'CAS'", got == "CAS", got)
    except Exception as exc:  # noqa: BLE001
        check("validate_college('cas') -> 'CAS'", False, repr(exc))
    try:
        validate_college("NOPE")
        check("validate_college('NOPE') raises ValueError", False, "no raise")
    except ValueError:
        check("validate_college('NOPE') raises ValueError", True)
    except Exception as exc:  # noqa: BLE001
        check("validate_college('NOPE') raises ValueError", False, repr(exc))

    print("\n[2] Login")
    r = client.post("/api/auth/login", json={"username": "qa", "password": "pw123456"})
    check("login returns 200", r.status_code == 200, r.text[:200])
    token = r.json().get("access_token") if r.status_code == 200 else None
    if not token:
        print("Cannot continue without a token.")
        return 1
    auth = {"Authorization": f"Bearer {token}"}

    print("\n[3] Previously NameError-broken GET endpoints")
    for path in (
        "/api/qa/thresholds",
        "/api/qa/intervention-rules",
        "/api/qa/alerts",
        "/api/qa/feedback",
        "/api/qa/dashboard",
        "/api/qa/survey-settings",
    ):
        r = client.get(path, headers=auth)
        check(f"GET {path} -> 200", r.status_code == 200, r.text[:300])

    print("\n[4] Aspect resolution in payloads")
    r = client.get("/api/qa/thresholds", headers=auth)
    check("GET /api/qa/thresholds returns a list", r.status_code == 200, r.text[:200])
    check("thresholds list is non-empty", bool(r.json()), f"{r.text[:300]}")
    if r.status_code == 200 and r.json():
        check("threshold aspect_code resolved",
              r.json()[0].get("aspect_code") == "PROC", str(r.json()[0]))
    r = client.get("/api/qa/intervention-rules", headers=auth)
    check("intervention-rules list is non-empty", bool(r.json()), f"{r.text[:300]}")
    if r.status_code == 200 and r.json():
        check("rule aspect_code resolved",
              r.json()[0].get("aspect_code") == "PROC", str(r.json()[0]))

    print("\n[5] Alert / feedback rows with aspect lookups")
    db.add_all([
        Respondent(id=1, student_number="23-23-001",
                   institutional_email="a@udm.edu.ph", college="CCS"),
        Feedback(id=1, respondent_id=1, department_id=1, rating=1, comment="Very slow service"),
        FeedbackLabel(id=1, feedback_id=1, aspect_id=1, aspect_source="student",
                      sentiment="negative"),
        Alert(id=1, aspect_id=1, department_id=1, negative_count=3,
              constructive_count=0, recommendation="Do something",
              status="new"),
    ])
    db.commit()

    r = client.get("/api/qa/feedback", headers=auth)
    check("GET /api/qa/feedback with label -> 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200 and r.json():
        row = r.json()[0]
        check("feedback aspect name resolved", row.get("aspect") == "Processing Time", str(row))
        check("feedback department resolved", row.get("department") == "Registrar", str(row))

    r = client.get("/api/qa/alerts", headers=auth)
    check("GET /api/qa/alerts with aspect -> 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200 and r.json():
        a = r.json()[0]
        check("alert aspect name resolved", a.get("aspect") == "Processing Time", str(a))
        check("alert aspect_code resolved", a.get("aspect_code") == "PROC", str(a))

    print("\n[6] PATCH endpoints (single-object serializers)")
    r = client.patch("/api/qa/thresholds/1", headers=auth, json={"min_count": 5})
    check("PATCH /api/qa/thresholds/1 -> 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        check("patched threshold aspect_code", r.json().get("aspect_code") == "PROC", r.text[:200])

    r = client.patch("/api/qa/intervention-rules/1", headers=auth,
                     json={"recommendation": "New recommendation"})
    check("PATCH /api/qa/intervention-rules/1 -> 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        check("patched rule aspect_code", r.json().get("aspect_code") == "PROC", r.text[:200])

    r = client.patch("/api/qa/alerts/1", headers=auth, json={"status": "acknowledged"})
    check("PATCH /api/qa/alerts/1 -> 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        check("patched alert aspect", r.json().get("aspect") == "Processing Time", r.text[:200])
        check("patched alert aspect_code", r.json().get("aspect_code") == "PROC", r.text[:200])

    print("\n[7] Public feedback submission with college validation")
    payload = {
        "department_id": 1,
        "college": "CCS",
        "student_number": "23-23-002",
        "institutional_email": "b@udm.edu.ph",
        "consent": True,
        "rating": 2,
        "comment": "Please improve turnaround time.",
    }
    r = client.post("/api/feedback", json=payload)
    check("POST /api/feedback -> 200 (valid college)", r.status_code == 200, r.text[:400])

    bad = dict(payload, college="ZZZ", student_number="23-23-003",
               institutional_email="c@udm.edu.ph")
    r = client.post("/api/feedback", json=bad)
    check("POST /api/feedback invalid college -> 4xx",
          400 <= r.status_code < 500, f"{r.status_code} {r.text[:300]}")

    print("\n[8] Dashboard payload sanity")
    r = client.get("/api/qa/dashboard", headers=auth)
    check("GET /api/qa/dashboard -> 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        d = r.json()
        check("dashboard has first_response_at key", "first_response_at" in d, str(list(d))[:300])
        check("dashboard has last_response_at key", "last_response_at" in d, str(list(d))[:300])
        check("dashboard by_day present", "by_day" in d, str(list(d))[:300])

    db.close()
    app.dependency_overrides.clear()

    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASSES)}   FAILED: {len(FAILS)}")
    if FAILS:
        print("\nFailures:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

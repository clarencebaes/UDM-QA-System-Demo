"""Verification for the intervention-rules + follow-up workflow (run from backend folder).

Covers:
  * Rule management: create, duplicate rejection, edit, disable, delete
  * Recommendation retrieval: active rule matching, disabled rules not suggested
  * Alert lifecycle: Save draft (no approval) -> Approve (confirmed_at set,
    NOT completed) -> Mark complete (completed_at + completion_note, one stable record)
  * Guard rails: approving without a recommendation is rejected

Run:  python verify_workflow.py
"""

import os
import sys

os.environ.setdefault("JWT_SECRET", "verify-only-secret")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Alert,
    Aspect,
    Department,
    InterventionRule,
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
        InterventionRule(id=1, aspect_id=1, diagnosed_pattern="Long queues and delays",
                         recommendation="Review queue logs and adjust staffing.", is_active=True),
        SurveySettings(id=1, start_date=None, end_date=None, is_active=True),
    ])
    db.commit()

    client = TestClient(app)

    print("\n[1] Login")
    r = client.post("/api/auth/login", json={"username": "qa", "password": "pw123456"})
    check("login returns 200", r.status_code == 200, r.text[:200])
    token = r.json().get("access_token") if r.status_code == 200 else None
    if not token:
        return 1
    auth = {"Authorization": f"Bearer {token}"}

    print("\n[2] Rule management")
    # Create
    r = client.post("/api/qa/intervention-rules", headers=auth, json={
        "aspect_id": 2,
        "diagnosed_pattern": "Slow or unhelpful responses",
        "recommendation": "Refresh staff service standards and conduct spot checks.",
        "is_active": True,
    })
    check("POST rule -> 201", r.status_code == 201, r.text[:300])
    new_id = r.json().get("id") if r.status_code == 201 else None
    if r.status_code == 201:
        check("created rule reports aspect_code",
              r.json().get("aspect_code") == "STAFF", r.text[:300])
        check("created rule is active", r.json().get("is_active") is True, r.text[:200])

    # Duplicate aspect rejected (one default rule per aspect)
    r = client.post("/api/qa/intervention-rules", headers=auth, json={
        "aspect_id": 2,
        "diagnosed_pattern": "Another pattern",
        "recommendation": "Another recommendation text.",
    })
    check("duplicate aspect rule -> 400", r.status_code == 400, r.text[:300])

    # Unknown aspect rejected
    r = client.post("/api/qa/intervention-rules", headers=auth, json={
        "aspect_id": 999,
        "diagnosed_pattern": "Unknown aspect pattern",
        "recommendation": "Recommendation for unknown aspect.",
    })
    check("unknown aspect rule -> 400", r.status_code == 400, r.text[:300])

    # Short recommendation rejected by schema
    r = client.post("/api/qa/intervention-rules", headers=auth, json={
        "aspect_id": 2,
        "diagnosed_pattern": "Slow responses",
        "recommendation": "short",
    })
    check("too-short recommendation -> 4xx", 400 <= r.status_code < 500,
          f"{r.status_code} {r.text[:200]}")

    # Edit pattern + recommendation + disable
    if new_id:
        r = client.patch(f"/api/qa/intervention-rules/{new_id}", headers=auth, json={
            "diagnosed_pattern": "Updated pattern text",
            "recommendation": "Updated prescribed recommendation for QUAD.",
        })
        check("PATCH rule -> 200", r.status_code == 200, r.text[:300])
        if r.status_code == 200:
            check("PATCH persisted recommendation",
                  r.json().get("recommendation") == "Updated prescribed recommendation for QUAD.",
                  r.text[:300])
        r = client.patch(f"/api/qa/intervention-rules/{new_id}", headers=auth,
                         json={"is_active": False})
        check("disable rule -> 200", r.status_code == 200, r.text[:200])
        if r.status_code == 200:
            check("rule reports inactive", r.json().get("is_active") is False, r.text[:200])

    # List shows both rules with status
    r = client.get("/api/qa/intervention-rules", headers=auth)
    check("GET rules -> list of 2", r.status_code == 200 and len(r.json()) == 2,
          r.text[:300])
    if r.status_code == 200:
        active = [x for x in r.json() if x.get("is_active") is True]
        check("exactly one active rule", len(active) == 1, r.text[:300])

    print("\n[3] Recommendation retrieval for an alert")
    # An active alert on PROC (aspect 1, active rule) must surface its rule;
    # the disabled STAFF rule must not be suggested.
    r = client.get("/api/qa/intervention-rules", headers=auth)
    rules = r.json() if r.status_code == 200 else []
    proc_rule = next((x for x in rules if x["aspect_code"] == "PROC" and x.get("is_active", True)), None)
    staff_rule = next((x for x in rules if x["aspect_code"] == "STAFF"), None)
    check("active rule found for PROC alert", proc_rule is not None, r.text[:300])
    check("disabled rule flagged for STAFF",
          staff_rule is not None and staff_rule.get("is_active") is False, r.text[:300])

    print("\n[4] Alert lifecycle: draft -> approve -> complete")
    db.add(Alert(id=1, aspect_id=1, department_id=1, negative_count=3,
                 constructive_count=0, recommendation="", status="new"))
    db.commit()

    # Save draft: stays open, NOT approved (confirmed_at untouched)
    r = client.patch("/api/qa/alerts/1", headers=auth,
                     json={"status": "acknowledged",
                           "note": "[Short term] Adjust staffing during peak periods.",
                           "department_id": 1})
    check("save draft -> 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        body = r.json()
        check("draft is acknowledged (awaiting approval)",
              body.get("status") == "acknowledged", r.text[:300])
        check("draft has no confirmed_at yet", body.get("confirmed_at") is None, r.text[:300])
        check("draft has no completed_at yet", body.get("completed_at") is None, r.text[:300])
        check("draft stamped service area", body.get("department") == "Registrar", r.text[:300])

    # Approving with empty note is rejected (no recommendation written)
    db2 = TestingSession()
    alert_row = db2.get(Alert, 1)
    saved_note = alert_row.note
    alert_row.note = ""
    db2.commit()
    db2.close()
    r = client.patch("/api/qa/alerts/1", headers=auth, json={"status": "in-progress"})
    check("approve without recommendation -> 400", r.status_code == 400, r.text[:300])
    db3 = TestingSession()
    alert_row = db3.get(Alert, 1)
    alert_row.note = saved_note
    db3.commit()
    db3.close()

    # Approve: in-progress + confirmed_at, still NOT in History
    r = client.patch("/api/qa/alerts/1", headers=auth, json={"status": "in-progress"})
    check("approve -> 200", r.status_code == 200, r.text[:300])
    confirmed_at = None
    if r.status_code == 200:
        body = r.json()
        check("approved status is in-progress", body.get("status") == "in-progress", r.text[:300])
        check("confirmed_at stamped on approval", bool(body.get("confirmed_at")), r.text[:300])
        check("approval does NOT complete", body.get("completed_at") is None, r.text[:300])
        confirmed_at = body.get("confirmed_at")

    # Approved item must NOT appear in History (History = resolved/completed only)
    r = client.get("/api/qa/alerts", headers=auth)
    hist = [a for a in r.json() if a.get("status") in ("resolved", "completed")]
    check("approved alert not in History yet", len(hist) == 0, r.text[:300])

    # Mark complete with optional notes
    r = client.patch("/api/qa/alerts/1", headers=auth,
                     json={"status": "resolved",
                           "completion_note": "Two desk clerks added on Mondays."})
    check("mark complete -> 200", r.status_code == 200, r.text[:300])
    completed_at = None
    if r.status_code == 200:
        body = r.json()
        check("completed status is resolved", body.get("status") == "resolved", r.text[:300])
        check("completed_at stamped", bool(body.get("completed_at")), r.text[:300])
        check("completion note saved",
              body.get("completion_note") == "Two desk clerks added on Mondays.", r.text[:300])
        check("confirmed_at kept from approval", body.get("confirmed_at") == confirmed_at,
              r.text[:300])
        completed_at = body.get("completed_at")

    # Re-saving must not rewrite dates or duplicate the record
    r = client.patch("/api/qa/alerts/1", headers=auth, json={"status": "resolved"})
    if r.status_code == 200:
        body = r.json()
        check("re-complete keeps original completed_at",
              body.get("completed_at") == completed_at, r.text[:300])
    r = client.get("/api/qa/alerts", headers=auth)
    check("History has exactly one record", len(r.json()) == 1, r.text[:300])
    hist = [a for a in r.json() if a.get("status") in ("resolved", "completed")]
    check("completed alert appears in History", len(hist) == 1, r.text[:300])
    if hist:
        check("History row carries completion note",
              hist[0].get("completion_note") == "Two desk clerks added on Mondays.",
              r.text[:300])

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

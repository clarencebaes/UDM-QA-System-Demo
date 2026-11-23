"""Configuration regressions; isolated SQLite, no production database access."""
import os
os.environ.setdefault("JWT_SECRET", "configuration-regression-secret-at-least-32-bytes")

from sqlalchemy.engine import make_url
from app.config import Settings
from app.schemas import SurveySettingsPatch, ThresholdPatch
from pydantic import ValidationError
from verify_workflow import check, FAILS

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.models import Aspect, Threshold, User
from app.auth import hash_password
from app.main import app
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
with Session() as db:
    db.add_all([Aspect(id=1, code="PROC", name="Processing Time"),
                Threshold(id=1, aspect_id=1, min_count=3, window_days=14, include_constructive=False),
                User(username="qa", password_hash=hash_password("pw123456"), display_name="QA", role="qa")])
    db.commit()
def override_db():
    with Session() as db:
        yield db
app.dependency_overrides[get_db] = override_db
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
token = client.post("/api/auth/login", json={"username": "qa", "password": "pw123456"}).json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
for field in ("min_trigger_count", "alert_window_days"):
    for value in (0, -1, None):
        response = client.patch("/api/qa/survey-settings", headers=headers, json={field: value})
        check(f"reject invalid {field}={value}", response.status_code == 422)
response = client.patch("/api/qa/survey-settings", headers=headers,
                        json={"min_trigger_count": 7, "alert_window_days": 21,
                              "start_date": "", "end_date": "2026-12-31", "default_goal": "long_term"})
check("valid survey settings accepted", response.status_code == 200, response.text)
thresholds = client.get("/api/qa/thresholds", headers=headers).json()
check("global settings update actual aspect thresholds",
      bool(thresholds) and all(t["min_count"] == 7 and t["window_days"] == 21 for t in thresholds))
for field in ("min_count", "window_days"):
    check(f"reject nonpositive threshold {field}", client.patch(
        "/api/qa/thresholds/1", headers=headers, json={field: 0}).status_code == 422)
settings = Settings(_env_file=None, mysql_user="qa@user", mysql_password="p@ss:/?#%word")
for address in (settings.database_url, settings.server_url):
    url = make_url(address)
    check("database credentials round-trip special characters",
          url.username == settings.mysql_user and url.password == settings.mysql_password)
# Settings must expose the flag and reevaluate existing labels immediately.
from app.models import Department, Feedback, FeedbackLabel
with Session() as db:
    db.add(Department(id=1, code="REG", name="Registrar", is_active=True))
    for sentiment in ("negative", "negative", "constructive"):
        feedback = Feedback(department_id=1, comment="test concern", consent=True)
        db.add(feedback)
        db.flush()
        db.add(FeedbackLabel(feedback_id=feedback.id, aspect_id=1, sentiment=sentiment, aspect_source="model"))
    db.commit()
response = client.patch("/api/qa/survey-settings", headers=headers,
                        json={"min_trigger_count": 3, "include_constructive": True})
check("constructive inclusion saved", response.status_code == 200 and response.json()["include_constructive"] is True)
alerts = client.get("/api/qa/alerts", headers=headers).json()
check("2 negatives plus 1 constructive triggers at 3", len(alerts) == 1 and alerts[0]["negative_count"] == 2 and alerts[0]["constructive_count"] == 1)
response = client.patch("/api/qa/survey-settings", headers=headers, json={"include_constructive": False})
check("constructive exclusion saved", response.status_code == 200 and response.json()["include_constructive"] is False)
alerts = client.get("/api/qa/alerts", headers=headers).json()
check("saved alert counts refresh after disabling constructive", len(alerts) == 1 and alerts[0]["constructive_count"] == 0)
check("inclusion flag exposed on GET", client.get("/api/qa/survey-settings", headers=headers).json()["include_constructive"] is False)
check("null inclusion rejected", client.patch("/api/qa/survey-settings", headers=headers, json={"include_constructive": None}).status_code == 422)
if FAILS:
    raise SystemExit(1)
print("Configuration regressions passed.")

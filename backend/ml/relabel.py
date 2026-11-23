"""Re-run the ML classification over stored feedback.

The .joblib models evolve as the training seed grows. Feedback already in the
database keeps the labels it received under the OLD model, so rows classified
before a retrain still show the old aspect until this script is run:

    cd backend
    .venv\\Scripts\\activate
    python -m ml.relabel

Rules (same as the live classify pipeline):
- Student-picked aspects (Feedback.aspect_id set by the student) are kept;
  only model-predicted aspects and model sentiment are refreshed.
- Feedback without a written comment gets NO label at all (a rating-only
  submission is not a comment and must never feed alerts); stale labels on
  such rows are deleted.
- The constructive suggestion rule (sana / "would help" ...) applies.
- After relabeling, open alerts are re-evaluated against the corrected
  counts; an alert that no longer breaches its threshold is removed so
  Interventions never shows a stale "+N constructive".
"""

import pymysql

from app.config import settings
from app.database import SessionLocal, init_engine
from app.models import Alert, Feedback
from app.services.alerts import evaluate_thresholds
from app.services.classify import classify_feedback, load_models

OPEN_STATUSES = ("new", "acknowledged", "in-progress")


def _preflight() -> None:
    """Fail fast with a clear message when MySQL is not answering.

    A hung XAMPP mysqld accepts TCP connections but never replies, which would
    otherwise stall this script forever inside SQLAlchemy.
    """
    try:
        conn = pymysql.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            connect_timeout=5,
            read_timeout=10,
            write_timeout=10,
        )
        conn.close()
    except Exception as exc:  # noqa: BLE001 - report any failure verbatim
        raise SystemExit(
            f"MySQL at {settings.mysql_host}:{settings.mysql_port} did not respond "
            f"({exc}).\nStart/restart MySQL (XAMPP Control Panel -> Start on MySQL) "
            "and run this script again."
        )


def main() -> None:
    _preflight()
    init_engine()
    load_models()
    db = SessionLocal()
    try:
        items = db.query(Feedback).all()
        if not items:
            print("No feedback rows found.")
            return
        student_picked = 0
        for item in items:
            if item.aspect_id:
                student_picked += 1
            classify_feedback(db, item)
        db.expire_all()
        model_aspected = sum(
            1
            for i in items
            if i.label is not None and i.label.aspect_source == "model"
        )
        labeled = sum(1 for i in items if i.label is not None and i.label.sentiment)
        unlabeled = len(items) - labeled
        print(
            f"Relabeled {len(items)} feedback rows "
            f"({model_aspected} model aspects, {student_picked} student-picked aspects kept, "
            f"{labeled} with sentiment, {unlabeled} without comment)."
        )

        # ── Repair open alerts against the corrected labels ──
        open_alerts = db.query(Alert).filter(Alert.status.in_(OPEN_STATUSES)).all()
        dropped = 0
        for alert in open_alerts:
            if evaluate_thresholds(db, alert.aspect_id) is None:
                db.delete(alert)
                dropped += 1
        db.commit()
        if open_alerts:
            print(
                f"Refreshed {len(open_alerts)} open alert(s); "
                f"removed {dropped} no longer breaching threshold(s)."
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()

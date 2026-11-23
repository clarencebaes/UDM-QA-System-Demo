"""Lightweight MySQL migrations for existing XAMPP databases.

SQLAlchemy `create_all` does not alter tables that already exist, so older
local databases may miss columns added after the first install.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.colleges import COLLEGE_CODES
from app.service_areas import SERVICE_AREAS, SERVICE_AREA_CODES


def _column_names(insp, table: str) -> set[str]:
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def apply_migrations(engine: Engine) -> None:
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, additions in {
            "alerts": {"service_area_scope": "BOOLEAN NOT NULL DEFAULT 0"},
            "users": {"is_active": "BOOLEAN NOT NULL DEFAULT 1", "token_version": "INT NOT NULL DEFAULT 0", "failed_logins": "INT NOT NULL DEFAULT 0", "locked_until": "DATETIME NULL"},
            "feedback_labels": {"polarity": "VARCHAR(16) NULL", "is_constructive": "BOOLEAN NOT NULL DEFAULT 0", "analysis_reason": "VARCHAR(64) NULL"},
            "feedback": {"detected_language": "VARCHAR(16) NULL", "analysis_version": "VARCHAR(64) NULL", "submission_id": "INT NULL", "cycle_id": "INT NULL", "student_status": "VARCHAR(16) NULL"},
            "survey_settings": {"active_cycle_id": "INT NULL", "min_negative_count": "INT NULL", "min_constructive_count": "INT NULL"},
            "survey_cycles": {"start_date": "DATETIME NULL", "end_date": "DATETIME NULL"},
        }.items():
            columns = _column_names(insp, table)
            for name, definition in additions.items():
                if columns and name not in columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
        if engine.dialect.name == "mysql":
            conn.execute(text("ALTER TABLE users MODIFY COLUMN role VARCHAR(32) NOT NULL DEFAULT 'viewer'"))
        # Installation owners remain at the top of the four-role hierarchy.
        conn.execute(text("UPDATE users SET role = 'executive_director', token_version = token_version + 1 WHERE role IN ('super_admin', 'qa')"))
        conn.execute(text("UPDATE users SET role = 'viewer' WHERE role = 'department_head'"))
        conn.execute(text("UPDATE survey_cycles SET start_date=COALESCE(start_date, (SELECT s.start_date FROM survey_settings s WHERE s.active_cycle_id=survey_cycles.id LIMIT 1)), end_date=COALESCE(end_date, (SELECT s.end_date FROM survey_settings s WHERE s.active_cycle_id=survey_cycles.id LIMIT 1))"))
    if engine.dialect.name != "mysql":
        assign_existing_period(engine)
        assign_existing_student_status(engine)
        shorten_default_recommendations(engine)
        return
    with engine.begin() as conn:
        feedback_cols = _column_names(insp, "feedback")
        if feedback_cols and "rating" not in feedback_cols:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN rating INT NULL"))

        if feedback_cols and "rating_1" not in feedback_cols:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN rating_1 INT NULL"))
        if feedback_cols and "rating_2" not in feedback_cols:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN rating_2 INT NULL"))
        if feedback_cols and "rating_3" not in feedback_cols:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN rating_3 INT NULL"))

        alert_cols = _column_names(insp, "alerts")
        if alert_cols and "quad_note" not in alert_cols:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN quad_note TEXT NULL"))
        if alert_cols and "note" not in alert_cols:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN note TEXT NULL"))
        if alert_cols and "diagnosed_pattern" not in alert_cols:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN diagnosed_pattern TEXT NULL"))
        if alert_cols and "constructive_count" not in alert_cols:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN constructive_count INT NOT NULL DEFAULT 0"))

        # Intervention rule enable/disable (QUAD rules management in Settings).
        rule_cols = _column_names(insp, "intervention_rules")
        if rule_cols and "is_active" not in rule_cols:
            conn.execute(
                text("ALTER TABLE intervention_rules ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1")
            )

        # Approval vs completion are separate workflow steps.
        if alert_cols and "confirmed_at" not in alert_cols:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN confirmed_at DATETIME NULL"))
        if alert_cols and "completed_at" not in alert_cols:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN completed_at DATETIME NULL"))
        if alert_cols and "completion_note" not in alert_cols:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN completion_note TEXT NULL"))

        threshold_cols = _column_names(insp, "thresholds")
        if threshold_cols and "include_constructive" not in threshold_cols:
            conn.execute(
                text("ALTER TABLE thresholds ADD COLUMN include_constructive TINYINT(1) NOT NULL DEFAULT 1")
            )

        if alert_cols:
            conn.execute(
                text(
                    "ALTER TABLE alerts MODIFY COLUMN status "
                    "ENUM('new', 'acknowledged', 'in-progress', 'resolved', 'done') "
                    "NOT NULL DEFAULT 'new'"
                )
            )
            conn.execute(text("UPDATE alerts SET status = 'resolved' WHERE status = 'done'"))
            conn.execute(
                text(
                    "ALTER TABLE alerts MODIFY COLUMN status "
                    "ENUM('new', 'acknowledged', 'in-progress', 'resolved') "
                    "NOT NULL DEFAULT 'new'"
                )
            )

        label_cols = _column_names(insp, "feedback_labels")
        if label_cols:
            conn.execute(
                text(
                    "ALTER TABLE feedback_labels MODIFY COLUMN sentiment "
                    "ENUM('positive', 'negative', 'neutral', 'constructive') NOT NULL"
                )
            )

        tables = set(insp.get_table_names())
        if "respondents" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE respondents (
                      id INT AUTO_INCREMENT PRIMARY KEY,
                      student_number VARCHAR(32) NOT NULL UNIQUE,
                      institutional_email VARCHAR(160) NOT NULL UNIQUE,
                      college VARCHAR(16) NOT NULL,
                      created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB
                    """
                )
            )
            tables.add("respondents")

        if "college_headcounts" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE college_headcounts (
                      id INT AUTO_INCREMENT PRIMARY KEY,
                      college VARCHAR(16) NOT NULL UNIQUE,
                      headcount INT NOT NULL DEFAULT 0,
                      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB
                    """
                )
            )
            tables.add("college_headcounts")

        feedback_cols = _column_names(inspect(engine), "feedback")
        if feedback_cols and "respondent_id" not in feedback_cols:
            conn.execute(text("ALTER TABLE feedback ADD COLUMN respondent_id INT NULL"))
            conn.execute(
                text(
                    "ALTER TABLE feedback ADD CONSTRAINT fk_feedback_respondent "
                    "FOREIGN KEY (respondent_id) REFERENCES respondents(id)"
                )
            )
            conn.execute(text("CREATE INDEX idx_feedback_respondent ON feedback (respondent_id)"))

        for code in SERVICE_AREA_CODES:
            conn.execute(
                text(
                    "INSERT IGNORE INTO departments (code, name, description, is_active) "
                    "VALUES (:code, :name, :description, 1)"
                ),
                {
                    "code": code,
                    "name": next(item["name"] for item in SERVICE_AREAS if item["code"] == code),
                    "description": next(item.get("description", "") for item in SERVICE_AREAS if item["code"] == code),
                },
            )

        conn.execute(
            text(
                "UPDATE departments SET is_active = 0 "
                "WHERE code NOT IN ('" + "', '".join(SERVICE_AREA_CODES) + "')"
            )
        )

        for code in COLLEGE_CODES:
            conn.execute(
                text(
                    "INSERT IGNORE INTO college_headcounts (college, headcount, updated_at) "
                    "VALUES (:college, 0, NOW())"
                ),
                {"college": code},
            )
        conn.execute(
            text(
                "UPDATE college_headcounts SET updated_at = NOW() "
                "WHERE updated_at IS NULL OR CAST(updated_at AS CHAR) LIKE '0000%'"
            )
        )

        # Create survey_settings table if it doesn't exist
        if "survey_settings" not in tables:
            conn.execute(
                text(
                    """
                    CREATE TABLE survey_settings (
                      id INT AUTO_INCREMENT PRIMARY KEY,
                      start_date DATETIME NULL,
                      end_date DATETIME NULL,
                      is_active TINYINT(1) NOT NULL DEFAULT 1,
                      min_trigger_count INT NOT NULL DEFAULT 3,
                      alert_window_days INT NOT NULL DEFAULT 14,
                      default_goal VARCHAR(32) NOT NULL DEFAULT 'short_term',
                      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB
                    """
                )
            )
            # Insert default settings
            conn.execute(
                text(
                    """
                    INSERT INTO survey_settings (start_date, end_date, is_active, min_trigger_count, alert_window_days, default_goal)
                    VALUES (NULL, NULL, 1, 3, 14, 'short_term')
                    """
                )
            )

    # Add constraints/indexes to migrated tables (create_all only handles new tables).
    fresh = inspect(engine)
    with engine.begin() as conn:
        for table, column, target, name in (
            ("feedback", "submission_id", "survey_submissions", "fk_feedback_submission"),
            ("feedback", "cycle_id", "survey_cycles", "fk_feedback_cycle"),
            ("survey_settings", "active_cycle_id", "survey_cycles", "fk_settings_cycle"),
        ):
            if not any(column in fk["constrained_columns"] for fk in fresh.get_foreign_keys(table)):
                conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({column}) REFERENCES {target}(id)"))

    # Additive read index for newest-first pages and alert-window scans.
    # Metadata.create_all does not add indexes to pre-existing tables.
    from app.models import Feedback
    for index in Feedback.__table__.indexes:
        if index.name in {"idx_feedback_created", "ix_feedback_submission_id", "ix_feedback_cycle_id"}:
            index.create(bind=engine, checkfirst=True)
    assign_existing_period(engine)
    assign_existing_student_status(engine)
    shorten_default_recommendations(engine)


def assign_existing_period(engine):
    """User-confirmed historical period, without inventing receipts or student status."""
    from datetime import datetime
    from app.models import SurveyCycle, AuditEvent
    with engine.begin() as conn:
        pending = conn.execute(text("SELECT COUNT(*) FROM feedback WHERE cycle_id IS NULL")).scalar()
        if not pending:
            return
        cycle = conn.execute(text("SELECT id FROM survey_cycles WHERE academic_year='2026-2027' AND semester='1st'")).scalar()
        if not cycle:
            result = conn.execute(SurveyCycle.__table__.insert().values(academic_year="2026-2027", semester="1st", created_at=datetime.utcnow()))
            cycle = result.inserted_primary_key[0]
        # Existing receipt assignments always take precedence over the historical default.
        conn.execute(text("UPDATE feedback SET cycle_id=COALESCE((SELECT s.cycle_id FROM survey_submissions s WHERE s.id=feedback.submission_id), :cycle) WHERE cycle_id IS NULL"), {"cycle": cycle})
        conn.execute(AuditEvent.__table__.insert().values(actor="system migration", action="historical_period_assigned", target="feedback", detail=f"Assigned {pending} unscoped evaluations; historical default confirmed as 2026-2027 1st semester. Existing receipt periods preserved.", created_at=datetime.utcnow()))


def assign_existing_student_status(engine):
    """Apply the project owner's confirmed classification only to pre-status records."""
    from datetime import datetime
    from app.models import AuditEvent
    with engine.begin() as conn:
        pending = conn.execute(text("SELECT COUNT(*) FROM feedback WHERE submission_id IS NULL AND student_status IS NULL")).scalar()
        if pending:
            conn.execute(text("UPDATE feedback SET student_status='regular' WHERE submission_id IS NULL AND student_status IS NULL"))
            conn.execute(AuditEvent.__table__.insert().values(actor="system migration", action="historical_student_status_assigned", target="feedback", detail=f"Assigned Regular to {pending} earlier evaluation records, as confirmed by the project owner. Recorded semester submission statuses were preserved.", created_at=datetime.utcnow()))


def shorten_default_recommendations(engine):
    from datetime import datetime
    from app.models import AuditEvent
    from app.intervention_templates import LEGACY_RECOMMENDATIONS, CONCISE_RECOMMENDATIONS
    with engine.begin() as conn:
        rows=conn.execute(text("SELECT r.id,a.code,r.recommendation FROM intervention_rules r JOIN aspects a ON a.id=r.aspect_id")).all()
        changed=0
        for row in rows:
            if row.recommendation == LEGACY_RECOMMENDATIONS.get(row.code) and row.code in CONCISE_RECOMMENDATIONS:
                conn.execute(text("UPDATE intervention_rules SET recommendation=:recommendation WHERE id=:id"),{"recommendation":CONCISE_RECOMMENDATIONS[row.code],"id":row.id})
                changed+=1
        if changed:
            conn.execute(AuditEvent.__table__.insert().values(actor="system migration",action="default_recommendations_shortened",target="intervention_rules",detail=f"Reworded {changed} unchanged default suggestions in plain language. Custom rules and saved interventions were preserved.",created_at=datetime.utcnow()))

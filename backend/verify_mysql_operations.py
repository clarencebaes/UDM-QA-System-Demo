"""Opt-in tests against a disposable localhost-only database on port 3307.
Run only after initializing the dedicated synthetic server described in docs/quad-rollout.md.
"""
import importlib.util
import subprocess
import sys
import types
import unittest
from pathlib import Path
from sqlalchemy import create_engine, text, event, inspect
from app.database import Base
from app.models import User, Feedback
from app.migrations import apply_migrations
from verify_operations import OperationsTests
from verify_service_area_revision import ServiceAreaRevisionTests
from verify_polarity_v4 import AnalysisIntegrationTests

ROOT="mysql+pymysql://root:SyntheticDbOnly123@127.0.0.1:3307/"

class MariaDBOperationsTests(OperationsTests):
    def make_engine(self):
        engine=create_engine(ROOT+"udm_quad_qa_regressions")
        @event.listens_for(engine,"connect")
        def strict(connection,_):
            with connection.cursor() as c:c.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ONLY_FULL_GROUP_BY,NO_ENGINE_SUBSTITUTION'")
        Base.metadata.drop_all(engine)
        return engine

class MariaDBServiceAreaRevisionTests(ServiceAreaRevisionTests):
    make_engine = MariaDBOperationsTests.make_engine

class MariaDBAnalysisTests(AnalysisIntegrationTests):
    make_engine = MariaDBOperationsTests.make_engine

    def test_neutral_survives_repeated_schema_migration(self):
        from app.models import FeedbackLabel
        with self.Session() as db:
            row=Feedback(department_id=1,comment="I visited the office.",consent=True)
            db.add(row);db.flush()
            db.add(FeedbackLabel(feedback_id=row.id,aspect_id=1,sentiment="neutral",polarity="neutral"));db.commit()
        apply_migrations(self.engine);apply_migrations(self.engine)
        with self.Session() as db:
            self.assertEqual(db.query(FeedbackLabel).one().sentiment,"neutral")
            self.assertEqual(db.query(Feedback).one().comment,"I visited the office.")

class MigrationTests(unittest.TestCase):
    def test_old_schema_migrates_twice_without_losing_feedback(self):
        engine=create_engine(ROOT+"udm_quad_qa_migration")
        # Snapshot the repository's pre-change model for a real old-schema migration.
        source=subprocess.check_output(["git","show","cce05bed74db3b199c93c19b12869d4bd7f39ece:backend/app/models.py"],text=True,encoding="utf-8")
        source=source.replace("from app.database import Base","from sqlalchemy.orm import declarative_base\nBase=declarative_base()")
        module=types.ModuleType("legacy_models");sys.modules[module.__name__]=module
        exec(compile(source,"legacy_models.py","exec"),module.__dict__)
        module.Base.metadata.create_all(engine)
        with engine.begin() as c:
            c.execute(text("INSERT INTO users (username,password_hash,display_name,role,created_at) VALUES ('existing_admin','synthetic-hash','Existing admin','qa',NOW())"))
            c.execute(text("INSERT INTO departments (code,name,description,is_active) VALUES ('REG','Registrar','',1)"))
            c.execute(text("INSERT INTO feedback (department_id,comment,consent,created_at) VALUES (1,'Preserve original feedback',1,NOW())"))
        Base.metadata.create_all(engine)
        apply_migrations(engine);apply_migrations(engine)
        with engine.connect() as c:
            self.assertEqual(c.execute(text("SELECT role FROM users WHERE username='existing_admin'")).scalar(),"super_admin")
            self.assertEqual(c.execute(text("SELECT comment FROM feedback WHERE id=1")).scalar(),"Preserve original feedback")
            self.assertEqual(c.execute(text("SELECT student_status FROM feedback WHERE id=1")).scalar(),"regular")
        self.assertTrue(any("submission_id" in fk["constrained_columns"] for fk in inspect(engine).get_foreign_keys("feedback")))
        self.assertIn("is_active",{col["name"] for col in inspect(engine).get_columns("users")})
        engine.dispose()

if __name__=="__main__":
    # Only these fixed, explicitly synthetic databases may be created/dropped.
    admin=create_engine(ROOT)
    with admin.begin() as c:
        for name in ("udm_quad_qa_regressions","udm_quad_qa_migration"):
            c.execute(text(f"DROP DATABASE IF EXISTS {name}"))
            c.execute(text(f"CREATE DATABASE {name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    admin.dispose()
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(MigrationTests), unittest.defaultTestLoader.loadTestsFromTestCase(MariaDBOperationsTests), unittest.defaultTestLoader.loadTestsFromTestCase(MariaDBServiceAreaRevisionTests)])
    suite.addTests(MariaDBAnalysisTests(name) for name in ("test_refresh_preserves_answers_and_actions_and_is_idempotent","test_negative_suggestion_is_one_comment_with_two_trigger_counts","test_neutral_survives_repeated_schema_migration"))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())

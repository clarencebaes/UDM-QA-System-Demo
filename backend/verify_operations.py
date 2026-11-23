"""Integration coverage for roles, cycles, receipts, reports and recovery (synthetic SQLite)."""
import json
import unittest
from uuid import uuid4
from unittest.mock import patch
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.auth import hash_password, create_token
from app.models import (User, Department, College, Respondent, SurveySettings, SurveyCycle, SurveySubmission,
    Feedback, AuditEvent, StudentConcern, Aspect, Alert, FeedbackLabel, InterventionRule)
from app.recovery import cipher

PASSWORD = "Synthetic-password-123"

class OperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.password_hash = hash_password(PASSWORD)

    def make_engine(self):
        engine = create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)
        @event.listens_for(engine,"connect")
        def fk(connection, _): connection.execute("PRAGMA foreign_keys=ON")
        return engine

    def setUp(self):
        self.engine=self.make_engine()
        Base.metadata.create_all(self.engine)
        self.Session=sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add_all([User(username=r,display_name=r,role=r,password_hash=self.password_hash) for r in ("super_admin","executive_director","admin","assistant","viewer")])
            db.add_all([Department(id=1,code="REG",name="Registrar",is_active=True), Department(id=2,code="LIB",name="Library",is_active=True), College(code="CAS",name="Arts and Sciences"), College(code="CCS",name="Computer Studies"), SurveyCycle(id=1,academic_year="2026-2027",semester="1st"),SurveyCycle(id=2,academic_year="2026-2027",semester="2nd"), Aspect(id=1,code="processing_time",name="Processing Time",description="")])
            db.commit()
            db.add(SurveySettings(active_cycle_id=1,is_active=True,start_date=datetime.utcnow()-timedelta(days=1),end_date=datetime.utcnow()+timedelta(days=30)))
            db.add(InterventionRule(aspect_id=1,diagnosed_pattern="Slow service",recommendation="Review processing delays with the office."))
            db.commit()
        def override():
            with self.Session() as db: yield db
        app.dependency_overrides[get_db]=override
        self.client=TestClient(app)
        self.mock=patch("app.main.classify_feedback",return_value=None);self.mock.start()

    def tearDown(self):
        self.mock.stop();self.client.close();app.dependency_overrides.clear();self.engine.dispose()

    def headers(self,role="super_admin"):
        with self.Session() as db:
            u=db.query(User).filter_by(username=role).one()
            return {"Authorization":"Bearer "+create_token(u.username,u.role,u.token_version)}

    def test_delete_user_preserves_audit_and_revokes_access(self):
        with self.Session() as db:
            target = db.query(User).filter_by(username="viewer").one().id
        old_headers = self.headers("viewer")
        response = self.client.delete(f"/api/qa/users/{target}", headers=self.headers("admin"))
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/qa/me", headers=old_headers).status_code, 401)
        with self.Session() as db:
            self.assertIsNone(db.get(User, target))
            self.assertTrue(db.query(AuditEvent).filter_by(action="delete", target=f"users:{target}").first())

    def test_delete_user_enforces_hierarchy_and_self_protection(self):
        with self.Session() as db:
            ids = {u.username:u.id for u in db.query(User)}
        for role in ("assistant", "viewer", "admin"):
            self.assertEqual(self.client.delete(f"/api/qa/users/{ids['executive_director']}", headers=self.headers(role)).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/qa/users/{ids['executive_director']}", headers=self.headers("executive_director")).status_code, 409)
        self.assertEqual(self.client.delete(f"/api/qa/users/{ids['admin']}", headers=self.headers("executive_director")).status_code, 204)

    def test_delete_last_active_director_is_blocked(self):
        with self.Session() as db:
            target = db.query(User).filter_by(username="executive_director").one().id
            db.query(User).filter_by(username="super_admin").update({"is_active":False})
            db.commit()
        self.assertEqual(self.client.delete(f"/api/qa/users/{target}", headers=self.headers("admin")).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/qa/users/{target}", headers=self.headers("executive_director")).status_code, 409)

    def test_comment_categories_reconcile_across_pages_and_combine_without_duplicates(self):
        with self.Session() as db:
            for text, category in (("Good service", "positive"), ("Slow service", "negative"),
                                   ("Please add chairs", "constructive"), ("I visited today", "neutral"),
                                   ("qwerty unknown", None), ("N/A", None), ("none", None), ("", None)):
                row=Feedback(department_id=1,comment=text,consent=True,detected_language="undetermined")
                db.add(row);db.flush()
                if category: db.add(FeedbackLabel(feedback_id=row.id,aspect_id=1,sentiment=category,polarity="negative" if category=="constructive" else category,is_constructive=category=="constructive"))
            db.commit()
        headers=self.headers()
        page=self.client.get("/api/qa/feedback-page",headers=headers).json()
        dash=self.client.get("/api/qa/dashboard",headers=headers).json()
        report=self.client.post("/api/qa/reports",headers=headers,json={}).json()
        self.assertEqual(page["total"],5)
        self.assertEqual(sum(page["counts"][key] for key in ("positive","negative","constructive","neutral","unclassified")),5)
        self.assertEqual(dash["total_comments"],5)
        self.assertEqual(report["comments"],5)
        self.assertEqual(sum(report["sentiment"].values()),5)
        self.assertEqual(sum(report["language_counts"].values()),5)
        combined=self.client.get("/api/qa/feedback-page?sentiment=negative,constructive",headers=headers).json()
        self.assertEqual(combined["total"],2)
        self.assertEqual(len({row["id"] for row in combined["items"]}),2)
        self.assertEqual(self.client.get("/api/qa/feedback-page?sentiment=invalid",headers=headers).status_code,422)

    def test_workspace_uses_current_rules_after_settings_edit_and_disable(self):
        headers=self.headers()
        with self.Session() as db:
            rule_id=db.query(InterventionRule).one().id
        changed="Post clear requirements and help students at the counter."
        response=self.client.patch(f"/api/qa/intervention-rules/{rule_id}",headers=headers,json={"recommendation":changed})
        self.assertEqual(response.status_code,200,response.text)
        workspace=self.client.get("/api/qa/interventions?include_alerts=true",headers=headers).json()
        self.assertEqual(workspace["rules"][0]["recommendation"],changed)
        self.client.patch(f"/api/qa/intervention-rules/{rule_id}",headers=headers,json={"is_active":False})
        workspace=self.client.get("/api/qa/interventions?include_alerts=true",headers=headers).json()
        self.assertFalse(workspace["rules"][0]["is_active"])

    def body(self,cycle=1,college="CAS",number="26-01-001",email="student@udm.edu.ph"):
        return dict(cycle_id=cycle,student_status="regular",request_key=str(uuid4()),consent_version="2026-10-29",items=[dict(department_id=d,student_number=number,institutional_email=email,college=college,consent=True,rating_1=4,rating_2=4,rating_3=5,comment="") for d in (1,2)])

    def test_opening_requires_both_schedule_dates(self):
        h=self.headers()
        self.client.put("/api/qa/cycles/2/activate",headers=h)
        for body in ({"is_active":True}, {"is_active":True,"start_date":"2026-01-01"}, {"is_active":True,"end_date":"2027-01-01"}):
            result=self.client.patch("/api/qa/survey-settings",headers=h,json=body)
            self.assertEqual(result.status_code,422,result.text)
        self.assertFalse(self.client.get("/api/survey-status").json()["is_active"])
        result=self.client.patch("/api/qa/survey-settings",headers=h,json={"is_active":True,"start_date":"2026-01-01","end_date":"2027-01-01"})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.patch("/api/qa/survey-settings",headers=h,json={"start_date":None}).status_code,422)

    def test_workspace_includes_newly_created_alerts_in_the_same_response(self):
        with self.Session() as db:
            for i in range(3):
                row=Feedback(department_id=1,comment=f"Slow service complaint {i}",consent=True)
                db.add(row);db.flush();db.add(FeedbackLabel(feedback_id=row.id,aspect_id=1,sentiment="negative"))
            db.commit()
        result=self.client.get("/api/qa/interventions?include_alerts=true",headers=self.headers("assistant"))
        self.assertEqual(result.status_code,200,result.text)
        workspace=result.json()
        self.assertEqual(len(workspace["pairs"]),1)
        self.assertIn(workspace["pairs"][0]["alert_id"],{row["id"] for row in workspace["alerts"]})
        denied=self.client.get("/api/qa/interventions?include_alerts=true",headers=self.headers("viewer"))
        self.assertEqual(denied.status_code,403)

    def test_two_semesters_and_schedule_history_drive_report(self):
        h=self.headers()
        self.assertEqual(self.client.post("/api/qa/cycles",headers=h,json={"academic_year":"2027-2028","semester":"Summer"}).status_code,422)
        self.assertEqual(self.client.post("/api/qa/cycles",headers=h,json={"academic_year":"2026-2027","semester":"1st"}).status_code,409)
        self.client.post("/api/submissions",json=self.body())
        result=self.client.patch("/api/qa/survey-settings",headers=h,json={"start_date":"2026-01-01T00:00:00+08:00","end_date":"2026-12-31T23:59:59+08:00"})
        self.assertEqual(result.status_code,200,result.text)
        self.client.put("/api/qa/cycles/2/activate",headers=h)
        self.client.put("/api/qa/cycles/1/activate",headers=h)
        self.client.put("/api/qa/cycles/2/activate",headers=h)
        report=self.client.post("/api/qa/reports",headers=h,json={"cycle_id":1,"start_date":"2099-01-01","end_date":"2099-01-02"})
        self.assertEqual(report.status_code,200,report.text)
        self.assertEqual(report.json()["evaluations"],2)
        self.assertEqual(report.json()["schedule"]["start_date"],"2025-12-31T16:00:00")
        self.assertNotIn("start_date",report.json()["filters"])

    def test_feedback_search_matches_text_area_college_and_email_with_cycle_scope(self):
        self.client.post("/api/submissions",json=self.body())
        with self.Session() as db:
            db.query(Feedback).filter_by(department_id=1).one().comment="Queue assistance is helpful."
            db.commit()
        h=self.headers()
        for query,total in (("Queue assistance",1),("Registrar",1),("CAS",2),("student@udm.edu.ph",2),("%",0)):
            from urllib.parse import urlencode
            response=self.client.get("/api/qa/feedback-page?"+urlencode({"search":query,"comments_only":"false","cycle_id":1}),headers=h)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["total"],total,(query,response.text))
        response=self.client.get("/api/qa/feedback-page?search=Queue&cycle_id=2",headers=h)
        self.assertEqual(response.json()["total"],0)

    def test_historical_period_backfill_preserves_answers_and_blocks_duplicates(self):
        from app.migrations import assign_existing_period
        from sqlalchemy import text
        with self.Session() as db:
            person=Respondent(student_number="26-01-123",institutional_email="historical@udm.edu.ph",college="CAS")
            db.add(person);db.flush()
            db.add(Feedback(respondent_id=person.id,department_id=1,comment="Original answer",rating_1=4,consent=True))
            db.commit()
        assign_existing_period(self.engine);assign_existing_period(self.engine)
        with self.Session() as db:
            row=db.query(Feedback).one()
            self.assertEqual((row.cycle_id,row.comment,row.submission_id),(1,"Original answer",None))
            self.assertEqual(db.query(AuditEvent).filter_by(action="historical_period_assigned").count(),1)
        report=self.client.post("/api/qa/reports",headers=self.headers(),json={"cycle_id":1})
        self.assertEqual(report.status_code,200,report.text)
        self.assertEqual(report.json()["evaluations"],1)
        body=self.body()
        for item in body["items"]:
            item.update(student_number="26-01-123",institutional_email="historical@udm.edu.ph")
        self.assertEqual(self.client.post("/api/submissions",json=body).status_code,409)

    def test_atomic_receipt_duplicate_retry_and_new_semester(self):
        body=self.body();r=self.client.post("/api/submissions",json=body);self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(self.client.post("/api/submissions",json=body).json(),r.json())
        receipt=self.client.post("/api/receipt",json={"token":r.json()["receipt_token"]})
        self.assertEqual(receipt.status_code,200);self.assertEqual(len(receipt.json()["answers"]),2)
        self.assertEqual(receipt.headers["cache-control"],"no-store")
        self.assertEqual(self.client.post("/api/receipt",json={"token":"x"*64}).status_code,404)
        self.assertEqual(self.client.post("/api/submissions",json=self.body()).status_code,409)
        with self.Session() as db: self.assertEqual(db.query(Feedback).count(),2)
        self.assertEqual(self.client.put("/api/qa/cycles/2/activate",headers=self.headers()).status_code,200)
        self.assertFalse(self.client.get("/api/survey-status").json()["is_active"])
        self.client.patch("/api/qa/survey-settings",headers=self.headers(),json={"is_active":True,"start_date":(datetime.utcnow()-timedelta(days=1)).isoformat(),"end_date":(datetime.utcnow()+timedelta(days=30)).isoformat()})
        r2=self.client.post("/api/submissions",json=self.body(cycle=2,college="CCS"));self.assertEqual(r2.status_code,200,r2.text)
        first=self.client.post("/api/receipt",json={"token":r.json()["receipt_token"]}).json()
        self.assertEqual(first["college"],"CAS")
        second=self.client.post("/api/receipt",json={"token":r2.json()["receipt_token"]}).json()
        self.assertEqual(second["college"],"CCS")

    def test_validation_does_not_write_partial_answers(self):
        body=self.body();body["items"][1]["rating_1"]=1
        self.assertEqual(self.client.post("/api/submissions",json=body).status_code,422)
        body=self.body();body["items"].pop()
        self.assertEqual(self.client.post("/api/submissions",json=body).status_code,422)
        body=self.body();body["cycle_id"]=2
        self.assertEqual(self.client.post("/api/submissions",json=body).status_code,409)
        with self.Session() as db:
            self.assertEqual(db.query(Feedback).count(),0);self.assertEqual(db.query(SurveySubmission).count(),0)
        self.assertEqual(self.client.post("/api/feedback/batch",json={"items":self.body()["items"]}).status_code,409)

    def test_role_permissions_and_privilege_escalation(self):
        for role in ("viewer","assistant"):
            self.assertEqual(self.client.patch("/api/qa/survey-settings",headers=self.headers(role),json={"is_active":False}).status_code,403)
            self.assertEqual(self.client.post("/api/qa/backup",headers=self.headers(role)).status_code,403)
            self.assertEqual(self.client.post("/api/qa/cycles",headers=self.headers(role),json={"academic_year":"2027-2028","semester":"1st"}).status_code,403)
        self.assertEqual(self.client.get("/api/qa/feedback-page",headers=self.headers("viewer")).status_code,403)
        payload=dict(username="new_viewer",display_name="New viewer",role="viewer",password=PASSWORD,is_active=True)
        self.assertEqual(self.client.post("/api/qa/users",headers=self.headers("executive_director"),json=payload).status_code,201)
        payload.update(username="bad_promotion",role="executive_director")
        self.assertEqual(self.client.post("/api/qa/users",headers=self.headers("admin"),json=payload).status_code,403)
        self.assertEqual(self.client.get("/api/qa/audit",headers=self.headers("admin")).status_code,200)

    def test_panel_concurrent_submissions_and_duplicate_race(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from concurrent.futures import ThreadPoolExecutor
        with TemporaryDirectory(prefix="quad-parallel-") as temporary:
            engine=create_engine("sqlite:///"+str(Path(temporary)/"parallel.sqlite"),connect_args={"check_same_thread":False,"timeout":30})
            Base.metadata.create_all(engine)
            sessions=sessionmaker(bind=engine)
            with sessions() as db:
                db.add_all([Department(id=1,code="REG",name="Registrar",is_active=True),Department(id=2,code="LIB",name="Library",is_active=True),College(code="CAS",name="Arts and Sciences"),SurveyCycle(id=1,academic_year="2026-2027",semester="1st")]);db.commit()
                db.add(SurveySettings(active_cycle_id=1,is_active=True,start_date=datetime.utcnow()-timedelta(days=1),end_date=datetime.utcnow()+timedelta(days=1)));db.commit()
            def override():
                with sessions() as db: yield db
            previous=app.dependency_overrides[get_db];app.dependency_overrides[get_db]=override
            try:
                # Do not enter TestClient lifespan: production startup owns a real DB.
                def send(body):
                    client=TestClient(app)
                    try: return client.post("/api/submissions",json=body)
                    finally: client.close()
                bodies=[self.body(number=f"26-02-{i:03}",email=f"parallel{i}@udm.edu.ph") for i in range(1,9)]
                with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(send,bodies))
                self.assertTrue(all(r.status_code==200 for r in results),[(r.status_code,r.text) for r in results])
                duplicates=[self.body(number="26-03-001",email="race@udm.edu.ph") for _ in range(8)]
                with ThreadPoolExecutor(max_workers=8) as pool: races=list(pool.map(send,duplicates))
                self.assertEqual(sum(r.status_code==200 for r in races),1,[(r.status_code,r.text) for r in races])
                self.assertTrue(all(r.status_code in {200,409} for r in races))
                with sessions() as db:
                    self.assertEqual(db.query(SurveySubmission).count(),9)
                    self.assertEqual(db.query(Feedback).count(),18)
            finally:
                app.dependency_overrides[get_db]=previous;engine.dispose()

    def test_panel_duplicate_status_requires_browser_capability(self):
        body=self.body()
        saved=self.client.post("/api/submissions",json=body).json()
        identity={"cycle_id":1,"student_number":"26-01-001","institutional_email":"student@udm.edu.ph"}
        status=self.client.post("/api/submissions/status",json=identity)
        self.assertEqual(status.status_code,200,status.text)
        self.assertEqual(status.headers["cache-control"],"no-store")
        self.assertTrue(status.json()["submitted"])
        self.assertFalse(status.json()["receipt_available"])
        self.assertIsNone(status.json()["receipt_token"])
        recovered=self.client.post("/api/submissions/status",json={**identity,"request_key":body["request_key"]}).json()
        self.assertEqual(recovered["receipt_token"],saved["receipt_token"])
        recovered=self.client.post("/api/submissions/status",json={**identity,"token":saved["receipt_token"]}).json()
        self.assertTrue(recovered["receipt_available"])
        wrong=self.client.post("/api/submissions/status",json={**identity,"token":"x"*64}).json()
        self.assertFalse(wrong["receipt_available"])
        self.assertFalse(self.client.post("/api/submissions/status",json={**identity,"cycle_id":2}).json()["submitted"])

    def test_panel_hierarchy_creation_and_director_protection(self):
        for role in ("admin","executive_director"):
            self.assertEqual(self.client.patch("/api/qa/survey-settings",headers=self.headers(role),json={"is_active":False}).status_code,200)
        payload=dict(username="panel_staff",display_name="Panel staff",role="assistant",password=PASSWORD,is_active=False)
        created=self.client.post("/api/qa/users",headers=self.headers("admin"),json=payload)
        self.assertEqual(created.status_code,201,created.text)
        self.assertTrue(created.json()["is_active"])
        payload.update(role="executive_director",username="panel_owner")
        self.assertEqual(self.client.post("/api/qa/users",headers=self.headers("admin"),json=payload).status_code,403)
        listing=self.client.get("/api/qa/users",headers=self.headers()).json()["items"]
        self.assertEqual(listing[0]["role"],"executive_director")
        self.assertEqual(listing[-1]["role"],"viewer")
        director=next(row for row in listing if row["username"]=="executive_director")
        self.assertEqual(self.client.put(f"/api/qa/users/{director['id']}",headers=self.headers("admin"),json={**director,"password":""}).status_code,403)
        self.assertEqual(self.client.post("/api/qa/restore",headers=self.headers("admin"),json={}).status_code,403)

    def test_panel_language_filter_matches_reports_and_counts(self):
        with self.Session() as db:
            for language in ("english","tagalog","taglish",None,"unsupported"):
                db.add(Feedback(department_id=1,comment="Meaningful written feedback",consent=True,detected_language=language,rating_1=4,rating_2=4,rating_3=4))
            db.commit()
        for language,count in (("english",1),("tagalog",1),("taglish",1),("unclassified",2)):
            page=self.client.get("/api/qa/feedback-page",params={"language":language},headers=self.headers()).json()
            report=self.client.post("/api/qa/reports",json={"language":language},headers=self.headers("viewer")).json()
            self.assertEqual(page["total"],count)
            self.assertEqual(page["counts"]["all"],count)
            self.assertEqual(report["comments"],count)
            self.assertEqual(sum(report["language_counts"].values()),count)
        self.assertEqual(self.client.get("/api/qa/feedback-page?language=invalid",headers=self.headers()).status_code,422)

    def test_active_semester_is_returned_with_survey_schedule(self):
        headers=self.headers()
        settings=self.client.get("/api/qa/survey-settings",headers=headers).json()
        self.assertEqual(settings["active_cycle"]["id"],1)
        self.assertEqual(settings["active_cycle"]["semester"],"1st")
        self.assertIn("2026-2027",settings["active_cycle"]["label"])
        self.assertEqual(self.client.put("/api/qa/cycles/2/activate",headers=headers).status_code,200)
        self.assertEqual(self.client.get("/api/qa/survey-settings",headers=headers).json()["active_cycle"]["semester"],"2nd")

    def test_audit_live_search_matches_readable_labels(self):
        with self.Session() as db:
            db.add_all([AuditEvent(actor="synthetic",action="login",target="session"),AuditEvent(actor="synthetic",action="update",target="survey_settings:1"),AuditEvent(actor="synthetic",action="update",target="users:3")]);db.commit()
        for query in ("Signed in","Survey settings","User account #3","Updated"):
            result=self.client.get("/api/qa/audit",params={"search":query},headers=self.headers())
            self.assertEqual(result.status_code,200,result.text)
            self.assertGreater(result.json()["total"],0,query)
            global_result=self.client.get("/api/qa/search",params={"q":query},headers=self.headers())
            self.assertIn("Audit trail",{group["label"] for group in global_result.json()["groups"]})

    def test_staff_and_admin_concern_access_differs(self):
        self.client.post("/api/concerns",json={"student_number":"26-01-111","email":"test@udm.edu.ph","category":"other","message":"Synthetic role separation concern."})
        self.assertEqual(self.client.get("/api/qa/concerns",headers=self.headers("assistant")).status_code,403)
        result=self.client.get("/api/qa/concerns",headers=self.headers("admin"))
        self.assertEqual(result.status_code,200)
        concern_id=result.json()["items"][0]["id"]
        path=f"/api/qa/concerns/{concern_id}"
        self.assertEqual(self.client.patch(path,headers=self.headers("assistant"),json={"status":"reviewing","staff_note":"Reviewing the reported issue."}).status_code,403)
        self.assertEqual(self.client.patch(path,headers=self.headers("admin"),json={"status":"reviewing","staff_note":"Reviewing the reported issue."}).status_code,200)

    def test_revocation_and_self_lockout(self):
        h=self.headers("viewer")
        with self.Session() as db: u=db.query(User).filter_by(username="viewer").one();uid=u.id
        body=dict(username="viewer",display_name="Viewer",role="viewer",password="",is_active=False)
        self.assertEqual(self.client.put(f"/api/qa/users/{uid}",headers=self.headers(),json=body).status_code,200)
        self.assertEqual(self.client.get("/api/qa/me",headers=h).status_code,401)
        with self.Session() as db: uid=db.query(User).filter_by(username="super_admin").one().id
        body.update(username="super_admin",role="super_admin")
        self.assertEqual(self.client.put(f"/api/qa/users/{uid}",headers=self.headers(),json=body).status_code,409)

    def test_login_lockout_and_logout(self):
        for _ in range(5):self.assertEqual(self.client.post("/api/auth/login",json={"username":"viewer","password":"wrong"}).status_code,401)
        self.assertEqual(self.client.post("/api/auth/login",json={"username":"viewer","password":PASSWORD}).status_code,429)
        h=self.headers("assistant")
        self.assertEqual(self.client.post("/api/auth/logout",headers=h).status_code,200)
        self.assertEqual(self.client.get("/api/qa/me",headers=h).status_code,401)

    def test_reports_all_and_selected_colleges_no_identifiers(self):
        self.client.post("/api/submissions",json=self.body())
        self.client.post("/api/submissions",json=self.body(college="CCS",number="26-01-002",email="second@udm.edu.ph"))
        with self.Session() as db:
            f=db.query(Feedback).first();f.comment="Very slow service";db.add(FeedbackLabel(feedback_id=f.id,aspect_id=1,sentiment="negative"));db.commit()
        r=self.client.post("/api/qa/reports",headers=self.headers("viewer"),json={"cycle_id":1});self.assertEqual(r.status_code,200,r.text)
        data=r.json();self.assertEqual(data["respondents"],2);self.assertEqual(data["evaluations"],4);self.assertEqual(len(data["concerns"]),1)
        self.assertNotIn("student@udm.edu.ph",r.text);self.assertNotIn("26-01-001",r.text)
        r=self.client.post("/api/qa/reports",headers=self.headers("viewer"),json={"cycle_id":1,"colleges":["CAS"]})
        self.assertEqual(r.json()["respondents"],1)
        r=self.client.post("/api/qa/reports",headers=self.headers("viewer"),json={"cycle_id":2})
        self.assertEqual(r.json()["evaluations"],0)

    def test_existing_dashboard_and_feedback_obey_cycle_scope(self):
        self.client.post("/api/submissions",json=self.body())
        for route in ("/api/qa/dashboard", "/api/qa/feedback-page"):
            response=self.client.get(route+"?cycle_id=2&comments_only=false",headers=self.headers())
            self.assertEqual(response.status_code,200,response.text)
            data=response.json()
            self.assertEqual(data["total_feedback"] if "total_feedback" in data else data["total"],0)
            response=self.client.get(route+"?cycle_id=1&comments_only=false",headers=self.headers())
            self.assertEqual(response.status_code,200,response.text)
            data=response.json()
            self.assertEqual(data["total_feedback"] if "total_feedback" in data else data["total"],2)
            if "overall_enrolled" in data:self.assertIsNone(data["overall_enrolled"])
        response=self.client.get("/api/qa/feedback-page?answered_from=2030-01-01&comments_only=false",headers=self.headers())
        self.assertEqual(response.json()["total"],0)
        self.assertEqual(self.client.get("/api/qa/dashboard?cycle_id=bad",headers=self.headers()).status_code,422)

    def test_schedule_timezone_and_closed_period(self):
        h=self.headers()
        response=self.client.patch("/api/qa/survey-settings",headers=h,json={"start_date":"2030-01-01T00:00:00+08:00","end_date":"2030-01-31T23:59:59+08:00","is_active":True})
        self.assertEqual(response.status_code,200,response.text)
        with self.Session() as db:self.assertEqual(db.query(SurveySettings).one().start_date,datetime(2029,12,31,16))
        self.assertFalse(self.client.get("/api/survey-status").json()["is_active"])
        self.assertEqual(self.client.post("/api/submissions",json=self.body()).status_code,403)
        bad=self.client.patch("/api/qa/survey-settings",headers=h,json={"end_date":"2029-01-01T23:59:59+08:00"})
        self.assertEqual(bad.status_code,422)

    def test_concern_inbox_and_audit(self):
        body=dict(student_number="26-01-001",email="student@udm.edu.ph",category="submission",message="I could not complete the submission.")
        r=self.client.post("/api/concerns",json=body);self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(self.client.get("/api/qa/concerns").status_code,401)
        data=self.client.get("/api/qa/concerns",headers=self.headers("admin")).json();self.assertEqual(data["total"],1)
        cid=data["items"][0]["id"]
        r=self.client.patch(f"/api/qa/concerns/{cid}",headers=self.headers("admin"),json={"status":"reviewing","staff_note":"Identity verification requested."});self.assertEqual(r.status_code,200,r.text)
        events=self.client.get("/api/qa/audit",headers=self.headers()).json()["items"]
        self.assertTrue(any(e["action"]=="update" and "student_concerns" in e["target"] for e in events))
        self.assertNotIn(PASSWORD,json.dumps(events))

    def test_approval_and_completion_require_authorized_roles_and_evidence(self):
        with self.Session() as db:
            db.add(Alert(id=1,aspect_id=1,negative_count=4,recommendation="Review delays",status="new"));db.commit()
        path="/api/qa/alerts/1"
        self.assertEqual(self.client.patch(path,headers=self.headers("assistant"),json={"note":"Review queue processing and follow up."}).status_code,403)
        self.assertEqual(self.client.patch(path,headers=self.headers("admin"),json={"note":"Review queue processing and follow up."}).status_code,200)
        self.assertEqual(self.client.patch(path,headers=self.headers("assistant"),json={"status":"in-progress"}).status_code,403)
        self.assertEqual(self.client.patch(path,headers=self.headers("admin"),json={"status":"in-progress"}).status_code,403)
        self.assertEqual(self.client.patch(path,headers=self.headers("admin"),json={"status":"resolved","completion_note":"Action performed."}).status_code,409)
        self.assertEqual(self.client.patch(path,headers=self.headers("executive_director"),json={"status":"in-progress"}).status_code,200)
        self.assertEqual(self.client.patch(path,headers=self.headers("admin"),json={"status":"resolved"}).status_code,422)
        self.assertEqual(self.client.patch(path,headers=self.headers("admin"),json={"status":"resolved","completion_note":"Queue process reviewed with staff."}).status_code,200)
        self.assertEqual(self.client.patch(path,headers=self.headers(),json={"status":"in-progress"}).status_code,409)

    def test_concern_status_filters_and_open_without_remarks(self):
        for index in range(3):
            result=self.client.post("/api/concerns",json={"student_number":f"26-01-00{index}","email":f"case{index}@udm.edu.ph","category":"submission","message":"Synthetic concern for reviewing status filters."})
            self.assertEqual(result.status_code,201,result.text)
        h=self.headers("admin")
        items=self.client.get("/api/qa/concerns",headers=h).json()["items"]
        for item,status in zip(items,("reviewing","resolved","open")):
            body={"status":status,"staff_note":"Follow-up action recorded." if status!="open" else ""}
            self.assertEqual(self.client.patch(f'/api/qa/concerns/{item["id"]}',headers=h,json=body).status_code,200)
        for status in ("open","reviewing","resolved"):
            data=self.client.get(f"/api/qa/concerns?status={status}",headers=h).json()
            self.assertEqual(data["total"],1);self.assertEqual(data["counts"],{"all":3,"open":1,"reviewing":1,"resolved":1})
            self.assertTrue(all(row["status"]==status for row in data["items"]))
        self.assertEqual(self.client.patch(f'/api/qa/concerns/{items[0]["id"]}',headers=h,json={"status":"resolved","staff_note":""}).status_code,422)

    def test_saved_draft_and_intervention_report_stages(self):
        self.client.post("/api/submissions",json=self.body())
        with self.Session() as db:
            f=db.query(Feedback).first();f.comment="The document processing queue is too slow."
            db.add(FeedbackLabel(feedback_id=f.id,aspect_id=1,sentiment="negative"))
            db.add_all([Alert(id=1,aspect_id=1,negative_count=4,recommendation="Automatic suggestion",status="new"),
                        Alert(id=2,aspect_id=1,negative_count=4,recommendation="Automatic suggestion",status="in-progress",note="[Long term] Approved improvement plan.",confirmed_at=datetime.utcnow()),
                        Alert(id=3,aspect_id=1,negative_count=4,recommendation="Automatic suggestion",status="resolved",note="[Short term] Completed improvement plan.",confirmed_at=datetime.utcnow(),completed_at=datetime.utcnow(),completion_note="Queue procedure updated with the office.")])
            db.commit()
        path="/api/qa/alerts/1"
        self.assertEqual(self.client.patch(path,headers=self.headers("admin"),json={"note":"[Short term] "}).status_code,422)
        result=self.client.patch(path,headers=self.headers("admin"),json={"note":"[Short term] Publish processing steps and monitor delays."})
        self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()["status"],"acknowledged")
        saved=next(a for a in self.client.get("/api/qa/alerts",headers=self.headers()).json() if a["id"]==1)
        self.assertEqual(saved["note"],result.json()["note"])
        for stage,expected in (("all",3),("awaiting",1),("approved",1),("completed",1)):
            report=self.client.post("/api/qa/reports",headers=self.headers("viewer"),json={"cycle_id":1,"intervention_status":stage})
            self.assertEqual(report.status_code,200,report.text)
            self.assertEqual(len(report.json()["actions"]),expected)
            self.assertTrue(all(not a["recommendation"].startswith("[") for a in report.json()["actions"]))
        self.assertEqual(self.client.patch("/api/qa/alerts/2",headers=self.headers(),json={"note":"Alter the already approved recommendation."}).status_code,409)
        progress=self.client.patch("/api/qa/alerts/2",headers=self.headers("admin"),json={"quad_note":"Consultation with the office is underway; revised steps are being reviewed."})
        self.assertEqual(progress.status_code,200,progress.text)
        self.assertEqual(progress.json()["status"],"in-progress")
        report=self.client.post("/api/qa/reports",headers=self.headers("viewer"),json={"cycle_id":1,"intervention_status":"approved"}).json()
        self.assertIn("Consultation",report["actions"][0]["remarks"])

    def test_restore_requires_udmbackup_filename_and_authenticated_contents(self):
        backup=self.client.post("/api/qa/backup",headers=self.headers()).text
        for name in (None,"backup.txt","backup.udmbackup.txt"):
            result=self.client.post("/api/qa/restore",headers=self.headers(),json={"backup":backup,"filename":name,"password":PASSWORD,"confirmation":"RESTORE"})
            self.assertEqual(result.status_code,422,result.text)
        result=self.client.post("/api/qa/restore",headers=self.headers(),json={"backup":"not an application backup","filename":"renamed.udmbackup","password":PASSWORD,"confirmation":"RESTORE"})
        self.assertEqual(result.status_code,422,result.text)

    def test_backup_roundtrip_tampering_and_session_revocation(self):
        self.client.post("/api/submissions",json=self.body())
        h=self.headers()
        backup=self.client.post("/api/qa/backup",headers=h);self.assertEqual(backup.status_code,200,backup.text)
        self.assertNotIn("student@udm.edu.ph",backup.text)
        altered=backup.text[:50]+("A" if backup.text[50]!="A" else "B")+backup.text[51:]
        bad=self.client.post("/api/qa/restore",headers=self.headers(),json={"backup":altered,"password":PASSWORD,"confirmation":"RESTORE","filename":"synthetic.udmbackup"})
        self.assertEqual(bad.status_code,422,bad.text)
        with self.Session() as db: db.add(StudentConcern(reference="AFTER",student_number="26-01-001",email="x@udm.edu.ph",category="other",message="Temporary test concern"));db.commit()
        h=self.headers()
        restored=self.client.post("/api/qa/restore",headers=h,json={"backup":backup.text,"password":PASSWORD,"confirmation":"RESTORE","filename":"synthetic.udmbackup"})
        self.assertEqual(restored.status_code,200,restored.text)
        self.assertIn("recovery_backup",restored.json())
        self.assertEqual(self.client.get("/api/qa/me",headers=h).status_code,401)
        with self.Session() as db:
            self.assertEqual(db.query(Feedback).count(),2);self.assertEqual(db.query(StudentConcern).count(),0)
            self.assertFalse(db.query(SurveySettings).one().is_active)
            self.assertTrue(db.query(AuditEvent).filter_by(action="restore_completed").count())

    def test_system_search_respects_every_source_permission_and_period(self):
        self.client.post("/api/submissions",json=self.body())
        with self.Session() as db:
            db.query(Feedback).first().comment="RoleScope shared search evidence."
            db.query(User).filter_by(username="viewer").one().display_name="RoleScope account"
            db.add(StudentConcern(reference="HELP-RoleScope",student_number="26-01-111",email="test@udm.edu.ph",category="other",message="RoleScope concern evidence."))
            db.add(AuditEvent(actor="RoleScope",action="search_test",target="synthetic",detail="Read-only search evidence"))
            db.add(Alert(aspect_id=1,status="acknowledged",negative_count=4,recommendation="",note="RoleScope saved recommendation."))
            rule=db.query(InterventionRule).filter_by(aspect_id=1).one()
            rule.diagnosed_pattern="RoleScope pattern";rule.recommendation="RoleScope configured recommendation."
            db.commit()
        for role,expected in (("super_admin",{"Evaluations","Interventions","Student concerns","Users","Audit trail","Settings"}),
                              ("executive_director",{"Evaluations","Interventions","Student concerns","Users","Audit trail","Settings"}),
                              ("admin",{"Evaluations","Interventions","Student concerns","Users","Audit trail","Settings"}),
                              ("assistant",{"Evaluations","Interventions"}), ("viewer",set())):
            result=self.client.get("/api/qa/search?q=RoleScope",headers=self.headers(role))
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual({g["label"] for g in result.json()["groups"]},expected,(role,result.text))
            self.assertNotIn("password_hash",result.text)
        result=self.client.get("/api/qa/search?q=RoleScope&cycle_id=2",headers=self.headers()).json()
        self.assertNotIn("Evaluations",{g["label"] for g in result["groups"]})
        self.assertIn("Users",{g["label"] for g in result["groups"]})
        self.assertEqual(self.client.get("/api/qa/search?q=ab").status_code,401)

    def test_concern_delete_is_authorized_and_audited(self):
        result=self.client.post("/api/concerns",json={"student_number":"26-01-111","email":"test@udm.edu.ph","category":"other","message":"Synthetic deletion workflow concern."})
        reference=result.json()["reference"]
        item=self.client.get("/api/qa/concerns",headers=self.headers()).json()["items"][0]
        path=f'/api/qa/concerns/{item["id"]}'
        for role in ("assistant","viewer"):
            self.assertEqual(self.client.delete(path,headers=self.headers(role)).status_code,403)
        self.assertEqual(self.client.delete(path,headers=self.headers("admin")).status_code,204)
        with self.Session() as db:
            self.assertEqual(db.query(StudentConcern).count(),0)
            event=db.query(AuditEvent).filter_by(action="concern_deleted",target=reference).one()
            self.assertEqual(event.actor,"admin")

    def test_completed_report_is_available_without_matching_evaluation_concerns(self):
        with self.Session() as db:
            db.add(Alert(aspect_id=1,status="resolved",negative_count=4,recommendation="",note="[Short term] Completed queue procedure review.",confirmed_at=datetime.utcnow(),completed_at=datetime.utcnow(),completion_note="Published the revised procedure and informed students."))
            db.commit()
        report=self.client.post("/api/qa/reports",headers=self.headers("viewer"),json={"cycle_id":2}).json()
        self.assertEqual(report["evaluations"],0)
        self.assertEqual(len(report["completed_interventions"]),1)
        self.assertIn("Published",report["completed_interventions"][0]["action_taken"])

    def test_restore_accepts_previous_backup_period_schema(self):
        from app.recovery import cipher
        self.client.post("/api/submissions",json=self.body())
        snapshot=self.client.post("/api/qa/backup",headers=self.headers()).text
        payload=json.loads(cipher().decrypt(snapshot.encode()))
        for row in payload["tables"]["feedback"]: row.pop("cycle_id")
        for row in payload["tables"]["survey_cycles"]:
            row.pop("start_date");row.pop("end_date")
        old_snapshot=cipher().encrypt(json.dumps(payload).encode()).decode()
        response=self.client.post("/api/qa/restore",headers=self.headers(),json={"backup":old_snapshot,"password":PASSWORD,"confirmation":"RESTORE","filename":"synthetic.udmbackup"})
        self.assertEqual(response.status_code,200,response.text)
        with self.Session() as db:
            self.assertEqual({r.cycle_id for r in db.query(Feedback)},{1})

if __name__=="__main__":unittest.main()

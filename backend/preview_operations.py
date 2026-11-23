"""Local UI QA with synthetic data only. Never connects to the configured MySQL database."""
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models import User, SurveyCycle, SurveySettings, Department, SurveySubmission, Respondent, Feedback, FeedbackLabel, Aspect, Alert
from app.auth import hash_password
from app.seed import seed_if_empty
from app.operations import digest

if __name__ == "__main__":
    import uvicorn
    temporary = tempfile.TemporaryDirectory(prefix="udm-ui-qa-")
    engine = create_engine("sqlite:///"+str(Path(temporary.name)/"preview.sqlite"),connect_args={"check_same_thread":False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as db:
        seed_if_empty(db)
        existing=db.query(User).first();existing.username="super_admin";existing.display_name="QA Preview";existing.password_hash=hash_password("Synthetic-password-123");existing.role="super_admin"
        for role in ("executive_director","admin","assistant","viewer"):
            db.add(User(username=role,display_name=role.replace("_"," ").title(),role=role,password_hash=existing.password_hash))
        db.add(SurveyCycle(id=1,academic_year="2026-2027",semester="1st"));db.commit()
        config=SurveySettings(min_negative_count=1,min_constructive_count=5,active_cycle_id=1,is_active=True,start_date=datetime.utcnow()-timedelta(days=1),end_date=datetime.utcnow()+timedelta(days=30));db.add(config)
        person=Respondent(student_number="26-01-001",institutional_email="synthetic@udm.edu.ph",college="CAS");db.add(person);db.flush()
        submission=SurveySubmission(cycle_id=1,respondent_id=person.id,reference="UDM-SYNTHETIC",receipt_hash=digest("preview"),request_key="preview",payload_hash="preview",student_number=person.student_number,institutional_email=person.institutional_email,college="CAS",student_status="regular",consent_version="2026-10-29")
        db.add(submission);db.flush();aspect=db.query(Aspect).filter_by(code="processing_time").one()
        for department in db.query(Department).filter_by(is_active=True):
            feedback=Feedback(submission_id=submission.id,respondent_id=person.id,department_id=department.id,comment="The service queue takes too long.",rating=3,rating_1=3,rating_2=3,rating_3=4,consent=True)
            db.add(feedback);db.flush();db.add(FeedbackLabel(feedback_id=feedback.id,aspect_id=aspect.id,sentiment="negative"))
        # Populate every aspect so dense chart layouts can be checked visually.
        department=db.query(Department).filter_by(is_active=True).first()
        for other in db.query(Aspect).filter(Aspect.id != aspect.id):
            feedback=Feedback(cycle_id=1,respondent_id=person.id,department_id=department.id,comment=f"Synthetic chart example for {other.name}.",rating=4,rating_1=4,rating_2=4,rating_3=4,consent=True)
            db.add(feedback);db.flush();db.add(FeedbackLabel(feedback_id=feedback.id,aspect_id=other.id,sentiment="positive"))
        db.add(Alert(aspect_id=aspect.id,negative_count=16,recommendation="Review queue processing with the office.",status="new"));db.commit()
    # Show both unclassified comments and exact no-comment entries in UI QA.
    with Session() as db:
        person=db.query(Respondent).first()
        department=db.query(Department).filter_by(is_active=True).first()
        for text in ("N/A","No comment","---","I visited the office to submit a request.","Pumunta ako sa opisina kahapon.","Nag submit ako ng form sa registrar.","Sana ayusin ang sirang computer.","The staff are helpful, please add chairs."):
            db.add(Feedback(cycle_id=1,respondent_id=person.id,department_id=department.id,comment=text,rating_1=4,rating_2=4,rating_3=4,consent=True))
        db.commit()
    from app.migrations import assign_existing_student_status
    assign_existing_student_status(engine)
    from app.services.reanalyze import refresh_analysis
    with Session() as db: refresh_analysis(db)
    def local_db():
        with Session() as db:yield db
    app.router.on_startup.clear()
    app.dependency_overrides[get_db]=local_db
    try: uvicorn.run(app,host="127.0.0.1",port=8001)
    finally: engine.dispose();temporary.cleanup()

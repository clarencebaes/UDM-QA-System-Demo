"""Survey cycles, atomic submissions, protected receipts and staff operations."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import secrets
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user, hash_password, verify_password
from app.access import role_of, ROLE_RANK
from app.audit import record, audit_search_clause
from app.config import settings
from app.models import (User, SurveyCycle, SurveySubmission, SurveySettings, Respondent, Feedback,
                        Department, AuditEvent, StudentConcern)
from app.schemas import FeedbackIn
from app.colleges import configured_colleges, validate_student_number, validate_institutional_email
from app.service_areas import is_service_area_applicable, get_service_area

router = APIRouter(prefix="/api")
CONSENT_VERSION = "2026-10-29"

def cycle_out(c):
    return {"id": c.id, "academic_year": c.academic_year, "semester": c.semester,
            "label": f"{c.academic_year} · {c.semester} semester", "start_date": c.start_date, "end_date": c.end_date}

def current_cycle(db):
    config = db.query(SurveySettings).first()
    return db.get(SurveyCycle, config.active_cycle_id) if config and config.active_cycle_id else None

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def receipt_token(key):
    return hmac.new(settings.jwt_secret.encode(), ("receipt:" + key).encode(), hashlib.sha256).hexdigest()

class CycleIn(BaseModel):
    academic_year: str = Field(pattern=r"^\d{4}-\d{4}$")
    semester: Literal["1st", "2nd"]

    @field_validator("academic_year")
    @classmethod
    def year_range(cls, value):
        a, b = map(int, value.split("-"))
        if b != a + 1 or a < 2000 or b > 2200:
            raise ValueError("Use consecutive academic years, for example 2026-2027.")
        return value

@router.get("/qa/cycles")
def cycles(user=Depends(get_current_user), db: Session = Depends(get_db)):
    active = current_cycle(db)
    return {"active_id": active.id if active else None,
            "items": [cycle_out(c) for c in db.query(SurveyCycle).order_by(SurveyCycle.academic_year.desc(), SurveyCycle.id.desc())]}

@router.post("/qa/cycles")
def create_cycle(body: CycleIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = SurveyCycle(**body.model_dump())
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This academic year and semester already exist.")
    return cycle_out(c)

@router.put("/qa/cycles/{cycle_id}/activate")
def activate_cycle(cycle_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(SurveyCycle, cycle_id)
    if not c:
        raise HTTPException(404, "Survey cycle not found.")
    if c.semester not in {"1st", "2nd"}:
        raise HTTPException(422, "Only 1st and 2nd semester surveys can be activated.")
    config = db.query(SurveySettings).with_for_update().first()
    if config is None:
        config = SurveySettings(is_active=False)
        db.add(config)
    if config.active_cycle_id != c.id:
        previous = db.get(SurveyCycle, config.active_cycle_id) if config.active_cycle_id else None
        if previous and config.start_date and config.end_date:
            previous.start_date, previous.end_date = config.start_date, config.end_date
        config.active_cycle_id = c.id
        config.is_active = False
        config.start_date = None
        config.end_date = None
    db.commit()
    return {**cycle_out(c), "message": "Cycle selected. Set its schedule and open the survey in Settings."}

class SubmissionIn(BaseModel):
    cycle_id: int
    student_status: Literal["regular", "irregular"]
    request_key: str = Field(pattern=r"^[a-fA-F0-9-]{36}$")
    consent_version: Literal["2026-10-29"]
    items: list[FeedbackIn] = Field(min_length=1, max_length=30)

@router.post("/submissions")
def submit(body: SubmissionIn, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    fingerprint = digest(body.model_dump_json())
    previous = db.query(SurveySubmission).filter_by(request_key=body.request_key).first()
    if previous:
        if previous.payload_hash != fingerprint:
            raise HTTPException(409, "This submission attempt has already been used. Start a new evaluation.")
        return {"reference": previous.reference, "receipt_token": receipt_token(body.request_key)}
    # Shared admission lock: students can submit concurrently, while schedule
    # changes wait for already-admitted submissions to commit (MySQL/MariaDB).
    config = db.query(SurveySettings).with_for_update(read=True).first()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not config or not config.is_active or config.active_cycle_id != body.cycle_id or not config.start_date or not config.end_date:
        raise HTTPException(409, "The survey is closed or its semester changed. Return home to check the current survey.")
    if (config.start_date and now < config.start_date) or (config.end_date and now > config.end_date):
        raise HTTPException(403, "The survey is outside its scheduled period.")
    first = body.items[0]
    if first.college not in {c["code"] for c in configured_colleges(db)}:
        raise HTTPException(422, "Select a valid college.")
    identity = (first.student_number, first.institutional_email.lower(), first.college)
    areas = {d.id: d for d in db.query(Department).filter_by(is_active=True)
             if is_service_area_applicable(d.code, first.college)}
    if len(body.items) != len(areas) or {i.department_id for i in body.items} != set(areas):
        raise HTTPException(422, "Complete each applicable service area exactly once.")
    for item in body.items:
        if (item.student_number, item.institutional_email.lower(), item.college) != identity or not item.consent:
            raise HTTPException(422, "Student details and consent must match throughout the evaluation.")
        scores = [item.rating_1, item.rating_2, item.rating_3]
        if any(s is None for s in scores):
            raise HTTPException(422, "All three ratings are required for each service area.")
        if min(scores) <= 2 and len(item.comment.strip()) < 10:
            raise HTTPException(422, "Explain low ratings in at least 10 characters.")
    existing = db.query(SurveySubmission).filter(SurveySubmission.cycle_id == body.cycle_id,
        or_(SurveySubmission.student_number == identity[0], SurveySubmission.institutional_email == identity[1])).first()
    if existing:
        raise HTTPException(409, "An evaluation is already recorded for these details in this semester. If this was not you, use Report a concern.")
    respondents = db.query(Respondent).filter(or_(Respondent.student_number == identity[0], Respondent.institutional_email == identity[1])).all()
    prior_feedback = db.query(Feedback.id).filter(Feedback.cycle_id == body.cycle_id,
        or_(Feedback.respondent_id.in_([r.id for r in respondents]), Feedback.student_number == identity[0])).first()
    if prior_feedback:
        raise HTTPException(409, "An evaluation is already recorded for these details in this semester. If this was not you, use Report a concern.")
    if respondents and (len(respondents) != 1 or respondents[0].student_number != identity[0] or respondents[0].institutional_email.lower() != identity[1]):
        raise HTTPException(409, "Your details conflict with an existing record. Use Report a concern for staff review.")
    person = respondents[0] if respondents else Respondent(student_number=identity[0], institutional_email=identity[1], college=identity[2])
    db.add(person)
    token = receipt_token(body.request_key)
    try:
        db.flush()
        submission = SurveySubmission(cycle_id=body.cycle_id, respondent_id=person.id,
            reference="UDM-" + secrets.token_hex(8).upper(), receipt_hash=digest(token),
            request_key=body.request_key, payload_hash=fingerprint, student_number=identity[0],
            institutional_email=identity[1], college=identity[2], student_status=body.student_status,
            consent_version=body.consent_version)
        db.add(submission)
        db.flush()
        records = []
        for item in body.items:
            f = Feedback(submission_id=submission.id, cycle_id=body.cycle_id, respondent_id=person.id, department_id=item.department_id,
                comment=item.comment.strip(), rating=round((item.rating_1 + item.rating_2 + item.rating_3)/3),
                rating_1=item.rating_1, rating_2=item.rating_2, rating_3=item.rating_3, consent=True)
            db.add(f)
            records.append(f)
        record(db, "student", "submit", submission.reference, "Complete evaluation and consent recorded")
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent retry may have committed this exact request.
        saved = db.query(SurveySubmission).filter_by(request_key=body.request_key, payload_hash=fingerprint).first()
        if saved:
            return {"reference": saved.reference, "receipt_token": token}
        raise HTTPException(409, "A submission already exists or your details conflict. Use Report a concern if needed.")
    # Classification runs after the entire evaluation is durable.
    from app.main import classify_feedback, evaluate_feedback_aspects, logger
    for f in records:
        try:
            label = classify_feedback(db, f)
            if label:
                evaluate_feedback_aspects(db, f.id)
        except Exception:
            db.rollback()
            logger.exception("Classification pending for feedback %s", f.id)
    return {"reference": submission.reference, "receipt_token": token}

class ReceiptIn(BaseModel):
    token: str = Field(min_length=64, max_length=64)

class SubmissionStatusIn(BaseModel):
    cycle_id: int
    student_number: str
    institutional_email: str
    token: str = Field(default="", max_length=64)
    request_key: str = Field(default="", max_length=36)

    @field_validator("student_number")
    @classmethod
    def student(cls, value): return validate_student_number(value)

    @field_validator("institutional_email")
    @classmethod
    def email(cls, value): return validate_institutional_email(value)

@router.post("/submissions/status")
def submission_status(body: SubmissionStatusIn, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    existing = db.query(SurveySubmission).filter(SurveySubmission.cycle_id == body.cycle_id,
        or_(SurveySubmission.student_number == body.student_number,
            SurveySubmission.institutional_email == body.institutional_email.lower())).first()
    if existing:
        # Identity fields alone are not proof of ownership. Never disclose answers
        # or mint a new receipt token from a student number and email address.
        candidate = body.token or (receipt_token(body.request_key) if body.request_key else "")
        allowed = bool(candidate) and hmac.compare_digest(existing.receipt_hash, digest(candidate))
        return {"submitted": True, "receipt_available": allowed, "receipt_token": candidate if allowed else None}
    prior = db.query(Feedback.id).outerjoin(Respondent, Feedback.respondent_id == Respondent.id).filter(
        Feedback.cycle_id == body.cycle_id, or_(Feedback.student_number == body.student_number,
        Respondent.student_number == body.student_number,
        Respondent.institutional_email == body.institutional_email.lower())).first()
    return {"submitted": bool(prior), "receipt_available": False}

@router.post("/receipt")
def receipt(body: ReceiptIn, response: Response, db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    s = db.query(SurveySubmission).filter_by(receipt_hash=digest(body.token)).first()
    if not s:
        raise HTTPException(404, "Receipt unavailable. Use the same browser tab or report a concern.")
    c = db.get(SurveyCycle, s.cycle_id)
    answers = []
    for f in db.query(Feedback).filter_by(submission_id=s.id).order_by(Feedback.id):
        d = db.get(Department, f.department_id)
        definition = get_service_area(d.code)
        answers.append({"service_area": d.name, "questions": definition["questions"] if definition else [],
                        "ratings": [f.rating_1, f.rating_2, f.rating_3], "comment": f.comment})
    return {"reference": s.reference, "cycle": cycle_out(c), "student_number": s.student_number,
            "institutional_email": s.institutional_email, "college": s.college,
            "student_status": s.student_status, "submitted_at": s.created_at.isoformat() + "Z", "answers": answers}

class ConcernIn(BaseModel):
    student_number: str = Field(max_length=32)
    email: str = Field(max_length=160)
    category: Literal["submission", "access", "receipt", "correction", "privacy", "other"]
    message: str = Field(min_length=10, max_length=2000)

    @field_validator("student_number")
    @classmethod
    def student(cls, value): return validate_student_number(value)

    @field_validator("email")
    @classmethod
    def email_address(cls, value): return validate_institutional_email(value)

@router.post("/concerns", status_code=201)
def concern(body: ConcernIn, db: Session = Depends(get_db)):
    if len(body.message.strip()) < 10:
        raise HTTPException(422, "Describe your concern in at least 10 characters.")
    cutoff = datetime.utcnow() - timedelta(hours=1)
    if db.query(StudentConcern).filter(StudentConcern.email == body.email, StudentConcern.created_at >= cutoff).count() >= 3:
        raise HTTPException(429, "Three concerns have already been sent for this email this hour. Please try later.")
    item = StudentConcern(reference="HELP-" + secrets.token_hex(6).upper(), **body.model_dump())
    db.add(item)
    record(db, "student", "concern_submitted", item.reference)
    db.commit()
    return {"reference": item.reference, "message": "Your concern is in the staff inbox. Keep this reference when contacting QUAD. This is not an email confirmation."}

@router.get("/qa/concerns")
def concerns(search: str = "", status: Literal["all", "open", "reviewing", "resolved"] = "all", page: int = Query(1, ge=1), user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(StudentConcern)
    if search.strip():
        q = q.filter(or_(*[column.contains(search.strip(), autoescape=True) for column in (StudentConcern.reference, StudentConcern.student_number, StudentConcern.email, StudentConcern.message, StudentConcern.category, StudentConcern.staff_note)]))
    counts = {"all": q.count(), "open": 0, "reviewing": 0, "resolved": 0}
    for value, count in q.with_entities(StudentConcern.status, func.count(StudentConcern.id)).group_by(StudentConcern.status): counts[value] = count
    if status != "all": q = q.filter(StudentConcern.status == status)
    total = q.count()
    page = min(page, max(1, (total + 19) // 20))
    return {"total": total, "counts": counts, "page": page, "items": [{k: getattr(c, k) for k in ("id", "reference", "student_number", "email", "category", "message", "status", "staff_note", "created_at")} for c in q.order_by(StudentConcern.created_at.desc()).offset((page-1)*20).limit(20)]}

class ConcernPatch(BaseModel):
    status: Literal["open", "reviewing", "resolved"]
    staff_note: str = Field(default="", max_length=2000)

@router.patch("/qa/concerns/{concern_id}")
def update_concern(concern_id: int, body: ConcernPatch, user=Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(StudentConcern, concern_id)
    if not c: raise HTTPException(404, "Concern not found.")
    note = body.staff_note.strip()
    if body.status != "open" and len(note) < 5: raise HTTPException(422, "Record a meaningful staff note before reviewing or resolving a concern.")
    c.status = body.status
    # Preserve any earlier remarks when reopening, but keep them out of the Open view.
    if body.status != "open": c.staff_note = note
    db.commit()
    return {"ok": True}

def user_out(u):
    return {"id": u.id, "username": u.username, "display_name": u.display_name, "role": role_of(u), "is_active": u.is_active}

@router.delete("/qa/concerns/{concern_id}", status_code=204)
def delete_concern(concern_id: int, user=Depends(get_current_user), db: Session=Depends(get_db)):
    item=db.get(StudentConcern,concern_id)
    if not item: raise HTTPException(404,"Concern not found.")
    record(db,user.username,"concern_deleted",item.reference,"Deleted the student concern; evaluation answers were not changed.")
    db.delete(item);db.commit()
    return Response(status_code=204)

class UserIn(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9._]{3,32}$")
    display_name: str = Field(min_length=2, max_length=100)
    role: Literal["viewer", "assistant", "admin", "executive_director", "super_admin"]
    password: str = Field(default="", max_length=72)
    is_active: bool = True

def check_password(password):
    if len(password) < 12 or len(password.encode()) > 72:
        raise HTTPException(422, "Use a password of at least 12 characters and at most 72 UTF-8 bytes.")

def managed(user, target_role):
    target = {"super_admin": "executive_director", "qa": "executive_director"}.get(target_role, target_role)
    if role_of(user) != "executive_director" and target == "executive_director":
        raise HTTPException(403, "Only the Executive Director can manage Director accounts.")

@router.get("/qa/users")
def users(search: str = "", page: int = Query(1, ge=1), user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(User)
    if search.strip(): q = q.filter(or_(User.username.contains(search.strip(), autoescape=True), User.display_name.contains(search.strip(), autoescape=True)))
    rank = case((User.role.in_(["executive_director", "super_admin", "qa"]), 0),
                *[(User.role == role, priority) for role, priority in ROLE_RANK.items() if priority], else_=4)
    return {"total": q.count(), "items": [user_out(u) for u in q.order_by(rank, User.display_name, User.id).offset((page-1)*20).limit(20)]}

@router.post("/qa/users", status_code=201)
def create_user(body: UserIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    managed(user, body.role)
    check_password(body.password)
    u = User(username=body.username.lower(), display_name=body.display_name.strip(), role=body.role,
             is_active=True, password_hash=hash_password(body.password))
    db.add(u)
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already exists.")
    return user_out(u)

@router.put("/qa/users/{user_id}")
def update_user(user_id: int, body: UserIn, user=Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u: raise HTTPException(404, "Account not found.")
    managed(user, role_of(u)); managed(user, body.role)
    if u.id == user.id and (not body.is_active or body.role != role_of(u)):
        raise HTTPException(409, "You cannot deactivate or change your own role.")
    # Serialize owner changes to preserve at least one active Director.
    admins = db.query(User).filter(User.role.in_(["executive_director", "super_admin", "qa"]), User.is_active.is_(True)).with_for_update().all()
    if role_of(u) == "executive_director" and (body.role not in {"executive_director", "super_admin"} or not body.is_active) and len(admins) <= 1:
        raise HTTPException(409, "Keep at least one active Executive Director.")
    if body.password:
        check_password(body.password)
        u.password_hash = hash_password(body.password)
    u.username, u.display_name, u.role, u.is_active = body.username.lower(), body.display_name.strip(), body.role, body.is_active
    u.token_version += 1
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already exists.")
    return user_out(u)

@router.delete("/qa/users/{user_id}", status_code=204)
def delete_user(user_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    directors = db.query(User).filter(User.role.in_(["executive_director", "super_admin", "qa"]), User.is_active.is_(True)).with_for_update().all()
    account = db.get(User, user_id)
    if not account:
        raise HTTPException(404, "Account not found.")
    managed(user, role_of(account))
    if account.id == user.id:
        raise HTTPException(409, "You cannot delete your own account.")
    if role_of(account) == "executive_director" and account.is_active and len(directors) <= 1:
        raise HTTPException(409, "Keep at least one active Executive Director.")
    db.delete(account)
    db.commit()
    return Response(status_code=204)

@router.get("/qa/audit")
def audit(search: str = "", event_id: int | None = Query(default=None, ge=1), page: int = Query(1, ge=1), user=Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(AuditEvent)
    if event_id: q = q.filter(AuditEvent.id == event_id)
    if search.strip():
        q = q.filter(audit_search_clause(search))
    return {"total": q.count(), "items": [{k: getattr(e, k) for k in ("id", "actor", "action", "target", "detail", "created_at")} for e in q.order_by(AuditEvent.id.desc()).offset((page-1)*20).limit(20)]}

@router.post("/auth/logout")
def logout(user=Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    record(db, user.username, "logout", "session", "All sessions for this account revoked")
    db.commit()
    return {"ok": True}

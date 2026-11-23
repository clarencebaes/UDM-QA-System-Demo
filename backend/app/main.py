from datetime import datetime, timezone, timedelta
import logging
import hashlib
import hmac
from time import perf_counter
from typing import Optional, Literal

from fastapi import Depends, FastAPI, HTTPException, Response, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import database as dbmod
from app.auth import create_token, get_current_user, verify_password
from app.config import settings
from app.database import Base, get_db
from app.colleges import configured_colleges, seed_colleges
from app.models import (
    Alert,
    Aspect,
    CollegeHeadcount,
    College,
    Department,
    Feedback,
    FeedbackLabel,
    InterventionRule,
    Respondent,
    SurveySettings,
    Threshold,
    User,
    SurveyCycle,
)
from app.schemas import (
    AlertOut,
    AlertPatch,
    AspectOut,
    CollegeCreate,
    CollegeOut,
    DashboardOut,
    DepartmentOut,
    FeedbackAck,
    FeedbackBatchIn,
    FeedbackDetail,
    FeedbackIn,
    FeedbackRow,
    HeadcountBulkIn,
    HeadcountRow,
    InterventionRuleCreate,
    InterventionRuleOut,
    InterventionRulePatch,
    LoginIn,
    SurveySettingsPatch,
    ThresholdOut,
    ThresholdPatch,
    TokenOut,
)
from app.seed import clear_stale_alerts, seed_if_empty
from app.services.alerts import evaluate_thresholds
from app.services.dashboard import aggregate_dashboard
from app.services.aspect_labels import display_aspects, aspect_ids
from app.services.aspect_model import model_status
from app.services.sentiment_model import sentiment_status
from ml.feedback_semantics import GENERAL_ASPECT_NAME
from app.services.feedback_text import is_no_substantive_feedback
from app.services.admin_reads import feedback_page, feedback_options, most_commented, intervention_view, selected_area_detail, load_options
from app.migrations import apply_migrations
from app.operations import router as operations_router, current_cycle, cycle_out, CONSENT_VERSION
from app.search import router as search_router
from app.access import role_of
from app.audit import record
import re
from app import audit as audit_events
from app.service_areas import (
    SERVICE_AREAS, LABORATORY_CODE, LABORATORY_COLLEGES,
    get_service_area, is_service_area_applicable,
)
from app.services.classify import classify_feedback, load_models

app = FastAPI(
    title="UdM QA Feedback System",
    description="Aspect-based Naïve Bayes feedback platform for administrative quality assurance.",
    version="0.1.0",
)
app.include_router(search_router)

app.include_router(operations_router)
from app.reports import router as reports_router
from app.recovery import router as recovery_router
app.include_router(reports_router)
app.include_router(recovery_router)

logger = logging.getLogger("udm.feedback")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list() + ["http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_slow_requests(request: Request, call_next):
    started = perf_counter()
    try:
        response = await call_next(request)
        if request.url.path.startswith(("/api/qa/", "/api/auth/", "/api/submissions/")) or request.url.path in {"/api/receipt", "/api/submissions"}:
            response.headers["Cache-Control"] = "no-store"
        return response
    finally:
        elapsed = perf_counter() - started
        if elapsed >= 2:
            # No tokens, bodies or query strings in timing diagnostics.
            logger.warning("Slow request: %s %s %.2fs", request.method, request.url.path, elapsed)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import sys
    import traceback
    # Log the full error server-side for debugging...
    print(f"UNHANDLED EXCEPTION: {exc}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    # ...but never leak internal details (which can expose the DB schema,
    # file paths, or library versions) to the client in production.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


@app.on_event("startup")
def on_startup():
    dbmod.init_engine()
    Base.metadata.create_all(bind=dbmod.engine)
    apply_migrations(dbmod.engine)
    load_models()
    db = dbmod.SessionLocal()
    try:
        seed_if_empty(db)
        from app.services.reanalyze import refresh_analysis
        refresh_analysis(db)
        clear_stale_alerts(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {
        "service": "UdM QA Feedback API",
        "docs": "/docs",
        "health": "/api/health",
        "frontend": "http://localhost:5173",
    }


@app.get("/json/version")
def json_version_probe():
    """Some dev tools probe this path; avoid noisy 404s in logs."""
    return {"status": "ok"}


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "db": dbmod.engine is not None,
        "service": "udm-qa-feedback",
        **model_status(),
        **sentiment_status(),
    }


@app.get("/api/colleges", response_model=list[CollegeOut])
def list_colleges(db: Session = Depends(get_db)):
    return [CollegeOut(code=item["code"], name=item["name"]) for item in configured_colleges(db)]


@app.post("/api/colleges", response_model=CollegeOut, status_code=201)
def add_college(
    college: CollegeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    seed_colleges(db)
    row = db.get(College, college.code)
    if row and row.is_active:
        raise HTTPException(status_code=400, detail="College code already exists.")
    numeric_code = college.numeric_code if college.numeric_code is not None else (row.numeric_code if row else None)
    if numeric_code and db.query(College).filter(College.numeric_code == numeric_code, College.code != college.code).first():
        raise HTTPException(status_code=400, detail="Numeric code already exists.")
    name = college.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="College name must contain at least two characters.")
    if db.query(College).filter(College.is_active.is_(True), func.lower(College.name) == name.lower(), College.code != college.code).first():
        raise HTTPException(status_code=400, detail="College name already exists.")
    if row:
        row.name, row.numeric_code, row.is_active = name, numeric_code, True
    else:
        db.add(College(code=college.code, name=name, numeric_code=numeric_code, is_active=True))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="College code or numeric code already exists.")
    return CollegeOut(code=college.code, name=name)


@app.delete("/api/colleges/{code}", status_code=204)
def delete_college(
    code: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    seed_colleges(db)
    row = db.get(College, code.strip().upper())
    if not row or not row.is_active:
        raise HTTPException(status_code=404, detail="College not found.")
    if db.query(College).filter(College.is_active.is_(True)).count() <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last college.")
    row.is_active = False
    db.commit()
    return Response(status_code=204)


def _require_college(db: Session, code: str) -> None:
    if code not in {item["code"] for item in configured_colleges(db)}:
        raise HTTPException(status_code=422, detail="Please select a valid college.")


@app.get("/api/departments", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db)):
    rows = db.query(Department).filter(Department.is_active.is_(True)).all()
    order = {item["code"]: index for index, item in enumerate(SERVICE_AREAS)}
    rows.sort(key=lambda r: order.get(r.code, len(order)))
    out = []
    for row in rows:
        sa = get_service_area(row.code)
        out.append(
            DepartmentOut(
                id=row.id,
                code=row.code,
                name=row.name,
                description=row.description or "",
                questions=sa["questions"] if sa else [],
                is_active=row.is_active,
                applicable_colleges=list(LABORATORY_COLLEGES) if row.code == LABORATORY_CODE else None,
            )
        )
    return out


@app.get("/api/evaluation-config")
def evaluation_config(db: Session = Depends(get_db)):
    # Public metadata only; existing consent and submission validation still apply.
    cycle = current_cycle(db)
    return {"departments": list_departments(db=db), "colleges": list_colleges(db=db), "cycle": cycle_out(cycle) if cycle else None, "consent_version": CONSENT_VERSION}


@app.get("/api/aspects", response_model=list[AspectOut])
def list_aspects(db: Session = Depends(get_db)):
    return db.query(Aspect).filter(Aspect.is_active.is_(True)).order_by(Aspect.name).all()


def _evaluation_complete(db: Session, respondent: Respondent) -> bool:
    required = {
        row.id for row in db.query(Department).filter(Department.is_active.is_(True)).all()
        if is_service_area_applicable(row.code, respondent.college)
    }
    received = {
        department_id for (department_id,) in db.query(Feedback.department_id)
        .filter(Feedback.respondent_id == respondent.id).distinct().all()
    }
    return bool(required) and required.issubset(received)


def _reject_repeated_areas(db: Session, respondent: Respondent, department_ids: list[int]) -> None:
    existing = db.query(Feedback.id).filter(
        Feedback.respondent_id == respondent.id,
        Feedback.department_id.in_(department_ids),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already submitted this evaluation for one or more service areas.")


def _get_or_create_respondent(db: Session, body: FeedbackIn) -> Respondent:
    by_number = (
        db.query(Respondent).filter(Respondent.student_number == body.student_number).first()
    )
    by_email = (
        db.query(Respondent)
        .filter(Respondent.institutional_email == body.institutional_email)
        .first()
    )
    if by_number and by_email and by_number.id != by_email.id:
        raise HTTPException(
            status_code=400,
            detail="This institutional email is already linked to a different student number.",
        )
    row = by_number or by_email
    if row:
        # Completion follows the respondent's applicable areas (15 or 16), not
        # a hardcoded row count. Check the stored college before changing it.
        if _evaluation_complete(db, row):
            raise HTTPException(
                status_code=400,
                detail="You have already submitted this evaluation.",
            )
        if row.college != body.college and db.query(Feedback.id).filter(Feedback.respondent_id == row.id).first():
            raise HTTPException(status_code=400, detail="College cannot be changed after an evaluation has been submitted.")
        row.student_number = body.student_number
        row.institutional_email = body.institutional_email
        row.college = body.college
        db.commit()
        db.refresh(row)
        return row
    row = Respondent(
        student_number=body.student_number,
        institutional_email=body.institutional_email,
        college=body.college,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Race: another simultaneous request created this respondent between
        # our SELECT and INSERT. Roll back and reuse the existing row instead
        # of surfacing a 500 to the student.
        db.rollback()
        row = (
            db.query(Respondent)
            .filter(
                (Respondent.student_number == body.student_number)
                | (Respondent.institutional_email == body.institutional_email)
            )
            .first()
        )
        if row is None:
            raise
    db.refresh(row)
    return row


def _survey_must_be_open(db: Session) -> None:
    """Legacy submission gate; current students use the atomic semester endpoint."""
    from app.config import settings as application_settings
    if not application_settings.legacy_submission_api:
        raise HTTPException(409, "Please use the current semester evaluation form.")
    settings = db.query(SurveySettings).first()
    if settings is not None and settings.active_cycle_id:
        raise HTTPException(409, "Please use the current semester evaluation form.")
    if settings is not None and not settings.is_active:
        raise HTTPException(
            status_code=403,
            detail="The survey is currently inactive. Please check back during the survey period.",
        )


@app.get("/api/survey-status")
def survey_status(db: Session = Depends(get_db)):
    config = db.query(SurveySettings).first()
    cycle = current_cycle(db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    opened = bool(config and config.is_active and cycle and config.start_date and config.end_date)
    if config and ((config.start_date and now < config.start_date) or (config.end_date and now > config.end_date)):
        opened = False
    return {"is_active": opened, "start_date": config.start_date if config else None,
            "end_date": config.end_date if config else None, "cycle": cycle_out(cycle) if cycle else None,
            "consent_version": CONSENT_VERSION}


@app.post("/api/feedback", response_model=FeedbackAck)
def submit_feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    _survey_must_be_open(db)
    _require_college(db, body.college)
    if not body.consent:
        raise HTTPException(status_code=400, detail="Consent is required before submitting feedback.")
    dept = db.get(Department, body.department_id)
    if not dept or not dept.is_active:
        raise HTTPException(status_code=400, detail="Unknown department.")
    if not is_service_area_applicable(dept.code, body.college):
        raise HTTPException(status_code=400, detail="Laboratory evaluation does not apply to the selected college.")
    aspect = None
    if body.aspect_id is not None:
        aspect = db.get(Aspect, body.aspect_id)
        if not aspect:
            raise HTTPException(status_code=400, detail="Unknown aspect.")

    respondent = _get_or_create_respondent(db, body)
    _reject_repeated_areas(db, respondent, [dept.id])
    item = Feedback(
        department_id=dept.id,
        aspect_id=aspect.id if aspect else None,
        respondent_id=respondent.id,
        comment=(body.comment or "").strip(),
        rating=body.rating,
        rating_1=body.rating_1,
        rating_2=body.rating_2,
        rating_3=body.rating_3,
        student_number=None,
        consent=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    try:
        label = classify_feedback(db, item)
        if label is not None:
            evaluate_feedback_aspects(db, label.feedback_id)
    except Exception:
        # Never lose the submission over classification, but do not swallow
        # the error silently either — a hidden failure here was how stale
        # labels survived.
        logger.exception("Post-submit classification failed for feedback %s", item.id)

    message = (
        "Thank you. Your comment was received."
        if item.comment
        else "Thank you. Your response was received."
    )
    return FeedbackAck(id=item.id, message=message)


@app.post("/api/feedback/batch", response_model=list[FeedbackAck])
def submit_feedback_batch(body: FeedbackBatchIn, db: Session = Depends(get_db)):
    _survey_must_be_open(db)
    if not body.items:
        raise HTTPException(status_code=400, detail="No evaluations provided.")
    _require_college(db, body.items[0].college)
    first = body.items[0]
    if any((item.student_number, item.institutional_email, item.college) !=
           (first.student_number, first.institutional_email, first.college) for item in body.items):
        raise HTTPException(status_code=400, detail="All evaluations in a batch must belong to the same student and college.")
    department_ids = [item.department_id for item in body.items]
    if len(set(department_ids)) != len(department_ids):
        raise HTTPException(status_code=400, detail="A service area may appear only once in an evaluation batch.")
    for item in body.items:
        if not item.consent:
            raise HTTPException(status_code=400, detail="Consent is required before submitting feedback.")
    for item in body.items:
        dept = db.get(Department, item.department_id)
        if not dept or not dept.is_active:
            raise HTTPException(status_code=400, detail=f"Unknown department: {item.department_id}.")
        if not is_service_area_applicable(dept.code, item.college):
            raise HTTPException(status_code=400, detail="Laboratory evaluation does not apply to the selected college.")
        aspect = None
        if item.aspect_id is not None:
            aspect = db.get(Aspect, item.aspect_id)
            if not aspect:
                raise HTTPException(status_code=400, detail=f"Unknown aspect: {item.aspect_id}.")

    respondent = _get_or_create_respondent(db, body.items[0])
    _reject_repeated_areas(db, respondent, department_ids)
    acks = []
    for item in body.items:
        dept = db.get(Department, item.department_id)
        aspect = None
        if item.aspect_id is not None:
            aspect = db.get(Aspect, item.aspect_id)
        record = Feedback(
            department_id=dept.id,
            aspect_id=aspect.id if aspect else None,
            respondent_id=respondent.id,
            comment=(item.comment or "").strip(),
            rating=item.rating,
            rating_1=item.rating_1,
            rating_2=item.rating_2,
            rating_3=item.rating_3,
            student_number=None,
            consent=True,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        try:
            label = classify_feedback(db, record)
            if label is not None:
                evaluate_feedback_aspects(db, label.feedback_id)
        except Exception:
            logger.exception("Post-submit classification failed for feedback %s", record.id)
        acks.append(
            FeedbackAck(
                id=record.id,
                message=(
                    "Thank you. Your comment was received."
                    if record.comment
                    else "Thank you. Your response was received."
                ),
            )
        )
    return acks


@app.post("/api/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip().lower()).with_for_update().first()
    now = datetime.utcnow()
    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(429, "Too many login attempts. Try again in 15 minutes.")
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        if user and user.is_active:
            user.failed_logins = (0 if user.locked_until else user.failed_logins) + 1
            user.locked_until = now + timedelta(minutes=15) if user.failed_logins >= 5 else None
        record(db, "unauthenticated", "login_failed", "session")
        db.commit()
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    user.failed_logins, user.locked_until = 0, None
    record(db, user.username, "login", "session")
    db.commit()
    token = create_token(user.username, role_of(user), user.token_version)
    return TokenOut(access_token=token, display_name=user.display_name, role=role_of(user))


@app.get("/api/qa/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "display_name": user.display_name, "role": role_of(user)}


@app.patch("/api/qa/me")
def update_profile(
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.auth import hash_password, verify_password

    from app.operations import check_password
    current_password = body.get("current_password")
    new_password = body.get("new_password")
    new_username = body.get("new_username")
    if new_username:
        new_username = str(new_username).strip().lower()

    if (new_password or new_username) and (not current_password or not verify_password(current_password, user.password_hash)):
        raise HTTPException(400, "Current password is incorrect.")

    # Validate and update password if provided
    if new_password:
        if not current_password:
            raise HTTPException(status_code=400, detail="Current password is required to change password.")
        if not verify_password(current_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
        if len(new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
        if not any(c.isalpha() for c in new_password) or not any(c.isdigit() for c in new_password):
            raise HTTPException(status_code=400, detail="Password must contain both letters and numbers.")
        check_password(new_password)
        user.password_hash = hash_password(new_password)
        user.token_version += 1

    # Validate and update username if provided
    if new_username:
        if len(new_username) < 3 or len(new_username) > 20:
            raise HTTPException(status_code=400, detail="Username must be 3-20 characters.")
        if not all(c.isalnum() or c in "._" for c in new_username):
            raise HTTPException(status_code=400, detail="Username can only contain letters, numbers, dots, and underscores.")
        # Check if username already exists
        existing = db.query(User).filter(User.username == new_username).first()
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Username already exists.")
        user.username = new_username.lower()
        user.token_version += 1

    db.commit()
    db.refresh(user)
    return {"username": user.username, "display_name": user.display_name, "role": role_of(user)}


def _aspect_name(db: Session, aspect_id: int | None) -> str:
    """Resolve an aspect name without relying on ORM relationship loading."""
    if not aspect_id:
        return ""
    aspect = db.get(Aspect, aspect_id)
    return aspect.name if aspect else ""


def _aspect_code(db: Session, aspect_id: int | None) -> str:
    """Resolve an aspect code without relying on ORM relationship loading."""
    if not aspect_id:
        return ""
    aspect = db.get(Aspect, aspect_id)
    return aspect.code if aspect else ""


def _threshold_out(t: Threshold, db: Session) -> ThresholdOut:
    return ThresholdOut(
        id=t.id,
        aspect_code=_aspect_code(db, t.aspect_id),
        min_count=t.min_count,
        window_days=t.window_days,
        include_constructive=t.include_constructive,
    )


def _rule_out(r: InterventionRule, db: Session) -> InterventionRuleOut:
    return InterventionRuleOut(
        id=r.id,
        aspect_code=_aspect_code(db, r.aspect_id),
        diagnosed_pattern=r.diagnosed_pattern,
        recommendation=r.recommendation,
        is_active=bool(getattr(r, "is_active", True)),
    )


def evaluate_feedback_aspects(db, feedback_id):
    for aspect_id in aspect_ids(db, feedback_id):
        evaluate_thresholds(db, aspect_id)


def _feedback_load_options():
    return load_options()


def _feedback_row(f: Feedback, db: Session) -> FeedbackRow:
    excluded = is_no_substantive_feedback(f.comment)
    label = None if excluded else f.label
    respondent = f.respondent
    names = display_aspects(f) if not excluded else []
    return FeedbackRow(
        id=f.id,
        respondent_group=hmac.new(settings.jwt_secret.encode(), f"survey-respondent:{f.respondent_id}".encode(), hashlib.sha256).hexdigest()[:24] if f.respondent_id else None,
        review_status="unclassified" if (f.comment or "").strip() and label is None else None,
        created_at=f.created_at,
        department=f.department.name if f.department else "",
        comment=f.comment or None,
        aspect=", ".join(names) if names else "N/A",
        aspects=names,
        aspect_version=f.aspect_run.model_version if f.aspect_run else None,
        sentiment=label.sentiment if label else None,
        polarity=label.polarity if label else None,
        is_constructive=bool(label.is_constructive) if label else False,
        detected_language=f.detected_language,
        analysis_reason=label.analysis_reason if label else None,
        aspect_source=("rule" if names == [GENERAL_ASPECT_NAME] else "model" if names else None) if f.aspect_run else label.aspect_source if label else None,
        sentiment_confidence=label.sentiment_confidence if label else None,
        rating=f.rating,
        rating_1=f.rating_1,
        rating_2=f.rating_2,
        rating_3=f.rating_3,
        college=f.submission.college if f.submission else f.respondent.college if f.respondent else None,
        student_number=(
            respondent.student_number if respondent else f.student_number
        ),
    )


def _headcount_map(db: Session) -> dict[str, CollegeHeadcount]:
    rows = db.query(CollegeHeadcount).all()
    return {row.college: row for row in rows}


def _safe_dt(value):
    if value is None or not hasattr(value, "year"):
        return None
    if getattr(value, "year", 1) < 1:
        return None
    return value


def _alert_out(a: Alert, db: Session) -> AlertOut:
    return AlertOut(
        id=a.id,
        service_area_scope=bool(a.service_area_scope),
        aspect="All reported aspects" if a.service_area_scope else a.aspect.name if a.aspect else "",
        aspect_code="all" if a.service_area_scope else a.aspect.code if a.aspect else "",
        department=a.department.name if a.department else None,
        negative_count=a.negative_count,
        constructive_count=a.constructive_count,
        diagnosed_pattern=a.diagnosed_pattern,
        recommendation=a.recommendation,
        status=a.status,
        note=a.note,
        quad_note=a.quad_note,
        confirmed_at=a.confirmed_at,
        completed_at=a.completed_at,
        completion_note=a.completion_note,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@app.get("/api/qa/feedback", response_model=list[FeedbackRow])
def qa_feedback(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    _ = user
    q = db.query(Feedback).options(*_feedback_load_options()).order_by(Feedback.created_at.desc())
    if start_date:
        q = q.filter(Feedback.created_at >= start_date)
    if end_date:
        q = q.filter(Feedback.created_at <= end_date)
    rows = q.limit(500).all()
    return [_feedback_row(f, db) for f in rows]


@app.get("/api/qa/feedback-page")
def qa_feedback_page(
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = None, department: Optional[str] = None, college: Optional[str] = None,
    aspect: Optional[str] = None, sentiment: str = "all",
    language: str = "all",
    comments_only: bool = True, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
):
    if not set(sentiment.split(",")).issubset({"all", "positive", "negative", "constructive", "neutral", "unclassified", "no_substantive", "uncertain"}):
        raise HTTPException(422, "Unknown comment category.")
    if language not in {"all", "english", "tagalog", "taglish", "unclassified", "undetermined"}:
        raise HTTPException(422, "Unknown detected language.")
    result = feedback_page(db, page, page_size, search, department, college, aspect, sentiment,
                           comments_only, start_date, end_date, language=language)
    result["items"] = [_feedback_row(item, db) for item in result["items"]]
    return result


@app.get("/api/qa/feedback-options")
def qa_feedback_options(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return feedback_options(db)


@app.get("/api/qa/most-commented")
def qa_most_commented(user: User = Depends(get_current_user), db: Session = Depends(get_db),
    page: int = Query(1, ge=1), page_size: int = Query(4, ge=1, le=16), department: Optional[str] = None):
    return most_commented(db, page, page_size, department)


@app.get("/api/qa/interventions")
def qa_intervention_view(user: User = Depends(get_current_user), db: Session = Depends(get_db), college: Optional[str] = None,
    page: int = Query(1, ge=1), page_size: int = Query(2, ge=1, le=10), include_alerts: bool = False):
    result = intervention_view(db, college, page=page, page_size=page_size)
    result["feedback"] = [_feedback_row(item, db) for item in result["feedback"]]
    for row in result["feedback"]:
        pair = next((p for p in result["pairs"] if p["service_area"] == row.department and p["aspect"] in row.aspects), None)
        if pair: row.aspect = pair["aspect"]
    if include_alerts:
        result["alerts"]=qa_alerts(user=user,db=db)
        result["rules"]=list_rules(user=user,db=db)
    return result


@app.get("/api/qa/intervention-detail")
def qa_intervention_detail(department: str, aspect_code: str,
    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    result = selected_area_detail(db, department, aspect_code)
    if result is None:
        raise HTTPException(status_code=404, detail="Service area/aspect configuration not found.")
    return result


@app.get("/api/qa/feedback/{feedback_id}", response_model=FeedbackDetail)
def qa_feedback_detail(
    feedback_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    item = db.get(Feedback, feedback_id)
    if not item:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    row = _feedback_row(item, db)
    respondent = item.respondent
    return FeedbackDetail(
        **row.model_dump(),
        institutional_email=respondent.institutional_email if respondent else None,
    )


@app.get("/api/qa/alerts", response_model=list[AlertOut])
def qa_alerts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    status: Optional[str] = None,
):
    _ = user
    q = db.query(Alert).options(joinedload(Alert.aspect), joinedload(Alert.department)).order_by(Alert.created_at.desc())
    if status:
        q = q.filter(Alert.status == status)
    return [_alert_out(a, db) for a in q.all()]


@app.patch("/api/qa/alerts/{alert_id}", response_model=AlertOut)
def patch_alert(
    alert_id: int,
    body: AlertPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    role = role_of(user)
    if alert.status == "resolved" and body.status and body.status != "resolved":
        raise HTTPException(409, "Completed interventions cannot be reopened. Create a new action for a new concern.")
    if body.note is not None:
        recommendation = re.sub(r"^\[(Short term|Long term)\]\s*", "", body.note.strip())
        if not 10 <= len(recommendation) <= 4000:
            raise HTTPException(422, "Write an actionable recommendation of 10 to 4,000 characters.")
        if alert.status == "new" and body.status in (None, "new"):
            body.status = "acknowledged"
    if role == "assistant" and (alert.status not in ("new", "acknowledged") or body.status not in (None, "new", "acknowledged")):
        raise HTTPException(403, "Unit staff can prepare drafts only.")
    if body.status == "in-progress" and role not in ("super_admin", "executive_director"):
        raise HTTPException(403, "Executive Director approval is required.")
    if body.status == "resolved":
        if role not in ("super_admin", "executive_director", "admin"):
            raise HTTPException(403, "Your role cannot complete interventions.")
        if not alert.confirmed_at:
            raise HTTPException(409, "Approve this recommendation before completing it.")
        if len((body.completion_note or alert.completion_note or "").strip()) < 10:
            raise HTTPException(422, "Describe the action taken in at least 10 characters.")
    if alert.status == "resolved" and role != "executive_director":
        raise HTTPException(409, "Completed interventions are retained as history.")
    if body.status in ("new", "acknowledged") and alert.confirmed_at:
        raise HTTPException(409, "An approved action cannot be returned to a draft.")
    if alert.confirmed_at and body.note is not None and body.note != alert.note:
        raise HTTPException(409, "The approved recommendation is retained. Record follow-up in remarks or create a new action.")
    if alert.confirmed_at and body.department_id is not None and body.department_id != alert.department_id:
        raise HTTPException(409, "An approved action cannot be reassigned to another service area.")
    if body.department_id is not None:
        dept = db.get(Department, body.department_id)
        if not dept:
            raise HTTPException(status_code=404, detail="Service area not found.")
        alert.department_id = dept.id
    if body.note is not None:
        alert.note = body.note
    if body.completion_note is not None:
        alert.completion_note = body.completion_note
    if body.quad_note is not None:
        alert.quad_note = body.quad_note.strip()
    if body.status:
        # Approval and completion are separate steps: an approved recommendation
        # stays in follow-up (in-progress) until it is explicitly completed.
        if body.status in ("in-progress", "resolved") and len(re.sub(r"^\[(Short term|Long term)\]\s*", "", (alert.note or "").strip())) < 10:
            raise HTTPException(
                status_code=400,
                detail="Write a recommendation before approving this alert.",
            )
        alert.status = body.status
        if body.status == "in-progress" and alert.confirmed_at is None:
            alert.confirmed_at = datetime.now(timezone.utc)
        if body.status == "resolved":
            if alert.confirmed_at is None:
                alert.confirmed_at = datetime.now(timezone.utc)
            if alert.completed_at is None:
                # First completion only — re-saving never rewrites the date,
                # so History keeps a single stable record per alert.
                alert.completed_at = datetime.now(timezone.utc)
    alert.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return _alert_out(alert, db)


@app.delete("/api/qa/alerts/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")
    db.delete(alert)
    db.commit()
    return Response(status_code=204)


@app.get("/api/qa/dashboard", response_model=DashboardOut)
def dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    college: Optional[str] = None,
    section: Literal["all", "summary", "charts"] = "all",
):
    return DashboardOut(**aggregate_dashboard(db, start_date, end_date, college, section))


@app.get("/api/qa/headcounts", response_model=list[HeadcountRow])
def list_headcounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    existing = _headcount_map(db)
    out = []
    for item in configured_colleges(db):
        row = existing.get(item["code"])
        out.append(
            HeadcountRow(
                college=item["code"],
                name=item["name"],
                headcount=row.headcount if row else 0,
                updated_at=_safe_dt(row.updated_at) if row else None,
            )
        )
    return out


@app.put("/api/qa/headcounts", response_model=list[HeadcountRow])
def save_headcounts(
    body: HeadcountBulkIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    existing = _headcount_map(db)
    for item in body.items:
        _require_college(db, item.college)
    for item in body.items:
        row = existing.get(item.college)
        if row:
            row.headcount = item.headcount
            row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            db.add(CollegeHeadcount(college=item.college, headcount=item.headcount))
    db.commit()
    return list_headcounts(user, db)


@app.get("/api/qa/thresholds", response_model=list[ThresholdOut])
def list_thresholds(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    return [_threshold_out(t, db) for t in db.query(Threshold).all()]


@app.patch("/api/qa/thresholds/{threshold_id}", response_model=ThresholdOut)
def patch_threshold(
    threshold_id: int,
    body: ThresholdPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    t = db.get(Threshold, threshold_id)
    if not t:
        raise HTTPException(status_code=404, detail="Threshold not found.")
    if body.min_count is not None:
        t.min_count = body.min_count
    if body.window_days is not None:
        t.window_days = body.window_days
    if body.include_constructive is not None:
        t.include_constructive = body.include_constructive
    db.commit()
    db.refresh(t)
    evaluate_thresholds(db, t.aspect_id)
    return _threshold_out(t, db)


@app.get("/api/qa/intervention-rules", response_model=list[InterventionRuleOut])
def list_rules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    return [_rule_out(r, db) for r in db.query(InterventionRule).all()]


def _validate_rule_aspect(db: Session, aspect_id: int, exclude_rule_id: int | None = None) -> None:
    """One default rule per aspect (intervention_rules.aspect_id is UNIQUE)."""
    if not db.get(Aspect, aspect_id):
        raise HTTPException(status_code=400, detail="Unknown aspect.")
    q = db.query(InterventionRule).filter(InterventionRule.aspect_id == aspect_id)
    if exclude_rule_id is not None:
        q = q.filter(InterventionRule.id != exclude_rule_id)
    if q.first():
        raise HTTPException(
            status_code=400,
            detail="This aspect already has an intervention rule. Edit that rule instead.",
        )


@app.post("/api/qa/intervention-rules", response_model=InterventionRuleOut, status_code=201)
def create_rule(
    body: InterventionRuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    _validate_rule_aspect(db, body.aspect_id)
    pattern = body.diagnosed_pattern.strip()
    recommendation = body.recommendation.strip()
    if len(pattern) < 3:
        raise HTTPException(status_code=400, detail="Diagnosed pattern must be at least 3 characters.")
    if len(recommendation) < 10:
        raise HTTPException(status_code=400, detail="Prescribed recommendation must be at least 10 characters.")
    rule = InterventionRule(
        aspect_id=body.aspect_id,
        diagnosed_pattern=pattern,
        recommendation=recommendation,
        is_active=body.is_active,
    )
    db.add(rule)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This aspect already has an intervention rule. Edit that rule instead.",
        )
    db.refresh(rule)
    return _rule_out(rule, db)


@app.patch("/api/qa/intervention-rules/{rule_id}", response_model=InterventionRuleOut)
def patch_rule(
    rule_id: int,
    body: InterventionRulePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    r = db.get(InterventionRule, rule_id)
    if not r:
        raise HTTPException(status_code=404, detail="Intervention rule not found.")
    if body.aspect_id is not None and body.aspect_id != r.aspect_id:
        _validate_rule_aspect(db, body.aspect_id, exclude_rule_id=rule_id)
        r.aspect_id = body.aspect_id
    if body.diagnosed_pattern is not None:
        r.diagnosed_pattern = body.diagnosed_pattern.strip()
    if body.recommendation is not None:
        r.recommendation = body.recommendation.strip()
    if body.is_active is not None:
        r.is_active = body.is_active
    db.commit()
    db.refresh(r)
    return _rule_out(r, db)


@app.delete("/api/qa/intervention-rules/{rule_id}", status_code=204)
def delete_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    r = db.get(InterventionRule, rule_id)
    if not r:
        raise HTTPException(status_code=404, detail="Intervention rule not found.")
    # Alerts keep their own copy of diagnosed_pattern/recommendation text, so
    # deleting a rule never erases history or existing alert records.
    db.delete(r)
    db.commit()
    return Response(status_code=204)


def _constructive_setting(db: Session):
    values = {t.include_constructive for t in db.query(Threshold).all()}
    return next(iter(values)) if len(values) == 1 else None


def _active_cycle_info(settings, db):
    cycle=db.get(SurveyCycle,settings.active_cycle_id) if settings.active_cycle_id else None
    return {"id":cycle.id,"academic_year":cycle.academic_year,"semester":cycle.semester,"label":f"{cycle.academic_year} · {cycle.semester} semester"} if cycle else None


@app.get("/api/qa/survey-settings")
def get_survey_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _ = user
    settings = db.query(SurveySettings).first()
    if not settings:
        # Create default settings
        settings = SurveySettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return {
        "active_cycle": _active_cycle_info(settings,db),
        "start_date": settings.start_date,
        "end_date": settings.end_date,
        "is_active": settings.is_active,
        "min_trigger_count": settings.min_trigger_count,
        "min_negative_count": settings.min_negative_count or settings.min_trigger_count,
        "min_constructive_count": settings.min_constructive_count or settings.min_trigger_count,
        "alert_window_days": settings.alert_window_days,
        "default_goal": settings.default_goal,
        "include_constructive": _constructive_setting(db),
    }


@app.patch("/api/qa/survey-settings")
def update_survey_settings(
    body: SurveySettingsPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = user
    body = body.model_dump(exclude_unset=True)
    for key in ("is_active", "min_trigger_count", "min_negative_count", "min_constructive_count", "alert_window_days", "default_goal", "include_constructive"):
        if key in body and body[key] is None:
            raise HTTPException(status_code=422, detail=f"{key} cannot be null.")
    settings = db.query(SurveySettings).first()
    if not settings:
        settings = SurveySettings()
        db.add(settings)

    for key in ("start_date", "end_date"):
        if body.get(key) and body[key].tzinfo:
            body[key] = body[key].astimezone(timezone.utc).replace(tzinfo=None)
    start = body.get("start_date", settings.start_date)
    end = body.get("end_date", settings.end_date)
    if body.get("is_active", settings.is_active) and any(key in body for key in ("is_active", "start_date", "end_date")) and (not start or not end):
        raise HTTPException(422, "Enter both the start date and end date before activating the survey.")
    if start and end and start > end:
        raise HTTPException(422, "Survey end must follow its start.")
    if body.get("is_active") and not settings.active_cycle_id:
        raise HTTPException(422, "Select a survey semester before opening submissions.")
    if "start_date" in body:
        settings.start_date = body["start_date"]
    if "end_date" in body:
        settings.end_date = body["end_date"]
    if settings.active_cycle_id and any(key in body for key in ("start_date", "end_date")):
        cycle = db.get(SurveyCycle, settings.active_cycle_id)
        if cycle:
            cycle.start_date, cycle.end_date = settings.start_date, settings.end_date
    if "is_active" in body:
        settings.is_active = body["is_active"]
    if "min_trigger_count" in body:
        settings.min_trigger_count = body["min_trigger_count"]
    for field in ("min_negative_count", "min_constructive_count"):
        if field in body: setattr(settings, field, body[field])
    if "min_trigger_count" in body:
        for field in ("min_negative_count", "min_constructive_count"):
            if field not in body: setattr(settings, field, body["min_trigger_count"])
    if "alert_window_days" in body:
        settings.alert_window_days = body["alert_window_days"]
    if "default_goal" in body:
        settings.default_goal = body["default_goal"]

    # Global controls in Settings must update the per-aspect trigger rules.
    for threshold in db.query(Threshold).all():
        if "min_trigger_count" in body:
            threshold.min_count = settings.min_trigger_count
        if "alert_window_days" in body:
            threshold.window_days = settings.alert_window_days
        if "include_constructive" in body:
            threshold.include_constructive = body["include_constructive"]
    settings.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(settings)
    if any(key in body for key in ("min_trigger_count", "min_negative_count", "min_constructive_count", "alert_window_days", "include_constructive")):
        evaluate_thresholds(db, None)

    return {
        "active_cycle": _active_cycle_info(settings,db),
        "start_date": settings.start_date,
        "end_date": settings.end_date,
        "is_active": settings.is_active,
        "min_trigger_count": settings.min_trigger_count,
        "min_negative_count": settings.min_negative_count or settings.min_trigger_count,
        "min_constructive_count": settings.min_constructive_count or settings.min_trigger_count,
        "alert_window_days": settings.alert_window_days,
        "default_goal": settings.default_goal,
        "include_constructive": _constructive_setting(db),
    }

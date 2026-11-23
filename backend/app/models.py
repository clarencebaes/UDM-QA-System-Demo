from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(default=True)


class Aspect(Base):
    __tablename__ = "aspects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(500), default="")
    is_active: Mapped[bool] = mapped_column(default=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Respondent(Base):
    __tablename__ = "respondents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_number: Mapped[str] = mapped_column(String(32), unique=True)
    institutional_email: Mapped[str] = mapped_column(String(160), unique=True)
    college: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now()
    )

    evaluations = relationship("Feedback", back_populates="respondent")


class College(Base):
    __tablename__ = "colleges"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    numeric_code: Mapped[str | None] = mapped_column(String(2), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CollegeHeadcount(Base):
    __tablename__ = "college_headcounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    college: Mapped[str] = mapped_column(String(16), unique=True)
    headcount: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now()
    )


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (Index("idx_feedback_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int | None] = mapped_column(ForeignKey("survey_submissions.id"), nullable=True, index=True)
    cycle_id: Mapped[int | None] = mapped_column(ForeignKey("survey_cycles.id"), nullable=True, index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    aspect_id: Mapped[int | None] = mapped_column(ForeignKey("aspects.id"), nullable=True)
    respondent_id: Mapped[int | None] = mapped_column(ForeignKey("respondents.id"), nullable=True)
    comment: Mapped[str] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_1: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_3: Mapped[int | None] = mapped_column(Integer, nullable=True)
    student_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    student_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    analysis_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consent: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    department = relationship("Department")
    submission = relationship("SurveySubmission")
    chosen_aspect = relationship("Aspect", foreign_keys=[aspect_id])
    respondent = relationship("Respondent", back_populates="evaluations")
    label = relationship("FeedbackLabel", uselist=False, back_populates="feedback")
    aspect_run = relationship("FeedbackAspectRun", uselist=False, back_populates="feedback", cascade="all, delete-orphan")


class FeedbackAspectRun(Base):
    __tablename__ = "feedback_aspect_runs"
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"), primary_key=True)
    model_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32))  # assigned or not_applicable
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    feedback = relationship("Feedback", back_populates="aspect_run")
    tags = relationship("FeedbackAspectTag", back_populates="run", cascade="all, delete-orphan")


class FeedbackAspectTag(Base):
    __tablename__ = "feedback_aspect_tags"
    __table_args__ = (UniqueConstraint("feedback_id", "aspect_id", name="uq_feedback_aspect_tag"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback_aspect_runs.feedback_id", ondelete="CASCADE"), index=True)
    aspect_id: Mapped[int] = mapped_column(ForeignKey("aspects.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    run = relationship("FeedbackAspectRun", back_populates="tags")
    aspect = relationship("Aspect")


class FeedbackLabel(Base):
    __tablename__ = "feedback_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feedback_id: Mapped[int] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"), unique=True)
    aspect_id: Mapped[int] = mapped_column(ForeignKey("aspects.id"))
    sentiment: Mapped[str] = mapped_column(Enum("positive", "negative", "neutral", "constructive"))
    polarity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_constructive: Mapped[bool] = mapped_column(default=False)
    analysis_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    aspect_confidence: Mapped[float] = mapped_column(Float, default=0)
    sentiment_confidence: Mapped[float] = mapped_column(Float, default=0)
    aspect_source: Mapped[str] = mapped_column(Enum("student", "model"), default="model")

    feedback = relationship("Feedback", back_populates="label")
    aspect = relationship("Aspect")


class Threshold(Base):
    __tablename__ = "thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aspect_id: Mapped[int] = mapped_column(ForeignKey("aspects.id"), unique=True)
    min_count: Mapped[int] = mapped_column(Integer, default=3)
    window_days: Mapped[int] = mapped_column(Integer, default=14)
    include_constructive: Mapped[bool] = mapped_column(Boolean, default=True)

    aspect = relationship("Aspect")


class InterventionRule(Base):
    __tablename__ = "intervention_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aspect_id: Mapped[int] = mapped_column(ForeignKey("aspects.id"), unique=True)
    diagnosed_pattern: Mapped[str] = mapped_column(String(500))
    recommendation: Mapped[str] = mapped_column(Text)
    # QUAD can disable a rule without deleting it; disabled rules are never
    # suggested on the Interventions page.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    aspect = relationship("Aspect")


class Alert(Base):
    __tablename__ = "alerts"

    service_area_scope: Mapped[bool] = mapped_column(Boolean, default=False)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aspect_id: Mapped[int] = mapped_column(ForeignKey("aspects.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    negative_count: Mapped[int] = mapped_column(Integer)
    constructive_count: Mapped[int] = mapped_column(Integer, default=0)
    diagnosed_pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Enum("new", "acknowledged", "in-progress", "resolved"), default="new")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    quad_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Approval and completion are separate steps: approving records confirmed_at,
    # only Mark complete records completed_at (and an optional completion note).
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    aspect = relationship("Aspect")
    department = relationship("Department")


class SurveySettings(Base):
    __tablename__ = "survey_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    active_cycle_id: Mapped[int | None] = mapped_column(ForeignKey("survey_cycles.id"), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    min_negative_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_constructive_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_trigger_count: Mapped[int] = mapped_column(Integer, default=3)
    alert_window_days: Mapped[int] = mapped_column(Integer, default=14)
    default_goal: Mapped[str] = mapped_column(String(32), default="short_term")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SurveyCycle(Base):
    __tablename__ = "survey_cycles"
    __table_args__ = (UniqueConstraint("academic_year", "semester", name="uq_survey_cycle"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    academic_year: Mapped[str] = mapped_column(String(9))
    semester: Mapped[str] = mapped_column(String(20))
    start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SurveySubmission(Base):
    __tablename__ = "survey_submissions"
    __table_args__ = (UniqueConstraint("cycle_id", "student_number", name="uq_cycle_student"),
                     UniqueConstraint("cycle_id", "institutional_email", name="uq_cycle_email"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("survey_cycles.id"))
    respondent_id: Mapped[int] = mapped_column(ForeignKey("respondents.id"))
    reference: Mapped[str] = mapped_column(String(40), unique=True)
    receipt_hash: Mapped[str] = mapped_column(String(64), unique=True)
    request_key: Mapped[str] = mapped_column(String(64), unique=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    student_number: Mapped[str] = mapped_column(String(32))
    institutional_email: Mapped[str] = mapped_column(String(160))
    college: Mapped[str] = mapped_column(String(16))
    student_status: Mapped[str] = mapped_column(String(16))
    consent_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str] = mapped_column(String(160))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StudentConcern(Base):
    __tablename__ = "student_concerns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True)
    student_number: Mapped[str] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    staff_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

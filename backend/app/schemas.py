from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.colleges import (
    normalize_college,
    validate_institutional_email,
    validate_student_number,
)


class DepartmentOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    questions: list[str] = []
    is_active: bool = True
    applicable_colleges: list[str] | None = None

    model_config = {"from_attributes": True}


class AspectOut(BaseModel):
    id: int
    code: str
    name: str
    description: str

    model_config = {"from_attributes": True}


class CollegeOut(BaseModel):
    code: str
    name: str


class CollegeCreate(BaseModel):
    code: str = Field(min_length=2, max_length=4)
    name: str = Field(min_length=2, max_length=120)
    numeric_code: Optional[str] = Field(default=None, pattern=r"^\d{2}$")

    @field_validator("code")
    @classmethod
    def _code(cls, value: str) -> str:
        return normalize_college(value)


class FeedbackIn(BaseModel):
    department_id: int
    aspect_id: Optional[int] = None
    comment: str = Field(default="", max_length=4000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    rating_1: Optional[int] = Field(default=None, ge=1, le=5)
    rating_2: Optional[int] = Field(default=None, ge=1, le=5)
    rating_3: Optional[int] = Field(default=None, ge=1, le=5)
    student_number: str = Field(min_length=1, max_length=32)
    institutional_email: str = Field(min_length=5, max_length=160)
    college: str = Field(min_length=2, max_length=16)
    consent: bool

    @field_validator("student_number")
    @classmethod
    def _student_number(cls, value: str) -> str:
        return validate_student_number(value)

    @field_validator("institutional_email")
    @classmethod
    def _email(cls, value: str) -> str:
        return validate_institutional_email(value)

    @field_validator("college")
    @classmethod
    def _college(cls, value: str) -> str:
        return normalize_college(value)


class FeedbackBatchIn(BaseModel):
    items: list[FeedbackIn]


class FeedbackAck(BaseModel):
    id: int
    message: str


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    display_name: str
    role: str


class FeedbackRow(BaseModel):
    aspects: list[str] = Field(default_factory=list)
    aspect_version: Optional[str] = None
    respondent_group: Optional[str] = None
    review_status: Optional[Literal["unclassified"]] = None
    id: int
    created_at: datetime
    department: str
    comment: Optional[str] = None
    aspect: Optional[str]
    sentiment: Optional[str]
    polarity: Optional[str] = None
    is_constructive: bool = False
    detected_language: Optional[str] = None
    analysis_reason: Optional[str] = None
    aspect_source: Optional[str]
    sentiment_confidence: Optional[float]
    rating: Optional[int]
    rating_1: Optional[int] = None
    rating_2: Optional[int] = None
    rating_3: Optional[int] = None
    college: Optional[str] = None
    student_number: Optional[str] = None

    model_config = {"from_attributes": True}


class FeedbackDetail(FeedbackRow):
    institutional_email: Optional[str] = None


class AlertOut(BaseModel):
    service_area_scope: bool = False
    quad_note: Optional[str] = None
    id: int
    aspect: str
    aspect_code: str
    department: Optional[str]
    negative_count: int
    constructive_count: int
    diagnosed_pattern: Optional[str] = None
    recommendation: str
    status: str
    note: Optional[str]
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completion_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertPatch(BaseModel):
    quad_note: Optional[str] = Field(default=None, max_length=4000)
    status: Optional[Literal["new", "acknowledged", "in-progress", "resolved"]] = None
    note: Optional[str] = None
    # Optional on Mark complete: what was actually done.
    completion_note: Optional[str] = None
    # Optional scope stamp: the service area the admin was reviewing.
    department_id: Optional[int] = None


class InterventionRuleOut(BaseModel):
    id: int
    aspect_code: str
    diagnosed_pattern: str
    recommendation: str
    is_active: bool = True

    model_config = {"from_attributes": True}


class InterventionRuleCreate(BaseModel):
    aspect_id: int
    diagnosed_pattern: str = Field(min_length=3, max_length=500)
    recommendation: str = Field(min_length=10, max_length=4000)
    is_active: bool = True


class ThresholdOut(BaseModel):
    id: int
    aspect_code: str
    min_count: int
    window_days: int
    include_constructive: bool

    model_config = {"from_attributes": True}


class ThresholdPatch(BaseModel):
    min_count: Optional[int] = Field(default=None, ge=1)
    window_days: Optional[int] = Field(default=None, ge=1)
    include_constructive: Optional[bool] = None


class InterventionRulePatch(BaseModel):
    aspect_id: Optional[int] = None
    diagnosed_pattern: Optional[str] = Field(default=None, min_length=3, max_length=500)
    recommendation: Optional[str] = Field(default=None, min_length=10, max_length=4000)
    is_active: Optional[bool] = None


class PriorityItem(BaseModel):
    aspect: str
    aspect_code: str
    negative: int
    total: int
    rank: int


class ServiceAreaPriorityItem(BaseModel):
    service_area: str
    negative: int
    constructive: int
    positive: int
    total: int
    negative_pct: int
    rank: int
    level: Literal["high", "medium", "low"]


class ServiceAreaAspectPriorityItem(BaseModel):
    service_area: str
    aspect: str
    classification: str
    count: int
    rank: int
    level: Literal["high", "medium", "low"]


class HeadcountRow(BaseModel):
    college: str
    name: str
    headcount: int
    updated_at: Optional[datetime] = None


class HeadcountPatch(BaseModel):
    college: str
    headcount: int = Field(ge=0, le=100000)

    @field_validator("college")
    @classmethod
    def _college(cls, value: str) -> str:
        return normalize_college(value)


class HeadcountBulkIn(BaseModel):
    items: list[HeadcountPatch]


class CollegeParticipationRow(BaseModel):
    neutral: int = 0
    neutral_pct: Optional[float] = None
    college: str
    name: str
    responses: int
    evaluations: int
    comments: int
    enrolled: Optional[int]
    response_rate: Optional[float]
    positive: int
    negative: int
    constructive: int
    positive_pct: Optional[float]
    negative_pct: Optional[float]
    constructive_pct: Optional[float]


class DashboardOut(BaseModel):
    neutral: int = 0
    polarity_counts: dict[str,int] = Field(default_factory=dict)
    language_counts: dict[str,int] = Field(default_factory=dict)
    feedback_types: dict[str,int] = Field(default_factory=dict)
    status_by_college: list[dict] = Field(default_factory=list)
    star_ratings: list[dict] = Field(default_factory=list)
    student_status: list[dict] = Field(default_factory=list)
    written_comments: int = 0
    no_substantive_comments: int = 0
    total_comments: int = 0
    classified_comments: int = 0
    unclassified_comments: int = 0
    short_unclassified_comments: int = 0
    pending_classification_comments: int = 0
    unassigned_comments: int = 0
    total_feedback: int
    unique_respondents: int
    overall_enrolled: Optional[int]
    overall_response_rate: Optional[float]
    positive: int
    negative: int
    constructive: int
    positive_pct: Optional[float]
    negative_pct: Optional[float]
    constructive_pct: Optional[float]
    unlabeled: int
    by_aspect: list[dict]
    by_department: list[dict]
    by_day: list[dict]
    priority: list[PriorityItem]
    service_area_priority: list[ServiceAreaPriorityItem]
    service_area_aspect_priority: list[ServiceAreaAspectPriorityItem]
    top_aspects: list[dict]
    concern_aspects: list[dict]
    open_alerts: int
    issue_count: int
    by_facility: list[dict]
    by_service_area: list[dict]
    by_college: list[CollegeParticipationRow]
    first_response_at: Optional[datetime] = None
    last_response_at: Optional[datetime] = None
    assistance_requests: list[dict] = []


class SurveySettingsPatch(BaseModel):
    min_negative_count: Optional[int] = Field(default=None, ge=1, le=100000)
    min_constructive_count: Optional[int] = Field(default=None, ge=1, le=100000)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    min_trigger_count: Optional[int] = Field(default=None, ge=1)
    alert_window_days: Optional[int] = Field(default=None, ge=1)
    include_constructive: Optional[bool] = None
    default_goal: Optional[Literal["short_term", "long_term"]] = None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def empty_date(cls, value):
        return None if value == "" else value

import os

from app.auth import hash_password, verify_password
from app.colleges import configured_colleges, seed_colleges
from app.models import Alert, Aspect, CollegeHeadcount, Department, Feedback, InterventionRule, Threshold, User, SurveySettings
from app.service_areas import SERVICE_AREAS

SERVICE_AREA_CODES = {item["code"] for item in SERVICE_AREAS}

from ml.aspect_taxonomy import CATALOG_DEFINITIONS

ASPECTS = [(item.code, item.name, item.includes) for item in CATALOG_DEFINITIONS]

# Survey-informed templates, not a diagnosis of every selected area.
RULES = {
    "processing_time": (
        "Comments describe slow document requests, repeated visits, and inconsistent processing or release times.",
        "Review the document-request workflow with the relevant office; publish requirements and turnaround targets; track delays and notify students when requests are ready.",
    ),
    "staff_responsiveness": (
        "Comments describe rude or intimidating interactions, inconsistent treatment, and difficulty obtaining helpful assistance.",
        "Review the reported interactions with the responsible office; reinforce respectful, consistent assistance; provide a confidential complaint channel and follow up on reported incidents.",
    ),
    "communication_clarity": (
        "Concerns about unclear announcements, requirements, or procedures require clarification with the relevant office.",
        "Review the specific unclear message or instruction; publish plain-language requirements and updates through official channels; identify a contact who can answer follow-up questions.",
    ),
    "service_accessibility": (
        "Comments describe offices or services being unavailable when needed, difficulty obtaining consultations, and limited access to online services or activities.",
        "Confirm the selected service area’s hours, availability, and contact channels; publish reliable schedules; provide an alternative contact or appointment route when staff or services are unavailable.",
    ),
    "facility_conditions": (
        "Comments describe dirty or unavailable restrooms, unreliable water, broken fans, chairs or computers, poor ventilation, and insufficient laboratory equipment.",
        "Inspect the specific problems reported in the selected service area; prioritize sanitation, water availability, ventilation and damaged equipment as applicable; assign repairs or cleaning and communicate progress to students.",
    ),
}

RULES.update({
    "general_service_feedback": (
        "Comments give an overall evaluation without identifying a specific service issue.",
        "Review the original comments with the service team. Maintain praised practices; clarify broad complaints or improvement requests before choosing a targeted intervention."),
    "digital_services": (
        "Comments describe slow internet, unreliable connectivity, or difficulties using online systems.",
        "Check the specific connection or platform problem; record reproducible issues, coordinate with ICT, and communicate service updates and available alternatives."),
    "affordability_value": (
        "Comments raise concerns about prices, student affordability, or value for money.",
        "Review the reported prices and available student options with the responsible provider; communicate pricing clearly and assess feasible affordable alternatives."),
    "service_program_quality": (
        "Comments question the quality, usefulness or adequacy of services, learning resources, food or student activities.",
        "Review the specific service or program with its responsible team; verify the reported quality issue, agree on improvements and follow up with students."),
    "fairness_inclusion_policy": (
        "Comments describe unequal treatment, inclusion concerns or inconsistent policy implementation.",
        "Review the reported incident and relevant policy impartially; clarify consistent criteria, provide a confidential reporting route and communicate the outcome through appropriate channels."),
})



from app.intervention_templates import CONCISE_RECOMMENDATIONS
RULES = {code:(pattern,CONCISE_RECOMMENDATIONS.get(code,rec)) for code,(pattern,rec) in RULES.items()}


def sync_service_areas(db) -> None:
    for item in SERVICE_AREAS:
        row = db.query(Department).filter(Department.code == item["code"]).first()
        if row:
            row.name = item["name"]
            row.description = item.get("description", "")
            row.is_active = True
        else:
            db.add(Department(code=item["code"], name=item["name"], description=item.get("description", "")))
    db.flush()
    for row in db.query(Department).all():
        if row.code not in SERVICE_AREA_CODES:
            row.is_active = False


def ensure_demo_user(db) -> None:
    # Credentials come from the environment so the production deploy can use a
    # strong, non-public password instead of the local demo default.
    username = os.getenv("QA_ADMIN_USER", "qa_admin")
    password = os.getenv("QA_ADMIN_PASSWORD", "qa1234")
    display_name = os.getenv("QA_ADMIN_NAME", "QA Administrator")

    # Provision only a fresh database. Never reset edited passwords or recreate
    # an account removed/renamed through user management on every restart.
    if db.query(User).count() == 0:
        db.add(User(username=username, password_hash=hash_password(password),
                    display_name=display_name, role="executive_director"))


def clear_stale_alerts(db) -> None:
    """Remove alerts when no feedback data exists yet."""
    if db.query(Feedback).count() == 0:
        db.query(Alert).delete()
        db.commit()


def seed_aspect_catalog(db) -> None:
    # Additive catalog: nine learned topics plus general feedback routing.
    settings = db.query(SurveySettings).first()
    first_threshold = db.query(Threshold).first()
    include_constructive = first_threshold.include_constructive if first_threshold else True
    for definition in CATALOG_DEFINITIONS:
        aspect = db.query(Aspect).filter(Aspect.code == definition.code).first()
        if aspect is None:
            aspect = Aspect(code=definition.code, name=definition.name, description=definition.includes)
            db.add(aspect)
            db.flush()
        else:
            aspect.name = definition.name
            aspect.description = definition.includes
        if not db.query(Threshold).filter(Threshold.aspect_id == aspect.id).first():
            db.add(Threshold(aspect_id=aspect.id,
                min_count=settings.min_trigger_count if settings else 3,
                window_days=settings.alert_window_days if settings else 14,
                include_constructive=include_constructive))
        if not db.query(InterventionRule).filter(InterventionRule.aspect_id == aspect.id).first():
            pattern, rec = RULES[aspect.code]
            db.add(InterventionRule(aspect_id=aspect.id, diagnosed_pattern=pattern, recommendation=rec))


def seed_if_empty(db) -> None:
    seed_colleges(db)
    sync_service_areas(db)
    clear_stale_alerts(db)

    seed_aspect_catalog(db)

    ensure_demo_user(db)

    for item in configured_colleges(db):
        if not db.query(CollegeHeadcount).filter(CollegeHeadcount.college == item["code"]).first():
            db.add(CollegeHeadcount(college=item["code"], headcount=0))

    db.commit()

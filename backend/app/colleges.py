"""Single source of truth for UDM college codes."""

from __future__ import annotations

import re
from app.models import College

COLLEGES = [
    {"code": "CAS", "name": "College of Arts and Sciences", "numeric_code": "20"},
    {"code": "CBM", "name": "College of Business and Management", "numeric_code": "21"},
    {"code": "CCJ", "name": "College of Criminal Justice", "numeric_code": "22"},
    {"code": "CCS", "name": "College of Computing Studies", "numeric_code": "23"},
    {"code": "CED", "name": "College of Education", "numeric_code": "24"},
    {"code": "CHS", "name": "College of Health Sciences", "numeric_code": "25"},
    {"code": "CPPG", "name": "College of Public Policy and Governance", "numeric_code": "26"},
]

COLLEGE_CODES = tuple(item["code"] for item in COLLEGES)
# Legacy administrative metadata only; never used to interpret student numbers.
COLLEGE_NUMERIC_CODES = {item["numeric_code"]: item["code"] for item in COLLEGES}

# Student numbers are opaque identifiers. Validate only the requested digit
# grouping; no group is interpreted as a year or college code.
_STUDENT_NUMBER_RE = re.compile(r"[0-9]{2}-[0-9]{2}-[0-9]{3}")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_college(value: str) -> str:
    code = (value or "").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9]{1,15}", code):
        raise ValueError("Please select a valid college.")
    return code


def validate_college(value: str) -> str:
    """Default-catalog validation for offline callers; API checks its database."""
    code = normalize_college(value)
    if code not in COLLEGE_CODES:
        raise ValueError("Please select a valid college.")
    return code


def seed_colleges(db) -> None:
    # Soft-deleted rows remain present, so a restart never resurrects removals.
    if db.query(College).count() == 0:
        db.add_all([College(**item) for item in COLLEGES])
        db.flush()


def configured_colleges(db, include_inactive: bool = False) -> list[dict]:
    rows = db.query(College).all()
    if not rows:
        return [dict(item) for item in COLLEGES]
    return [{"code": row.code, "name": row.name, "numeric_code": row.numeric_code}
            for row in rows if include_inactive or row.is_active]


def validate_student_number(value: str) -> str:
    """Accept ##-##-### without inferring a year, college, or sequence."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Student number is required.")
    if not _STUDENT_NUMBER_RE.fullmatch(raw):
        raise ValueError("Enter a student number in the format ##-##-### (digits and hyphens only).")
    return raw


def validate_institutional_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not email:
        raise ValueError("Institutional Email is required.")
    if len(email) > 160 or not _EMAIL_RE.match(email):
        raise ValueError("Enter a valid email address.")
    if not email.endswith("@udm.edu.ph"):
        raise ValueError("Only institutional email addresses (@udm.edu.ph) are accepted.")
    return email


def college_label(code: str | None) -> str:
    if not code:
        return "Unknown"
    for item in COLLEGES:
        if item["code"] == code:
            return f"{item['code']} · {item['name']}"
    return code

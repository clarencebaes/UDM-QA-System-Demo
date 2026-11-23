"""Authoritative four-role hierarchy enforced on staff API requests."""
from fastapi import HTTPException

ROLES = ("executive_director", "admin", "assistant", "viewer")
ROLE_RANK = {role: rank for rank, role in enumerate(ROLES)}

def role_of(user):
    # Compatibility for existing installation-owner accounts.
    return {"qa": "executive_director", "super_admin": "executive_director", "department_head": "viewer"}.get(user.role, user.role)

def authorize(user, path, method):
    role = role_of(user)
    if role not in ROLES:
        raise HTTPException(403, "This account has no staff access.")
    if path in {"/api/qa/me", "/api/auth/logout", "/api/qa/search"}:
        return
    resource = path.removeprefix("/api/qa/").split("/")[0]
    if path.startswith("/api/colleges"):
        resource = "settings"
    if role == "executive_director":
        return
    if role == "admin" and resource != "restore":
        return
    if resource == "cycles" and method == "GET":
        return
    if resource == "reports" and method in {"GET", "POST"}:
        return
    if role == "assistant" and method == "GET" and resource in {
        "dashboard", "feedback", "feedback-page", "feedback-options", "most-commented",
        "interventions", "intervention-detail", "alerts", "survey-settings", "thresholds",
        "intervention-rules", "headcounts"
    }:
        return
    raise HTTPException(403, "Your role does not permit this action.")

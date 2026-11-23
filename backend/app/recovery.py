"""Encrypted, same-installation application data snapshots; transactional restore."""
import base64
import hashlib
import json
from datetime import datetime
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import DateTime, select, delete
from sqlalchemy.orm import Session
from app.database import Base, get_db
from app.auth import get_current_user, verify_password
from app.config import settings
from app.models import User, AuditEvent
from app.audit import record

router = APIRouter(prefix="/api/qa")
MAX_BYTES = 20 * 1024 * 1024

def cipher():
    key = hashlib.sha256(("udm-backup-v1:" + settings.jwt_secret).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def tables():
    return [t for t in Base.metadata.sorted_tables if t.name != "audit_events"]

def pack(db):
    data = {}
    # Lock all application rows for a consistent snapshot. MySQL's next-key locks
    # also prevent insertions into these scans until this transaction ends.
    for t in tables():
        data[t.name] = [dict(r) for r in db.execute(select(t).with_for_update()).mappings()]
    history = [dict(r) for r in db.execute(select(AuditEvent.__table__).with_for_update()).mappings()]
    encoded = json.dumps({"format": "udm-app-backup-v1", "created_at": datetime.utcnow().isoformat(), "tables": data, "audit_events": history}, default=str).encode()
    if len(encoded) > MAX_BYTES:
        raise HTTPException(413, "This database exceeds the in-app backup limit. Use the database provider's backup procedure.")
    return cipher().encrypt(encoded).decode()

@router.post("/backup")
def backup(user=Depends(get_current_user), db: Session = Depends(get_db)):
    payload = pack(db)
    record(db, user.username, "backup_created", "application_data", "Encrypted snapshot including audit history")
    db.commit()
    return Response(payload, media_type="application/octet-stream", headers={"Cache-Control": "no-store", "Content-Disposition": 'attachment; filename="udm-backup.udmbackup"'})

@router.post("/restore")
async def restore(request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_BYTES * 2: raise HTTPException(413, "Backup file is too large.")
    try:
        body = json.loads(raw)
        if not isinstance(body, dict) or body.get("confirmation") != "RESTORE": raise ValueError()
        if not isinstance(body.get("filename"), str) or not body["filename"].lower().endswith(".udmbackup"):
            raise HTTPException(422, "Choose a .udmbackup file created by Download encrypted backup.")
        if not verify_password(str(body.get("password", "")), user.password_hash):
            raise HTTPException(403, "Current password is incorrect.")
        token = body["backup"].strip().encode()
        if base64.urlsafe_b64encode(base64.b64decode(token, altchars=b"-_", validate=True)) != token: raise ValueError()
        decoded = cipher().decrypt(token)
        if len(decoded) > MAX_BYTES: raise ValueError()
        saved = json.loads(decoded)
        if saved["format"] != "udm-app-backup-v1" or set(saved["tables"]) != {t.name for t in tables()}: raise ValueError()
        # Additive columns remain compatible with authentic older snapshots.
        for row in saved["tables"]["alerts"]:
            row.setdefault("service_area_scope", False)
        for row in saved["tables"]["feedback"]:
            row.setdefault("student_status", "regular" if row.get("submission_id") is None else None)
            row.setdefault("detected_language", None)
            row.setdefault("analysis_version", None)
        for row in saved["tables"]["feedback_labels"]:
            row.setdefault("polarity", None)
            row.setdefault("is_constructive", row.get("sentiment")=="constructive")
            row.setdefault("analysis_reason", None)
        for row in saved["tables"]["survey_settings"]:
            row.setdefault("min_negative_count", None)
            row.setdefault("min_constructive_count", None)
        # Accept snapshots from before the additive feedback-period column.
        old_feedback_columns = {c.name for c in Base.metadata.tables["feedback"].columns} - {"cycle_id"}
        old_rows = [r for r in saved["tables"]["feedback"] if set(r) == old_feedback_columns]
        if old_rows:
            cycles = saved["tables"]["survey_cycles"]
            historical = next((c for c in cycles if c["academic_year"] == "2026-2027" and c["semester"] == "1st"), None)
            if historical is None:
                historical = {"id": max((c["id"] for c in cycles), default=0) + 1, "academic_year": "2026-2027", "semester": "1st", "created_at": datetime.utcnow().isoformat()}
                cycles.append(historical)
            periods = {s["id"]: s["cycle_id"] for s in saved["tables"]["survey_submissions"]}
            for row in old_rows:
                row["cycle_id"] = periods.get(row["submission_id"], historical["id"])
        for cycle in saved["tables"]["survey_cycles"]:
            if set(cycle) == {"id", "academic_year", "semester", "created_at"}:
                config = next((c for c in saved["tables"]["survey_settings"] if c["active_cycle_id"] == cycle["id"]), {})
                cycle.update(start_date=config.get("start_date"), end_date=config.get("end_date"))
        for t in tables():
            rows = saved["tables"][t.name]
            if not isinstance(rows, list): raise ValueError()
            for row in rows:
                if set(row) != {c.name for c in t.columns}: raise ValueError()
                for c in t.columns:
                    if isinstance(c.type, DateTime) and row[c.name] is not None:
                        row[c.name] = datetime.fromisoformat(row[c.name])
        if not isinstance(saved.get("audit_events"), list): raise ValueError()
        for row in saved["audit_events"]:
            if set(row) != {c.name for c in AuditEvent.__table__.columns}: raise ValueError()
            row["created_at"] = datetime.fromisoformat(row["created_at"])
        restoring = next((u for u in saved["tables"]["users"] if u["username"] == user.username and u["role"] in {"executive_director", "super_admin", "qa"} and u["is_active"]), None)
        if not restoring: raise HTTPException(409, "Backup must contain your active Executive Director account.")
    except HTTPException: raise
    except (ValueError, KeyError, TypeError, InvalidToken, AttributeError):
        raise HTTPException(422, "Invalid, altered, or incompatible backup. Use a snapshot from this installation and encryption key.")
    # Require and return a fresh encrypted recovery snapshot before replacing data.
    before = pack(db)
    actor, password_hash = user.username, user.password_hash
    current_versions = {u.username: u.token_version for u in db.query(User)}
    restoring["password_hash"] = password_hash
    for u in saved["tables"]["users"]:
        u["token_version"] = max(u["token_version"], current_versions.get(u["username"], 0)) + 1
    for config in saved["tables"]["survey_settings"]:
        config["is_active"] = False
    try:
        db.info["skip_audit"] = True
        for t in reversed(tables()): db.execute(delete(t))
        for t in tables():
            if saved["tables"][t.name]: db.execute(t.insert(), saved["tables"][t.name])
        history_keys = {(a.actor, a.action, a.target, a.detail, a.created_at) for a in db.query(AuditEvent)}
        for item in saved["audit_events"]:
            key = tuple(item[k] for k in ("actor", "action", "target", "detail", "created_at"))
            if key not in history_keys:
                db.add(AuditEvent(**{k:v for k,v in item.items() if k != "id"}))
                history_keys.add(key)
        record(db, actor, "restore_completed", "application_data", "Survey closed; sessions revoked; current restoring administrator password preserved; live audit trail retained")
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "Restore failed validation. No data was replaced.")
    return {"message": "Restore complete. Survey is closed. Sign in again and review Settings before reopening.", "recovery_backup": before}

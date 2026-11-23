from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)

# bcrypt only uses the first 72 bytes of a password. bcrypt 5.x RAISES
# ValueError on longer input (4.x silently truncated), which crashed the app
# at startup when QA_ADMIN_PASSWORD was a long passphrase. Truncate
# identically in hash and verify so any password length works.
_BCRYPT_MAX_BYTES = 72


def _prepare(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prepare(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_token(username: str, role: str, version: int = 0) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {"sub": username, "role": role, "exp": exp, "ver": version}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in.")
    try:
        data = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired. Log in again.")
    user = db.query(User).filter(User.username == data.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found.")
    if not user.is_active or data.get("ver", 0) != user.token_version:
        raise HTTPException(401, "Session revoked. Please sign in again.")
    from app.access import authorize
    try:
        authorize(user, request.url.path, request.method)
    except HTTPException:
        from app.audit import record
        record(db, user.username, "access_denied", request.url.path)
        db.commit()
        raise
    db.info["actor"] = user.username
    from app.query_scope import set_scope
    set_scope(db, request)
    return user

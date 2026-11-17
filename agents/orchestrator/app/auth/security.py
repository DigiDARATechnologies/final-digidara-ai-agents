"""Password hashing and JWT session tokens for the platform's one real
account system (see app/models.py::User). This is the first genuine
authentication in the codebase — every agent's own ensure_profile/
ensure_session bridge stays untouched; they just now receive identity
that's actually been verified here."""
import os
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# No fallback string: a placeholder default here is a placeholder default
# everywhere it doesn't get overridden, which is exactly how session forgery
# happened — an environment left this unset and got the "dev-only" value for
# real. Generate a real secret per environment with `openssl rand -hex 32`.
_PLACEHOLDER_JWT_SECRETS = {
    "dev-only-insecure-secret-change-me",
    "dev-only-secret",
    "dev-only-jwt-secret",
}
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET or JWT_SECRET in _PLACEHOLDER_JWT_SECRETS:
    raise RuntimeError(
        "JWT_SECRET is not set (or is still a known placeholder value). "
        "Generate one with `openssl rand -hex 32` and set it before starting "
        "the orchestrator — every issued session token depends on it."
    )
JWT_ALGORITHM = "HS256"
# 7 days by default — long enough that this first pass doesn't need refresh
# tokens yet; can be shortened once that infrastructure exists.
JWT_EXPIRES_MINUTES = int(os.environ.get("JWT_EXPIRES_MINUTES", str(60 * 24 * 7)))

_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        # A malformed/corrupted stored hash (bad import, manual edit, truncated column) must
        # never crash the request with a 500 -- it simply can never verify successfully.
        # Caught broadly, not just ValueError: bcrypt's C build raises ValueError("Invalid
        # salt"), but its Rust build instead panics with a pyo3_runtime.PanicException,
        # which subclasses BaseException, not Exception.
        return False


def create_access_token(user_id: str, session_version: int = 0, session_id: str | None = None) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "sv": session_version, "iat": now, "exp": now + JWT_EXPIRES_MINUTES * 60}
    if session_id:
        # The sign-in this token belongs to (app/models.py:UserSignIn), so
        # Settings > Security can sign out one device on its own.
        payload["sid"] = session_id
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _session_state(user_id: str, session_id: str | None) -> tuple[int | None, bool]:
    """(session_version, revoked). The version is None when the account
    doesn't exist; callers already answer that case."""
    from app import db
    from app.models import User, UserSignIn

    session = db.get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            return None, False
        revoked = False
        if session_id:
            sign_in = session.get(UserSignIn, session_id)
            revoked = sign_in is not None and (sign_in.revoked_at is not None or sign_in.user_id != user_id)
        return int(user.session_version or 0), revoked
    finally:
        session.close()


def decode_session(token: str) -> tuple[str, str | None]:
    """(user_id, sign-in id) of a valid, unrevoked session token. Tokens from
    before sign-ins were recorded have no sign-in id."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session. Please log in again.") from exc
    # Other tokens signed with this secret -- the two-step sign-in challenge
    # ("purpose") and certificate links ("typ") -- are never a session.
    if payload.get("purpose") or payload.get("typ"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session. Please log in again.")
    user_id = payload["sub"]
    session_id = payload.get("sid")
    # Tokens issued before "sv" existed count as version 0, so this change
    # logs nobody out; a later bump (see auth/service.py:link_google_id)
    # still revokes them.
    current, revoked = _session_state(user_id, session_id)
    if revoked or (current is not None and int(payload.get("sv", 0)) != current):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session. Please log in again.")
    return user_id, session_id


def decode_access_token(token: str) -> str:
    return decode_session(token)[0]


def get_current_user_id(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)) -> str:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")
    return decode_access_token(credentials.credentials)


def get_current_session(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)) -> tuple[str, str | None]:
    """(user_id, sign-in id) for routes that act on this device's session."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")
    return decode_session(credentials.credentials)

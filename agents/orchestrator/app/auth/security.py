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
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "iat": now, "exp": now + JWT_EXPIRES_MINUTES * 60}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session. Please log in again.") from exc
    return payload["sub"]


def get_current_user_id(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme)) -> str:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")
    return decode_access_token(credentials.credentials)

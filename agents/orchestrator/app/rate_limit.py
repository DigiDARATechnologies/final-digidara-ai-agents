"""Per-user rate limiting (slowapi) for the orchestrator's chat routes.

Keys by the caller's verified user id when a valid bearer token is present,
falling back to per-IP only for the brief window before slowapi's own check
runs — every route that uses `limiter` also requires
Depends(get_current_user_id), so a request with no/invalid token is
rejected with 401 by that dependency rather than ever being counted here.
"""
from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth.security import decode_access_token


def _rate_limit_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        try:
            return decode_access_token(authorization[7:])
        except Exception:
            pass
    return get_remote_address(request)


# Shared by every gunicorn worker when RATE_LIMIT_STORAGE_URI points at Redis
# (docker-compose sets it); per-process memory otherwise, where 4 workers made
# every limit effectively 4x. If Redis is unreachable the limits fall back to
# per-process memory instead of failing the request.
RATE_LIMIT_STORAGE_URI = os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://").strip() or "memory://"

limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=RATE_LIMIT_STORAGE_URI,
    in_memory_fallback_enabled=not RATE_LIMIT_STORAGE_URI.startswith("memory://"),
    key_prefix="digidara",
)

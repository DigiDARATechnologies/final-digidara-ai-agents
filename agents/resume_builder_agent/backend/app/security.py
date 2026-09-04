"""Small, dependency-free security controls for the standalone application."""

from __future__ import annotations

from collections import defaultdict, deque
from functools import wraps
import hmac
import os
import secrets
import threading
from threading import Lock
from time import monotonic, time

from flask import current_app, jsonify, request, session


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LOCK = Lock()

# Set only by app/routes/invoke.py around its internal test_client()
# re-entry calls -- never settable by an incoming HTTP request, so this
# cannot be spoofed by a client. It exists because the inner re-entered
# request gets its own fresh Flask request/session, so the outer
# 'invoke.invoke' endpoint exemption below never covers it.
_invoke_reentry = threading.local()

def in_invoke_reentry() -> bool:
    return getattr(_invoke_reentry, "active", False)


def ensure_browser_session() -> tuple[str, str]:
    """Create a pseudonymous browser identity and CSRF token when needed."""
    if not session.get("user_id"):
        session["user_id"] = f"guest_{secrets.token_urlsafe(18)}"
    if not session.get("csrf_token"):
        session["csrf_token"] = secrets.token_urlsafe(32)
    session.permanent = True
    return session["user_id"], session["csrf_token"]


def session_user_id() -> str | None:
    return session.get("user_id")


def dev_header_allowed() -> bool:
    return (
        os.getenv("FLASK_ENV") != "production"
        and bool(current_app.config.get("ALLOW_DEV_USER_HEADER", False))
    )


def verify_csrf():
    """Validate double-submit style CSRF for cookie-authenticated mutations."""
    if current_app.testing:
        return None
    if request.method in SAFE_METHODS or not request.path.startswith("/api/"):
        return None
    # Strategy F requests carry no browser cookies. The invoke adapter owns
    # its production identity boundary and only re-enters protected routes
    # after applying a permitted identity context.
    if request.endpoint in {"session_api.session_info", "invoke.invoke"}:
        return None
    if in_invoke_reentry():
        return None
    if dev_header_allowed() and request.headers.get("X-User-Id"):
        return None

    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Your secure session expired. Refresh the page and retry.",
                }
            ),
            403,
        )
    return None


def _redis_client():
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    try:
        import redis
        return redis.Redis.from_url(redis_url, decode_responses=True)
    except ImportError as exc:
        raise RuntimeError("REDIS_URL requires the redis package to be installed.") from exc


def _redis_rate_limit(client, key, limit, window_seconds):
    now = time()
    member = f"{now}:{secrets.token_urlsafe(8)}"
    allowed, retry_after = client.eval(
        """
        local cutoff = tonumber(ARGV[1]) - tonumber(ARGV[2])
        redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
        if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then
            local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')[2]
            return {0, math.max(1, math.ceil(tonumber(oldest) + tonumber(ARGV[2]) - tonumber(ARGV[1])))}
        end
        redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
        redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
        return {1, 0}
        """,
        1, key, now, window_seconds, limit, member,
    )
    return bool(int(allowed)), int(retry_after)


def _memory_rate_limit(key, limit, window_seconds):
    now = monotonic()
    with _RATE_LOCK:
        bucket = _RATE_BUCKETS[key]
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            return False, max(1, int(window_seconds - (now - bucket[0])))
        bucket.append(now)
    return True, 0


def rate_limit(limit: int, window_seconds: int = 60):
    """Sliding-window limiter backed by Redis when REDIS_URL is configured."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if current_app.testing or current_app.config.get("DISABLE_RATE_LIMITS"):
                return view(*args, **kwargs)

            identity = session.get("user_id") or request.remote_addr or "unknown"
            key = f"rate-limit:{request.endpoint}:{identity}"
            try:
                client = _redis_client()
                allowed, retry_after = (
                    _redis_rate_limit(client, key, limit, window_seconds)
                    if client else _memory_rate_limit(key, limit, window_seconds)
                )
            except Exception:
                current_app.logger.exception("Redis rate limiter failed; denying request.")
                allowed, retry_after = False, window_seconds
            if not allowed:
                response = jsonify(
                    {
                        "success": False,
                        "message": "Too many requests. Please wait before retrying.",
                    }
                )
                response.status_code = 429
                response.headers["Retry-After"] = str(retry_after)
                return response
            return view(*args, **kwargs)

        return wrapped

    return decorator

import secrets
import time
import urllib.parse
from collections import defaultdict
from threading import Lock
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from cert_app.config import get_settings
from cert_app.schemas.user import UserRegister, UserLogin, Token
from cert_app.services.auth_service import (
    register_user, authenticate_user, create_access_token, verify_token
)

router = APIRouter()
security = HTTPBearer()


# ── In-Memory Handoff Code Store ─────────────────────────────────────────────
# NOTE: Pending exchange codes are stored in-memory in a thread-safe dict.
# WARNING: This in-memory implementation does NOT work across multiple worker
# processes or load-balanced nodes. Move handoff state to Redis or MySQL if
# scaling uvicorn to multiple workers (`--workers N`).
_handoff_store = {}
_handoff_lock = Lock()
HANDOFF_TTL_SECONDS = 30


# ── In-Memory IP Rate Limiter for Exchange Endpoint ──────────────────────────
# Protects unauthenticated /api/auth/exchange against brute-force code guessing.
class ExchangeRateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.ip_requests = defaultdict(list)
        self.lock = Lock()

    def check_rate_limit(self, request: Request):
        # SECURITY CRITICAL: Reading X-Forwarded-For must ONLY be enabled when
        # TRUST_PROXY_HEADERS is True. When TRUST_PROXY_HEADERS is False (default),
        # client-supplied X-Forwarded-For headers are strictly ignored so attackers
        # cannot bypass rate limits by spoofing random header values.
        # In production, TRUST_PROXY_HEADERS must only be enabled if your reverse proxy
        # (e.g. Nginx, Cloudflare, AWS ALB) is configured to strip incoming client
        # X-Forwarded-For headers and overwrite them with the actual verified client IP.
        s = get_settings()
        trust_proxy = getattr(s, "TRUST_PROXY_HEADERS", False)
        forwarded_for = request.headers.get("x-forwarded-for") if trust_proxy else None

        if trust_proxy and forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        now = time.time()
        with self.lock:
            # Filter timestamps outside window
            timestamps = [t for t in self.ip_requests[client_ip] if now - t < self.window_seconds]
            if len(timestamps) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many authentication exchange attempts. Please try again later."
                )
            timestamps.append(now)
            self.ip_requests[client_ip] = timestamps


exchange_rate_limiter = ExchangeRateLimiter(max_requests=10, window_seconds=60)


class HandoffRequest(BaseModel):
    token: str
    topic: Optional[str] = None


class ExchangeRequest(BaseModel):
    code: str


def _purge_expired_codes_locked():
    """Purge stale expired keys from the store. Must be called while holding _handoff_lock."""
    now = time.time()
    expired = [k for k, v in _handoff_store.items() if now > v.get("expires_at", 0) or v.get("used", False)]
    for k in expired:
        _handoff_store.pop(k, None)


def is_valid_handoff_code(code: str) -> bool:
    """Check if exchange code exists and is valid/unexpired without consuming it."""
    if not code:
        return False
    with _handoff_lock:
        _purge_expired_codes_locked()
        entry = _handoff_store.get(code)
        if not entry:
            return False
        return True


def consume_handoff_code(code: str) -> Optional[dict]:
    """Retrieve and immediately invalidate (delete) exchange code."""
    if not code:
        return None
    with _handoff_lock:
        _purge_expired_codes_locked()
        entry = _handoff_store.pop(code, None)
        if not entry:
            return None
        if time.time() > entry["expires_at"] or entry.get("used", False):
            return None
        entry["used"] = True
        return entry


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


@router.post("/register")
def register(request: UserRegister):
    try:
        user = register_user(request.name, request.email, request.password)
        # Convert datetime to string for JSON serialization
        if user.get("created_at"):
            user["created_at"] = str(user["created_at"])
        token = create_access_token({
            "sub": str(user["id"]),
            "name": user["name"],
            "email": user["email"]
        })
        return {"access_token": token, "token_type": "bearer", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
def login(request: UserLogin):
    user = authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    safe_user = {k: (str(v) if hasattr(v, 'isoformat') else v)
                 for k, v in user.items() if k != "hashed_password"}
    token = create_access_token({
        "sub": str(user["id"]),
        "name": user["name"],
        "email": user["email"]
    })
    return {"access_token": token, "token_type": "bearer", "user": safe_user}


@router.post("/handoff")
def create_handoff(request: HandoffRequest):
    """
    Cross-agent handoff endpoint: parent agent POSTs token and optional topic.
    Validates token and returns a short-lived (~30s), single-use exchange code.
    """
    payload = verify_token(request.token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token for handoff")

    code = secrets.token_urlsafe(32)
    expires_at = time.time() + HANDOFF_TTL_SECONDS

    with _handoff_lock:
        _purge_expired_codes_locked()
        _handoff_store[code] = {
            "token": request.token,
            "payload": payload,
            "topic": request.topic,
            "expires_at": expires_at,
            "used": False
        }

    safe_topic = urllib.parse.quote(request.topic) if request.topic else ""
    exchange_url = f"/?code={code}" + (f"&topic={safe_topic}" if safe_topic else "")
    return {
        "code": code,
        "expires_in": HANDOFF_TTL_SECONDS,
        "exchange_url": exchange_url
    }


@router.post("/exchange")
def exchange_code(request_body: ExchangeRequest, req: Request):
    """
    Exchanges a single-use code for session JWT and user details.
    Protected against brute-forcing via ExchangeRateLimiter (max 10 req/min per IP).
    Code is invalidated and popped immediately upon first use.
    """
    exchange_rate_limiter.check_rate_limit(req)

    entry = consume_handoff_code(request_body.code)
    if not entry:
        raise HTTPException(status_code=400, detail="Invalid, expired, or previously used exchange code")

    payload = entry["payload"]
    user_info = {
        "id": payload.get("sub"),
        "name": payload.get("name", ""),
        "email": payload.get("email", "")
    }
    return {
        "access_token": entry["token"],
        "token_type": "bearer",
        "user": user_info,
        "topic": entry.get("topic")
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user

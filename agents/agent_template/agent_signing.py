"""Verify the DigiDARA gateway's signature on incoming requests (FastAPI/ASGI).

The orchestrator signs every request it sends to an agent (see
orchestrator/app/auth/agent_signing.py). Verifying that signature is what makes
the x-digidara-user-id / x-digidara-is-admin headers trustworthy: without it,
anything that can reach this container could claim to be any user or an admin.

AGENT_SIGNATURE_MODE:
  warn     (default) log an invalid or missing signature but still serve the request
  enforce  reject it with 401
  off      skip verification

Every agent carries an identical copy of this file. Keep the golden vector in
the tests in step with orchestrator/tests/test_agent_signing.py.
"""
from __future__ import annotations

import hashlib
import contextvars
import hmac
import json
import logging
import os
import threading
import time

logger = logging.getLogger("digidara.signing")

DOMAIN = b"digidara-invoke-v1"
MAX_SKEW_SECONDS = 60
NONCE_TTL_SECONDS = 120
_DEFAULT_SECRET = "dev-only-agent-shared-secret"  # same local-dev fallback as registry_client.py

_nonces: dict[str, float] = {}
_nonce_lock = threading.Lock()
_last_sweep = 0.0
_verified_logged = False
# True while an already-accepted request is being handled in this task. A handler
# may call its own routes in-process (httpx.ASGITransport); those internal calls
# carry no signature and must not be verified a second time. A ContextVar follows
# the awaiting task (and threadpool hops) but never leaks between requests.
_outer_active: contextvars.ContextVar[bool] = contextvars.ContextVar("digidara_signing_outer_active", default=False)


def mode() -> str:
    value = os.environ.get("AGENT_SIGNATURE_MODE", "warn").strip().lower()
    return value if value in {"off", "warn", "enforce"} else "warn"


def _key() -> bytes:
    secret = os.environ.get("AGENT_SHARED_SECRET") or _DEFAULT_SECRET
    return hmac.new(secret.encode(), DOMAIN, hashlib.sha256).digest()


def canonical_string(timestamp, nonce, method, path, agent, user_id, is_admin, body: bytes) -> str:
    return "\n".join((
        DOMAIN.decode(), timestamp, nonce, method.upper(), path, agent,
        user_id, is_admin, hashlib.sha256(body).hexdigest(),
    ))


def _claim_nonce(nonce: str, now: float) -> bool:
    global _last_sweep
    with _nonce_lock:
        if now - _last_sweep > 10:
            _last_sweep = now
            for seen, at in list(_nonces.items()):
                if now - at > NONCE_TTL_SECONDS:
                    del _nonces[seen]
        if nonce in _nonces:
            return False
        _nonces[nonce] = now
        return True


def check(get_header, method: str, path: str, body: bytes, agent_name: str, now: float | None = None) -> str | None:
    """Return None when the request is validly signed, otherwise a reason code."""
    now = time.time() if now is None else now
    timestamp = get_header("x-digidara-timestamp") or ""
    nonce = get_header("x-digidara-nonce") or ""
    signature = get_header("x-digidara-signature") or ""
    target = get_header("x-digidara-agent") or ""
    if not (timestamp and nonce and signature and target):
        return "missing"
    try:
        signed_at = int(timestamp)
    except ValueError:
        return "malformed"
    if not 8 <= len(nonce) <= 64:
        return "malformed"
    if abs(now - signed_at) > MAX_SKEW_SECONDS:
        return "expired"
    if target != agent_name:
        return "wrong_recipient"
    canonical = canonical_string(
        timestamp, nonce, method, path, agent_name,
        get_header("x-digidara-user-id") or "", get_header("x-digidara-is-admin") or "", body,
    )
    expected = hmac.new(_key(), canonical.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return "bad_signature"
    if not _claim_nonce(nonce, now):
        return "replay"
    return None


def is_unsigned_health_probe(method: str, body: bytes) -> bool:
    """Docker healthchecks POST exactly {"action": "health"} to /api/invoke with no
    identity and no signature. That action returns only a static status."""
    if method.upper() != "POST" or len(body) > 200:
        return False
    try:
        parsed = json.loads(body)
    except ValueError:
        return False
    return isinstance(parsed, dict) and parsed.get("action") == "health" and set(parsed) <= {"action", "payload"} and not parsed.get("payload")


class GatewaySignatureMiddleware:
    """Pure ASGI middleware: buffers the body to hash it, then replays it downstream."""

    def __init__(self, app, agent_name: str):
        self.app = app
        self.agent_name = agent_name

    async def __call__(self, scope, receive, send):
        global _verified_logged
        current = mode()
        if scope["type"] != "http" or current == "off" or scope["path"] == "/health" or _outer_active.get():
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(chunks)

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        method = scope["method"]
        reason = None if is_unsigned_health_probe(method, body) else check(headers.get, method, scope["path"], body, self.agent_name)
        if reason is None:
            if not _verified_logged and headers.get("x-digidara-signature"):
                _verified_logged = True
                logger.info("gateway_signature_verified agent=%s (first verified request in this process)", self.agent_name)
        else:
            logger.warning(
                "gateway_signature_invalid reason=%s mode=%s agent=%s method=%s path=%s",
                reason, current, self.agent_name, method, scope["path"],
            )
            if current == "enforce":
                payload = json.dumps({"error": "Invalid service signature", "code": "invalid_service_signature"}).encode()
                await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())]})
                await send({"type": "http.response.body", "body": payload})
                return

        replayed = False

        async def replay():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        marker = _outer_active.set(True)
        try:
            await self.app(scope, replay, send)
        finally:
            _outer_active.reset(marker)

"""Verify the DigiDARA gateway's signature on incoming requests (Flask).

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
import hmac
import json
import logging
import os
import threading
import time

from flask import jsonify, request

logger = logging.getLogger("digidara.signing")

DOMAIN = b"digidara-invoke-v1"
MAX_SKEW_SECONDS = 60
NONCE_TTL_SECONDS = 120
_DEFAULT_SECRET = "dev-only-agent-shared-secret"  # same local-dev fallback as registry_client.py

_nonces: dict[str, float] = {}
_nonce_lock = threading.Lock()
_last_sweep = 0.0
_verified_logged = False
# Set while an already-accepted request is being handled on this thread. Invoke
# handlers re-enter the app's own routes in-process via app.test_client(); those
# internal calls carry no signature and must not be verified a second time.
_state = threading.local()
OUTER_MARKER = "digidara.signing.outer"


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


def install(app, agent_name: str) -> None:
    @app.before_request
    def verify_gateway_signature():
        global _verified_logged
        if getattr(_state, "outer_active", False):
            return None
        current = mode()
        if current == "off" or request.path == "/health":
            return None
        body = request.get_data()
        if is_unsigned_health_probe(request.method, body):
            return None
        reason = check(request.headers.get, request.method, request.path, body, agent_name)
        if reason is None:
            _state.outer_active = True
            request.environ[OUTER_MARKER] = True
            if not _verified_logged:
                _verified_logged = True
                logger.info("gateway_signature_verified agent=%s (first verified request in this process)", agent_name)
            return None
        logger.warning(
            "gateway_signature_invalid reason=%s mode=%s agent=%s method=%s path=%s",
            reason, current, agent_name, request.method, request.path,
        )
        if current == "enforce":
            return jsonify(error="Invalid service signature", code="invalid_service_signature"), 401
        _state.outer_active = True
        request.environ[OUTER_MARKER] = True
        return None

    @app.teardown_request
    def end_outer_request(_exc):
        # Only the request that set the flag clears it, never an internal re-entry.
        if request.environ.get(OUTER_MARKER):
            _state.outer_active = False

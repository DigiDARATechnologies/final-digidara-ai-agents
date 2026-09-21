"""Sign every orchestrator -> agent request so agents can trust the identity headers.

Agents verify these headers (see each agent's `agent_signing` module); until
an agent is switched to AGENT_SIGNATURE_MODE=enforce, a bad or missing
signature is only logged. Both sides must produce byte-identical canonical
strings: the golden vector in tests/test_agent_signing.py is copied into every
agent's tests to keep them in step.

The signing key is derived from AGENT_SHARED_SECRET with a domain label, so a
registration/heartbeat signature can never be replayed as an invoke signature
or the reverse.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlparse

from app.auth.service_auth import AGENT_SHARED_SECRET

DOMAIN = b"digidara-invoke-v1"


def _key() -> bytes:
    return hmac.new(AGENT_SHARED_SECRET.encode(), DOMAIN, hashlib.sha256).digest()


def canonical_string(timestamp: str, nonce: str, method: str, path: str, agent: str, user_id: str, is_admin: str, body: bytes) -> str:
    return "\n".join((
        DOMAIN.decode(), timestamp, nonce, method.upper(), path, agent,
        user_id, is_admin, hashlib.sha256(body).hexdigest(),
    ))


def signature_for(key: bytes, canonical: str) -> str:
    return hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest()


def sign_headers(
    agent_name: str, method: str, endpoint: str, body: bytes,
    user_id: str | None = None, is_admin: str | None = None,
    *, now: float | None = None, nonce: str | None = None,
) -> dict[str, str]:
    """Headers to add to a request to `endpoint`. `user_id` / `is_admin` must be
    exactly what is sent in x-digidara-user-id / x-digidara-is-admin (None when
    that header is not sent)."""
    timestamp = str(int(now if now is not None else time.time()))
    nonce = nonce or secrets.token_hex(16)
    path = urlparse(endpoint).path or "/"
    canonical = canonical_string(timestamp, nonce, method, path, agent_name, user_id or "", is_admin or "", body)
    return {
        "x-digidara-timestamp": timestamp,
        "x-digidara-nonce": nonce,
        "x-digidara-agent": agent_name,
        "x-digidara-signature": signature_for(_key(), canonical),
    }

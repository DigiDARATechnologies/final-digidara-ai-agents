"""Service-to-service auth for the orchestrator's /registry/* endpoints —
adapts the HMAC signed-request pattern already proven at
agents/codeforge_agent/services/lms-api/lms_api/auth.py: sign
timestamp + request-id + method + path + body-hash with a shared secret,
reject anything outside a max-age window, and reject an immediate replay of
the same request id.

Not applied to app/gateway/routes.py's /invoke route: that route is called
directly by the browser frontend with the end user's own bearer token (see
src/lib/gatewayClient.ts), never by another backend service, so there is no
shared secret to check there. Its own SSRF exposure — an unauthenticated
`action: "health"` call reaching whatever endpoint was registered — is
closed separately via the host allow-list in gateway/routes.py.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from threading import Lock

from fastapi import HTTPException, Request, status

ENV = os.environ.get("ENV", "dev")
AGENT_SHARED_SECRET = os.environ.get("AGENT_SHARED_SECRET", "")
if not AGENT_SHARED_SECRET:
    if ENV != "dev":
        raise RuntimeError(
            "AGENT_SHARED_SECRET is not set. Every agent that registers with "
            "or heartbeats to this orchestrator signs its requests with this "
            "shared secret — set it before starting the orchestrator outside "
            "of ENV=dev."
        )
    AGENT_SHARED_SECRET = "dev-only-agent-shared-secret"  # local dev only — every registry_client.py defaults to the same string

SIGNATURE_MAX_AGE_SECONDS = int(os.environ.get("SIGNATURE_MAX_AGE_SECONDS", "300"))

_seen_lock = Lock()
_seen_request_ids: dict[str, float] = {}


def _claim_request_id(request_id: str, now: float) -> bool:
    """Per-process replay guard: rejects an immediate resend of the same
    signed request within the max-age window. Not shared across worker
    processes — the timestamp+signature check is what stops a captured
    request from being replayed once it ages out, regardless of worker."""
    with _seen_lock:
        for seen_id, seen_at in list(_seen_request_ids.items()):
            if now - seen_at > SIGNATURE_MAX_AGE_SECONDS:
                del _seen_request_ids[seen_id]
        if request_id in _seen_request_ids:
            return False
        _seen_request_ids[request_id] = now
        return True


async def require_service_signature(request: Request) -> None:
    timestamp_text = request.headers.get("x-agent-timestamp", "")
    request_id = request.headers.get("x-agent-request-id", "").strip()
    signature = request.headers.get("x-agent-signature", "").strip()
    if not all((timestamp_text, request_id, signature)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing service signature.")

    try:
        timestamp = int(timestamp_text)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service signature.")

    now = time.time()
    if abs(now - timestamp) > SIGNATURE_MAX_AGE_SECONDS:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Service signature expired.")

    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((timestamp_text, request_id, request.method.upper(), request.url.path, body_hash))
    expected = hmac.new(AGENT_SHARED_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid service signature.")

    if not _claim_request_id(request_id, now):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This request has already been processed.")

import logging
import json
import os
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app import config
from app.auth.security import decode_access_token
from app.auth import service as auth_service
from app.registry import service as registry_service

logger = logging.getLogger("orchestrator.gateway")
router = APIRouter(prefix="/gateway", tags=["gateway"])

# Registration itself has no way to know an agent's endpoint is legitimate
# beyond the shared secret, and the `action: "health"` branch below is
# intentionally unauthenticated — so without this check, anyone who can
# register an agent (or tamper with one's registered endpoint) can make this
# gateway proxy a request to an arbitrary host on the internal network.
# Every real agent endpoint is a loopback service on this box or an internal
# hostname; nothing else should ever be reachable through here.
ALLOWED_AGENT_HOSTS = {
    h.strip() for h in os.environ.get("ALLOWED_AGENT_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()
}

# Used only as a fallback when an agent hasn't yet been upgraded to report
# its real per-call token usage via the X-Tokens-Used response header (see
# aptitude_agent's app/services/usage_service.py for the reference
# implementation). New accounts start with 10,000 (see app/models.py),
# topped up via Razorpay (app/billing/routes.py).
TOKEN_COST_PER_CALL = int(os.environ.get("TOKEN_COST_PER_CALL", "100"))

# Background bookkeeping/status calls the UI fires on its own -- opening
# Settings, refreshing an "online" indicator, listing a static catalog --
# not something the user actually asked for, and none of them invoke an
# LLM. Only genuine agent interactions get billed.
FREE_ACTIONS = {
    "ensure_session", "usage_summary", "list_courses", "list_languages",
    "ensure_profile", "get_thread_status", "getThreadStatus",
}


@router.post("/agents/{agent_name}/invoke")
async def invoke_registered_agent(agent_name: str, request: Request) -> Response:
    """Forward JSON or multipart bodies only to a live registry endpoint."""
    agent = registry_service.resolve_healthy(agent_name)
    if agent is None:
        raise HTTPException(503, f"Agent {agent_name!r} is not registered or its heartbeat is stale.")

    host = urlparse(agent.endpoint).hostname
    if host not in ALLOWED_AGENT_HOSTS:
        logger.warning(
            "blocked gateway invoke to disallowed host: agent=%s endpoint=%s host=%s", agent_name, agent.endpoint, host
        )
        raise HTTPException(403, f"Registered endpoint for {agent_name!r} is not on an allowed host.")

    body = await request.body()
    envelope = None
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            envelope = json.loads(body)
        except (TypeError, ValueError):
            pass

    # Health polling carries no learner data and remains public. Every other
    # action must be tied to a valid DigiDARA login.
    is_health = isinstance(envelope, dict) and envelope.get("action") == "health"
    user_id = None
    if not is_health:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing bearer token.")
        user_id = decode_access_token(authorization[7:])

    action_name = envelope.get("action") if isinstance(envelope, dict) else None
    is_free_action = action_name in FREE_ACTIONS
    is_billable = bool(user_id) and not is_free_action

    if is_billable:
        # Cheap pre-check only -- blocks starting a new request once a
        # balance has already run out. The real, accurate charge for this
        # specific request happens after the response comes back below.
        user = auth_service.get_by_id(user_id)
        if user is None:
            raise HTTPException(401, "This account no longer exists.")
        if user.token_balance <= 0:
            raise HTTPException(402, "Insufficient token balance. Please top up to continue.")

    headers: dict[str, str] = {}
    if content_type := request.headers.get("content-type"):
        headers["content-type"] = content_type
    if accept := request.headers.get("accept"):
        headers["accept"] = accept
    if user_id:
        # Derived from the verified platform JWT, never from the JSON payload.
        headers["x-digidara-user-id"] = user_id

    if isinstance(envelope, dict):
        if envelope.get("action") == "ensure_session":
            user = auth_service.get_by_id(user_id)
            if user is None:
                raise HTTPException(401, "This account no longer exists.")
            payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
            # Identity bridges receive only server-verified profile fields;
            # browser-supplied identity values are never forwarded.
            payload.update({"user_id": user.id, "name": user.name, "email": user.email, "mobile": user.mobile or ""})
            envelope["payload"] = payload
            body = json.dumps(envelope).encode("utf-8")

    try:
        async with httpx.AsyncClient(timeout=config.AGENT_CALL_TIMEOUT_SECONDS) as client:
            upstream = await client.post(agent.endpoint, content=body, headers=headers)
    except httpx.HTTPError as exc:
        logger.exception("gateway call failed: agent=%s endpoint=%s", agent_name, agent.endpoint)
        raise HTTPException(502, f"Registered agent {agent_name!r} could not be reached.") from exc

    if is_billable:
        real_tokens = None
        header_value = upstream.headers.get("x-tokens-used")
        if header_value is not None:
            try:
                parsed = int(header_value)
                if parsed > 0:
                    real_tokens = parsed
            except ValueError:
                pass
        # Real usage when the agent reports it; otherwise the flat fallback
        # rate, so billing still works for agents not yet upgraded.
        auth_service.settle_tokens(user_id, real_tokens if real_tokens is not None else TOKEN_COST_PER_CALL)

    response_headers: dict[str, str] = {}
    if upstream_content_type := upstream.headers.get("content-type"):
        response_headers["content-type"] = upstream_content_type
    if disposition := upstream.headers.get("content-disposition"):
        response_headers["content-disposition"] = disposition
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)

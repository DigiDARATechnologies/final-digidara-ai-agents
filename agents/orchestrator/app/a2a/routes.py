"""HTTP surface of the A2A hub.

    GET  /.well-known/agent-card.json             the hub's card (also at /a2a/.well-known/...)
    GET  /a2a/agents                              every reachable agent's card
    GET  /a2a/{agent}/.well-known/agent-card.json one agent's card
    POST /a2a/{agent}                             JSON-RPC: message/send, tasks/get, tasks/cancel

Cards are public (they hold no learner data). JSON-RPC calls need either a
learner's bearer token, or -- for an agent calling another agent on a
learner's behalf -- the registry's HMAC service signature plus
X-Digidara-On-Behalf-Of (the learner) and X-Digidara-Caller-Agent.
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.a2a import cards, hub
from app.a2a import protocol as p
from app.auth import service as auth_service
from app.auth.security import decode_access_token
from app.auth.service_auth import require_service_signature
from app.auth.verified import ensure_verified
from app.registry import service as registry_service

router = APIRouter(tags=["a2a"])

PUBLIC_BASE_URL = os.environ.get("A2A_PUBLIC_BASE_URL", "").rstrip("/")


def _base_url(request: Request) -> str:
    """Public origin for card URLs. TLS ends at the host's nginx, so the
    scheme this process sees is http; outside localhost it is https."""
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost"
    proto = request.headers.get("x-forwarded-proto")
    if not proto:
        proto = "http" if host.split(":")[0] in ("localhost", "127.0.0.1", "orchestrator") else "https"
    return f"{proto}://{host}"


def _healthy_cards(base_url: str) -> list[dict]:
    result = [
        cards.agent_card(base_url, row.agent_name, row.description, row.version)
        for row in registry_service.list_healthy()
    ]
    result.append(cards.readiness_card(base_url))
    return result


def _card_for(agent_name: str, base_url: str) -> dict:
    if agent_name == cards.READINESS_AGENT:
        return cards.readiness_card(base_url)
    row = registry_service.resolve_healthy(agent_name)
    if row is None:
        raise HTTPException(404, f"No reachable agent named {agent_name!r}.")
    return cards.agent_card(base_url, row.agent_name, row.description, row.version)


@router.get("/.well-known/agent-card.json")
@router.get("/a2a/.well-known/agent-card.json")
def hub_agent_card(request: Request) -> dict:
    base_url = _base_url(request)
    return cards.hub_card(base_url, _healthy_cards(base_url))


@router.get("/a2a/agents")
def list_agent_cards(request: Request) -> list[dict]:
    return _healthy_cards(_base_url(request))


@router.get("/a2a/{agent_name}/.well-known/agent-card.json")
def agent_card(agent_name: str, request: Request) -> dict:
    return _card_for(agent_name, _base_url(request))


async def _caller(request: Request):
    """(verified learner, caller name) for one JSON-RPC request."""
    if request.headers.get("x-agent-signature"):
        await require_service_signature(request)
        caller = (request.headers.get("x-digidara-caller-agent") or "").strip()
        if not caller or registry_service.resolve_healthy(caller) is None:
            raise HTTPException(403, "X-Digidara-Caller-Agent must name a registered, healthy agent.")
        user_id = (request.headers.get("x-digidara-on-behalf-of") or "").strip()
        if not user_id:
            raise HTTPException(400, "X-Digidara-On-Behalf-Of is required for agent-to-agent calls.")
        user = auth_service.get_by_id(user_id)
        ensure_verified(user)
        return user, caller
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token.")
    user = auth_service.get_by_id(decode_access_token(authorization[7:]))
    ensure_verified(user)
    return user, "user"


@router.post("/a2a/{agent_name}")
async def json_rpc(agent_name: str, request: Request) -> JSONResponse:
    user, caller = await _caller(request)
    if caller == agent_name:
        raise HTTPException(400, "An agent cannot call itself through the hub.")
    if agent_name != cards.READINESS_AGENT and registry_service.resolve_healthy(agent_name) is None:
        return JSONResponse(p.rpc_error(None, p.RpcError(p.INVALID_REQUEST, f"No reachable agent named {agent_name!r}.")))
    try:
        rpc = json.loads(await request.body())
    except ValueError:
        return JSONResponse(p.rpc_error(None, p.RpcError(p.PARSE_ERROR, "Request body is not valid JSON.")))
    return JSONResponse(await hub.handle(agent_name, rpc, user, caller))

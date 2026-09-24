import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.security import get_current_user_id
from app.orchestrator.graph import orchestrator_graph, route_message
from app.orchestrator.role_profiles import RoleProfileGenerationError, generate_role_profile
from app.rate_limit import limiter
from app.schemas import ChatRequest, ChatResponse, RoleProfileRequest, RoleProfileResponse, RouteRequest, RouteResponse

logger = logging.getLogger("orchestrator.api")

router = APIRouter(tags=["chat"])

CHAT_RATE_LIMIT_PER_MIN = os.environ.get("CHAT_RATE_LIMIT_PER_MIN", "20")
_CHAT_RATE_LIMIT = f"{CHAT_RATE_LIMIT_PER_MIN}/minute"


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(_CHAT_RATE_LIMIT)
def chat(req: ChatRequest, request: Request, user_id: str = Depends(get_current_user_id)) -> ChatResponse:
    thread_id = req.thread_id or uuid.uuid4().hex
    logger.info("=== POST /chat user=%s thread=%s message=%r", user_id, thread_id, req.message)
    try:
        result = orchestrator_graph.invoke({"message": req.message})
    except Exception:
        logger.exception("orchestrator graph failed for thread=%s", thread_id)
        raise HTTPException(
            502,
            "The orchestrator could not complete this turn (check LLM_MODEL / API key configuration). "
            "Please retry.",
        )
    return ChatResponse(thread_id=thread_id, reply=result.get("reply", ""), agent_used=result.get("agent_used"))


@router.post("/chat/route", response_model=RouteResponse)
@limiter.limit(_CHAT_RATE_LIMIT)
def chat_route(req: RouteRequest, request: Request, user_id: str = Depends(get_current_user_id)) -> RouteResponse:
    """Routing decision only (no agent call, no summarize) — the frontend
    uses this to hand a matched message off to that agent's own dedicated
    multi-turn flow instead of a single stateless tool invocation."""
    logger.info("=== POST /chat/route user=%s message=%r history_turns=%d", user_id, req.message, len(req.history))
    try:
        result = route_message(req.message, [turn.model_dump() for turn in req.history])
    except Exception:
        logger.exception("router-only graph failed")
        raise HTTPException(
            502,
            "The router could not complete this turn (check LLM_MODEL / API key configuration). Please retry.",
        )
    return RouteResponse(agent_name=result.get("agent_name"), reply=result.get("reply"))


@router.post("/role-profiles/generate", response_model=RoleProfileResponse)
@limiter.limit(_CHAT_RATE_LIMIT)
def generate_profile(
    req: RoleProfileRequest, request: Request, user_id: str = Depends(get_current_user_id)
) -> RoleProfileResponse:
    """Create a structured profile that clients can render or persist directly."""
    logger.info("=== POST /role-profiles/generate user=%s role=%r", user_id, req.target_role)
    try:
        return generate_role_profile(req)
    except RoleProfileGenerationError as exc:
        raise HTTPException(502, str(exc)) from exc

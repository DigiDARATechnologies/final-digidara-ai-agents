import json
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth import service as auth_service
from app.auth.verified import get_verified_user_id
from app.learner import service as learner_service
from app.llm import transcribe as speech
from app.orchestrator import boss_memory
from app.orchestrator.graph import orchestrator_graph, route_message, route_message_stream
from app.orchestrator.role_profiles import RoleProfileGenerationError, generate_role_profile
from app.rate_limit import limiter
from app.schemas import ChatRequest, ChatResponse, RoleProfileRequest, RoleProfileResponse, RouteRequest, RouteResponse

logger = logging.getLogger("orchestrator.api")

router = APIRouter(tags=["chat"])

CHAT_RATE_LIMIT_PER_MIN = os.environ.get("CHAT_RATE_LIMIT_PER_MIN", "20")
_CHAT_RATE_LIMIT = f"{CHAT_RATE_LIMIT_PER_MIN}/minute"


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(_CHAT_RATE_LIMIT)
def chat(req: ChatRequest, request: Request, user_id: str = Depends(get_verified_user_id)) -> ChatResponse:
    thread_id = req.thread_id or uuid.uuid4().hex
    # Length only: a learner's message is personal data (DPDP Act 2023) and
    # must not be copied into logs that outlive their account.
    logger.info("=== POST /chat user=%s thread=%s message_chars=%d", user_id, thread_id, len(req.message))
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
def chat_route(req: RouteRequest, request: Request, user_id: str = Depends(get_verified_user_id)) -> RouteResponse:
    """Routing decision only (no agent call, no summarize) — the frontend
    uses this to hand a matched message off to that agent's own dedicated
    multi-turn flow instead of a single stateless tool invocation."""
    logger.info("=== POST /chat/route user=%s message_chars=%d history_turns=%d", user_id, len(req.message), len(req.history))
    try:
        result = route_message(req.message, [turn.model_dump() for turn in req.history], _learner_context(user_id, req.message))
    except Exception:
        logger.exception("router-only graph failed")
        raise HTTPException(
            502,
            "The router could not complete this turn (check LLM_MODEL / API key configuration). Please retry.",
        )
    if not result.get("agent_name"):
        boss_memory.remember(user_id, req.message, result.get("reply"))
    return RouteResponse(agent_name=result.get("agent_name"), reply=result.get("reply"))


class RouteStreamRequest(RouteRequest):
    # The learner is talking to Boss by voice: a short spoken answer.
    voice: bool = False


@router.post("/chat/route/stream")
@limiter.limit(_CHAT_RATE_LIMIT)
def chat_route_stream(req: RouteStreamRequest, request: Request, user_id: str = Depends(get_verified_user_id)) -> StreamingResponse:
    """/chat/route, streamed as server-sent events: {"delta"} pieces of the
    answer as it is written, then {"done", "agent_name", "reply"}. The
    general chat shows (and Boss speaks) the answer while it is still being
    written instead of after it is finished."""
    logger.info("=== POST /chat/route/stream user=%s message_chars=%d history_turns=%d voice=%s",
                user_id, len(req.message), len(req.history), req.voice)
    context = _learner_context(user_id, req.message)
    history = [turn.model_dump() for turn in req.history]

    def events():
        try:
            for event in route_message_stream(req.message, history, context, voice=req.voice):
                if event.get("done") and not event.get("agent_name"):
                    boss_memory.remember(user_id, req.message, event.get("reply"))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("streamed router turn failed")
            yield 'data: {"error": "The router could not complete this turn. Please retry."}\n\n'

    # No proxy buffering, so each piece reaches the browser as it is written.
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _learner_context(user_id: str, question: str = "") -> dict | None:
    """Phase 2: the learner's goal, skills and shared memory, so the general
    chat answers personally. Never blocks a reply if it cannot be read."""
    try:
        context = learner_service.learner_context(user_id, "general_chat")
    except Exception:
        logger.warning("general chat: learner context unavailable", exc_info=True)
        context = {}
    # Their first name, so the assistant greets them like a friend.
    try:
        user = auth_service.get_by_id(user_id)
        first_name = str(user.name or "").strip().split()[0] if user and user.name else ""
    except Exception:
        first_name = ""
    if first_name:
        context = {**(context or {}), "first_name": first_name[:40]}
    # What Boss remembers from this learner's earlier conversations (mem0).
    remembered = boss_memory.recall(user_id, question) if question else []
    if remembered:
        context = {**(context or {}), "conversation_memory": remembered}
    return context or None


class TranscribeRequest(BaseModel):
    audio_base64: str = Field(min_length=1, max_length=speech.MAX_AUDIO_BASE64_CHARS)
    mime_type: str = Field(default="audio/webm", max_length=64)
    # "auto" (detect), "en" or "ta".
    language: str = Field(default="auto", max_length=8)


# Each call is a paid OpenAI request with up to a few minutes of audio.
# The microphone also sends the recording so far every few seconds, so the
# learner sees their words appear while they speak.
_TRANSCRIBE_RATE_LIMIT = "40/minute"


@router.post("/chat/transcribe")
@limiter.limit(_TRANSCRIBE_RATE_LIMIT)
def transcribe(req: TranscribeRequest, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    """The general chat's microphone: a recorded question in, its text out
    (OpenAI). The text is then sent like a typed message, so it passes the
    same length limit and prompt-injection guard."""
    try:
        text = speech.transcribe(req.audio_base64, req.mime_type, req.language)
    except speech.TranscriptionError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return {"transcript": text}


@router.post("/role-profiles/generate", response_model=RoleProfileResponse)
@limiter.limit(_CHAT_RATE_LIMIT)
def generate_profile(
    req: RoleProfileRequest, request: Request, user_id: str = Depends(get_verified_user_id)
) -> RoleProfileResponse:
    """Create a structured profile that clients can render or persist directly."""
    logger.info("=== POST /role-profiles/generate user=%s role=%r", user_id, req.target_role)
    try:
        return generate_role_profile(req)
    except RoleProfileGenerationError as exc:
        raise HTTPException(502, str(exc)) from exc

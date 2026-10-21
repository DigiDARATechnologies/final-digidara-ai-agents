import json
import logging
import os
import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.auth import service as auth_service
from app.auth.verified import get_verified_user_id
from app.english_only import require_english
from app.learner import service as learner_service
from app.links import service as links_service
from app.llm import client as llm_client
from app.llm import transcribe as speech
from app.orchestrator import assist, boss_memory
from app.orchestrator.graph import orchestrator_graph, route_message, route_message_stream
from app.orchestrator.role_profiles import RoleProfileGenerationError, generate_role_profile
from app.rate_limit import limiter
from app.registry import service as registry_service
from app.schemas import ChatRequest, ChatResponse, RoleProfileRequest, RoleProfileResponse, RouteRequest, RouteResponse

logger = logging.getLogger("orchestrator.api")

router = APIRouter(tags=["chat"])

CHAT_RATE_LIMIT_PER_MIN = os.environ.get("CHAT_RATE_LIMIT_PER_MIN", "20")
_CHAT_RATE_LIMIT = f"{CHAT_RATE_LIMIT_PER_MIN}/minute"

# Boss's own model calls are charged like an agent's: the tokens they really
# used come off the learner's balance, shown to them as points.
BOSS_USAGE_NAME = "boss"
OUT_OF_POINTS = "Not enough points. Please top up to continue."


def _require_points(user_id: str) -> None:
    """Like the gateway: a turn cannot start once the balance has run out."""
    user = auth_service.get_by_id(user_id)
    if user is not None and user.token_balance <= 0:
        raise HTTPException(402, OUT_OF_POINTS)


def _charge(user_id: str, usage: dict[str, int], action: str) -> None:
    tokens = int(usage.get("tokens") or 0)
    if tokens <= 0:
        return
    try:
        auth_service.settle_tokens(user_id, tokens, BOSS_USAGE_NAME, action)
    except Exception:
        logger.exception("could not charge %d Boss tokens to user=%s", tokens, user_id)


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(_CHAT_RATE_LIMIT)
def chat(req: ChatRequest, request: Request, user_id: str = Depends(get_verified_user_id)) -> ChatResponse:
    require_english(req.message)
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
    require_english(req.message)
    _require_points(user_id)
    usage: dict[str, int] = {}
    try:
        result = route_message(req.message, [turn.model_dump() for turn in req.history], _learner_context(user_id, req.message),
                               usage=usage)
    except Exception:
        logger.exception("router-only graph failed")
        raise HTTPException(
            502,
            "The router could not complete this turn (check LLM_MODEL / API key configuration). Please retry.",
        )
    finally:
        _charge(user_id, usage, "chat")
    if not result.get("agent_name"):
        boss_memory.remember(user_id, req.message, result.get("reply"))
    return RouteResponse(agent_name=result.get("agent_name"), reply=result.get("reply"))


@router.post("/chat/warm")
@limiter.limit("6/minute")
def chat_warm(request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    """A voice conversation has opened: do the slow first-turn work now, in the
    background, while Boss is still greeting (the learner's context and memory,
    the agent registry, the connection to the model). Returns at once."""
    def work() -> None:
        try:
            _learner_context(user_id)
            registry_service.list_healthy()
        except Exception:
            logger.info("chat warm-up: context not ready", exc_info=True)
        llm_client.warm_up()

    threading.Thread(target=work, name="chat-warm", daemon=True).start()
    return {"ok": True}


@router.post("/chat/assist/stream")
@limiter.limit("12/minute")
async def chat_assist_stream(req: assist.AssistRequest, request: Request,
                             user_id: str = Depends(get_verified_user_id)) -> StreamingResponse:
    """Boss guiding a learner on any screen, with an optional screenshot of it.
    Sizes only are logged: the question and the screen can hold personal data."""
    if not req.screenshot_ok():
        raise HTTPException(status_code=422, detail="The screenshot must be a JPEG, PNG or WebP image.")
    logger.info("=== POST /chat/assist/stream user=%s agent=%s message_chars=%d screenshot=%s voice=%s",
                user_id, req.agent_id or "-", len(req.message), bool(req.screenshot), req.voice)
    require_english(req.message)
    _require_points(user_id)

    # The signed-in learner's own profile, progress and chats -- looked up by
    # the verified user id only, so Boss can never see another learner's.
    learner = await run_in_threadpool(_learner_context, user_id, req.message)
    progress = await _own_progress(user_id)
    chats = await run_in_threadpool(_own_chats, user_id)
    certificates = await run_in_threadpool(_own_certificates, user_id, req)

    def events():
        usage: dict[str, int] = {}
        try:
            for event in assist.stream_assist(req, learner, progress, chats, certificates, usage):
                if "action" in event:
                    event = {"action": _link_action(user_id, event["action"], certificates)}
                    if event["action"] is None:
                        continue
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("assist turn failed")
            yield 'data: {"error": "Boss could not answer just now. Please try again."}\n\n'
        finally:
            _charge(user_id, usage, "assist")

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
    require_english(req.message)
    _require_points(user_id)
    context = _learner_context(user_id, req.message)
    history = [turn.model_dump() for turn in req.history]

    def events():
        usage: dict[str, int] = {}
        try:
            for event in route_message_stream(req.message, history, context, voice=req.voice, usage=usage):
                if event.get("done") and not event.get("agent_name"):
                    boss_memory.remember(user_id, req.message, event.get("reply"))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:
            logger.exception("streamed router turn failed")
            yield 'data: {"error": "The router could not complete this turn. Please retry."}\n\n'
        finally:
            _charge(user_id, usage, "chat")

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
    remembered = boss_memory.recall(user_id, question)
    if remembered:
        context = {**(context or {}), "conversation_memory": remembered}
    return context or None


async def _own_progress(user_id: str) -> list[dict] | None:
    """The learner's Job Readiness areas, read from every agent when the last
    reading is older than a few minutes; None when it cannot be read."""
    from app.readiness import service as readiness_service  # local import: readiness pulls in the A2A client

    try:
        user = await run_in_threadpool(auth_service.get_by_id, user_id)
        if user is None:
            return None
        result = await readiness_service.get(user)
    except Exception:
        logger.warning("assist: readiness unavailable", exc_info=True)
        return None
    return [area for area in result.get("areas") or [] if isinstance(area, dict)]


def _own_certificates(user_id: str, req: assist.AssistRequest) -> list[dict] | None:
    """The learner's own certificates, looked up only when the question (or
    the turn before it) is about certificates; None when not looked up."""
    recent = " ".join([req.message] + [turn.content for turn in req.history[-2:]])
    if not assist.CERTIFICATE_WORDS.search(recent):
        return None
    user = auth_service.get_by_id(user_id)
    if user is None:
        return None
    try:
        return links_service.own_certificates(user)
    except links_service.LinkError:
        logger.info("assist: certificates unavailable", exc_info=True)
        return None


def _link_action(user_id: str, action: dict, certificates: list[dict] | None) -> dict | None:
    """Boss's action for the browser. Sharing a chat or a certificate becomes
    the link itself, made here for the signed-in learner only."""
    try:
        if action.get("type") == "share":
            return {"type": "link", **links_service.create_chat_link(user_id, action["chat_id"], action["mode"])}
        if action.get("type") == "certificate":
            cert = next((c for c in certificates or [] if c.get("id") == action["cert_id"]), {})
            title = str(cert.get("topic") or "")
            return {"type": "link", **links_service.create_certificate_link(user_id, action["cert_id"], title)}
    except links_service.LinkError:
        logger.info("assist: link not made", exc_info=True)
        return None
    return action


def _own_chats(user_id: str) -> list[dict]:
    """The learner's own saved chats, newest first: id, agent, title, last used."""
    from app import db
    from app.models import Conversation

    session = db.get_session()
    try:
        rows = (session.query(Conversation.id, Conversation.agent_id, Conversation.title, Conversation.updated_at_ms)
                .filter(Conversation.user_id == user_id, Conversation.deleted_at.is_(None))
                .order_by(Conversation.updated_at_ms.desc()).limit(assist.CHAT_LIMIT).all())
    except Exception:
        logger.warning("assist: chat list unavailable", exc_info=True)
        return []
    finally:
        session.close()
    return [{"id": row.id, "agent": row.agent_id, "title": str(row.title or "")[:120], "last_used": _when(row.updated_at_ms)}
            for row in rows]


def _when(ms) -> str:
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat(timespec="minutes")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


class TranscribeRequest(BaseModel):
    audio_base64: str = Field(min_length=1, max_length=speech.MAX_AUDIO_BASE64_CHARS)
    mime_type: str = Field(default="audio/webm", max_length=64)
    # "auto" (detect), "en" or "ta".
    language: str = Field(default="auto", max_length=8)


# Each call is a paid OpenAI request with up to a few minutes of audio.
# The microphone also sends the recording so far every few seconds, so the
# learner sees their words appear while they speak.
_TRANSCRIBE_RATE_LIMIT = "60/minute"


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

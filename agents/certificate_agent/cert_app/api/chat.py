import json
import time
from collections import defaultdict
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from cert_app.schemas.chat import StartChatRequest, SendMessageRequest
from cert_app.services.auth_service import verify_token
from cert_app.db import chat_repository
from cert_app.services import chat_orchestrator
from cert_app.services.chat_orchestrator import _sanitize_message_for_client
from cert_app.services.exam_service import ensure_certificate_for_completed_chat_session

router = APIRouter()
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


# ── In-Memory Rate Limiter ───────────────────────────────────────────────────
# NOTE: This in-memory sliding window rate limiter tracks per-user request timestamps.
# WARNING: This in-memory implementation does NOT work across multiple server processes
# or load-balanced nodes. Move this rate limiting state to Redis before production scaling.

class InMemoryRateLimiter:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        # Clean up timestamps older than sliding window
        self.user_requests[user_id] = [t for t in self.user_requests[user_id] if t > cutoff]
        
        if len(self.user_requests[user_id]) >= self.max_requests:
            return False
        
        self.user_requests[user_id].append(now)
        return True

    def reset(self):
        self.user_requests.clear()


rate_limiter = InMemoryRateLimiter(max_requests=20, window_seconds=60)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/sessions")
def get_user_chat_sessions(user: dict = Depends(get_current_user)):
    """Retrieve all past conversation sessions for the authenticated user."""
    user_id = int(user["sub"])
    return chat_repository.get_user_sessions(user_id)


@router.post("/start")
def start_chat(
    request: StartChatRequest = StartChatRequest(),
    user: dict = Depends(get_current_user)
):
    """Start a new conversational exam session."""
    user_id = int(user["sub"])
    topic = (request.topic or "").strip()
    session_id = chat_repository.create_session(user_id=user_id, topic=topic)
    return {"session_id": session_id}


@router.post("/message")
def send_chat_message(
    request: SendMessageRequest,
    user: dict = Depends(get_current_user)
):
    """
    Send a message to an active chat session and stream SSE response events back to client.
    Enforces user rate limits and session ownership security.
    """
    user_id_str = str(user["sub"])

    # 1. Rate Limiting Check (Max 20 req/min)
    if not rate_limiter.is_allowed(user_id_str):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Maximum 20 requests per minute."
        )

    # 2. Session Ownership Check (HTTP 403 if unauthorized)
    session = chat_repository.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session["user_id"]) != user_id_str:
        raise HTTPException(status_code=403, detail="Access denied. Session belongs to another user.")

    # 3. Handle Message & Stream SSE Events
    def sse_event_generator():
        try:
            turn_result = chat_orchestrator.handle_message(request.session_id, request.message)
            
            # Emit individual message events
            for msg in turn_result.messages:
                event_payload = json.dumps(msg)
                yield f"event: message\ndata: {event_payload}\n\n"

            # Emit final turn status event
            status_payload = json.dumps({
                "session_status": turn_result.session_status,
                "current_question_index": turn_result.current_question_index,
                "total_questions": turn_result.total_questions,
                "score_percentage": turn_result.score_percentage,
                "passed": turn_result.passed,
                "is_final": True
            })
            yield f"event: status\ndata: {status_payload}\n\n"

        except Exception as e:
            error_payload = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_payload}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


@router.get("/session/{session_id}")
def get_chat_session(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Retrieve full session details and sanitized message history for reconnect/resume.
    Enforces session ownership security.
    """
    user_id_str = str(user["sub"])
    session = chat_repository.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if str(session["user_id"]) != user_id_str:
        raise HTTPException(status_code=403, detail="Access denied. Session belongs to another user.")

    raw_history = chat_repository.get_message_history(session_id)
    clean_history = [_sanitize_message_for_client(msg) for msg in raw_history]

    return {
        "session": session,
        "messages": clean_history
    }


@router.post("/session/{session_id}/certificate")
def recover_chat_certificate(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    """Issue/retrieve the certificate for an already-passed chat exam."""
    try:
        return ensure_certificate_for_completed_chat_session(session_id, int(user["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

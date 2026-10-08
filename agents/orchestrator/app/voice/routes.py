"""Voice API: natural speech for every agent (Phase 2)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.auth import service as auth_service
from app.auth.verified import get_verified_user_id
from app.rate_limit import limiter
from app.voice import tts

router = APIRouter(prefix="/voice", tags=["voice"])

# Points charged per character spoken, as tokens (the same unit the agents
# report). A cached repeat is free. Set to 0 to make voice free.
VOICE_TOKENS_PER_CHAR = int(os.environ.get("VOICE_TOKENS_PER_CHAR", "1"))
# A reply is spoken a sentence or two per request, so a long answer is
# several requests; this still stops a runaway client.
_SPEAK_RATE_LIMIT = "120/minute"


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=tts.MAX_TEXT_CHARS)
    language: str = "auto"
    persona: str = tts.DEFAULT_PERSONA


@router.get("/personas")
def personas() -> dict:
    return {
        "default": tts.DEFAULT_PERSONA,
        "personas": [{"id": key, "label": p["label"], "description": p["description"]} for key, p in tts.PERSONAS.items()],
        "languages": [
            {"id": "auto", "label": "Automatic"}, {"id": "en", "label": "English"}, {"id": "ta", "label": "தமிழ் (Tamil)"},
        ],
    }


@router.post("/speak")
@limiter.limit(_SPEAK_RATE_LIMIT)
async def speak(req: SpeakRequest, request: Request, user_id: str = Depends(get_verified_user_id)) -> Response:
    user = auth_service.get_by_id(user_id)
    if VOICE_TOKENS_PER_CHAR and user is not None and user.token_balance <= 0:
        raise HTTPException(402, "Not enough points. Please top up to continue.")
    try:
        audio, spoken_as, from_cache = await run_in_threadpool(tts.synthesize, req.text, req.language, req.persona)
    except tts.VoiceError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    if VOICE_TOKENS_PER_CHAR and not from_cache:
        auth_service.settle_tokens(user_id, len(req.text) * VOICE_TOKENS_PER_CHAR, "voice", "speak")
    return Response(
        content=audio, media_type="audio/mpeg",
        headers={"X-Voice-Language": spoken_as, "Cache-Control": "private, max-age=3600"},
    )

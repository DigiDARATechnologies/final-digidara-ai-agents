"""Neural Text-to-Speech (TTS) Service.

Provides studio-quality neural voice synthesis using OpenAI's TTS engine (tts-1),
delivering human-like intonation, natural pauses, and conversational warmth.
Caches generated audio in-memory/TTL to eliminate redundant costs and latency.
"""

import hashlib
import io
import logging
from typing import Optional, Tuple

import httpx
from flask import current_app

from .cache_service import get_cached, set_cached

logger = logging.getLogger(__name__)

# Preferred natural female voices for English coaching
# 'nova': energetic, bright, highly articulate tutor
# 'shimmer': gentle, warm, patient English coach
DEFAULT_VOICE = "nova"
DEFAULT_SPEED = 0.92  # Natural ESL pacing


def _clean_speech_text(text: str) -> str:
    """Prepare text for optimal neural delivery with natural breath pauses."""
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    # Ensure natural comma pause after salutation
    import re
    cleaned = re.replace if hasattr(re, "replace") else re.sub
    cleaned = re.sub(
        r"^(Good\s+(?:morning|afternoon|evening)|Hello|Hi|Hey)\s+([A-Z][a-zA-Z]+)(?=[,\s.!?]|$)",
        r"\1, \2.",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Ensure proper question mark
    if re.search(r"^(what|how|why|when|where|who|which|can|could|would|are|is|do|did|have|has)\b", cleaned, re.IGNORECASE) and not re.search(r"[.!?]$", cleaned):
        cleaned = f"{cleaned}?"
    elif not re.search(r"[.!?]$", cleaned):
        cleaned = f"{cleaned}."
    return cleaned


def synthesize_neural_speech(
    text: str,
    voice: str = DEFAULT_VOICE,
    speed: float = DEFAULT_SPEED,
) -> Tuple[Optional[bytes], str]:
    """Synthesize speech using OpenAI Neural TTS (tts-1).

    Returns:
        (audio_bytes, mime_type) or (None, "") on failure.
    """
    cleaned = _clean_speech_text(text)
    if not cleaned:
        return None, ""

    # Check cache first
    cache_key = hashlib.sha256(f"{voice}:{speed}:{cleaned}".encode("utf-8")).hexdigest()
    cached_audio = get_cached("neural_tts", cache_key)
    if cached_audio:
        return cached_audio, "audio/mpeg"

    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key or not str(api_key).startswith("sk-"):
        # Fall back to environment variable directly
        import os
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key or not str(api_key).startswith("sk-"):
        logger.warning("Neural TTS: OPENAI_API_KEY not configured or invalid sk- key.")
        return None, ""

    endpoint = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "tts-1",
        "input": cleaned[:4096],
        "voice": voice if voice in {"nova", "shimmer", "alloy", "echo", "fable", "onyx"} else DEFAULT_VOICE,
        "response_format": "mp3",
        "speed": max(0.25, min(4.0, float(speed))),
    }

    try:
        response = httpx.post(endpoint, headers=headers, json=payload, timeout=12.0)
        if response.status_code == 200:
            audio_bytes = response.content
            # Cache synthesized audio for 24 hours
            set_cached("neural_tts", audio_bytes, ttl_seconds=86400, key=cache_key)
            return audio_bytes, "audio/mpeg"
        logger.error("Neural TTS request failed: %s %s", response.status_code, response.text)
        return None, ""
    except Exception as exc:
        logger.exception("Neural TTS synthesis error: %s", exc)
        return None, ""

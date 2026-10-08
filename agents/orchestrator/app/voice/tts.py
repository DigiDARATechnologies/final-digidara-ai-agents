"""Natural, friendly speech for every agent, in English, Tamil, or both.

One place turns agent text into speech: OpenAI's steerable TTS model, told
how to sound (a warm coach, natural spoken Tamil, relaxed pace) instead of a
flat reading voice. The browser asks for one or two sentences at a time and
plays them back to back, so speech starts after the first sentence instead
of after the whole reply. Recent results are cached, so a repeated prompt
(an interview question read again) costs nothing.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
from collections import OrderedDict

import httpx

logger = logging.getLogger("orchestrator.voice")

OPENAI_SPEECH_URL = "https://api.openai.com/v1/audio/speech"
TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
TTS_TIMEOUT_SECONDS = 30
MAX_TEXT_CHARS = 1200
CACHE_ENTRIES = 300

# Persona id -> OpenAI voice and how it is described to learners.
PERSONAS: dict[str, dict[str, str]] = {
    "nila": {"voice": "coral", "label": "Nila", "description": "Warm, cheerful coach"},
    "arjun": {"voice": "ash", "label": "Arjun", "description": "Friendly, encouraging mentor"},
    "meera": {"voice": "sage", "label": "Meera", "description": "Calm, patient guide"},
    "kavin": {"voice": "verse", "label": "Kavin", "description": "Energetic study buddy"},
}
DEFAULT_PERSONA = "nila"
LANGUAGES = ("auto", "en", "ta")

_BASE_STYLE = (
    "You are a warm, friendly learning coach talking with a student in India. Sound like a supportive "
    "friend who is genuinely happy to help: relaxed and natural, a smile in the voice, gentle emphasis on "
    "the important words, short natural pauses between sentences. Never sound robotic, rushed or like a "
    "news reader. Read numbers, scores and technical terms clearly."
)
_LANGUAGE_STYLE = {
    "en": "Speak clear, natural English with a light, friendly Indian accent.",
    "ta": (
        "The text is Tamil. Speak natural, everyday spoken Tamil with a neutral Tamil Nadu accent, the way a "
        "friendly teacher talks, not stiff formal written Tamil. Say English technical words such as Python, "
        "SQL, interview or resume the way Tamil speakers naturally say them."
    ),
    "mixed": (
        "The text mixes Tamil and English. Switch between them smoothly, exactly as bilingual Tamil speakers "
        "do in everyday conversation: Tamil sentences in natural spoken Tamil, English words and phrases in "
        "clear Indian English."
    ),
}

_TAMIL = re.compile(r"[஀-௿]")
_LETTER = re.compile(r"[A-Za-z஀-௿]")


class VoiceError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def detect_language(text: str) -> str:
    """"ta", "mixed" or "en", from how much of the text is Tamil script."""
    letters = len(_LETTER.findall(text))
    if not letters:
        return "en"
    share = len(_TAMIL.findall(text)) / letters
    if share >= 0.6:
        return "ta"
    if share >= 0.1:
        return "mixed"
    return "en"


def instructions_for(language: str) -> str:
    return f"{_BASE_STYLE} {_LANGUAGE_STYLE.get(language, _LANGUAGE_STYLE['en'])}"


_cache: OrderedDict[str, bytes] = OrderedDict()
_cache_lock = threading.Lock()


def _cache_key(text: str, language: str, voice: str) -> str:
    return hashlib.sha256(f"{TTS_MODEL}|{voice}|{language}|{text}".encode()).hexdigest()


def cached(text: str, language: str, persona: str) -> bytes | None:
    voice = PERSONAS.get(persona, PERSONAS[DEFAULT_PERSONA])["voice"]
    with _cache_lock:
        key = _cache_key(text, language, voice)
        audio = _cache.get(key)
        if audio is not None:
            _cache.move_to_end(key)
        return audio


def resolve_language(text: str, requested: str) -> str:
    """The learner's chosen language wins when the text is in that script;
    otherwise the text itself decides (an English reply is never read as Tamil)."""
    detected = detect_language(text)
    if requested == "ta" and detected != "en":
        return "ta" if detected == "ta" else "mixed"
    return detected


def synthesize(text: str, language: str = "auto", persona: str = DEFAULT_PERSONA) -> tuple[bytes, str, bool]:
    """(mp3 bytes, the language it was spoken as, whether it came from cache)."""
    text = " ".join(text.split())
    if not text:
        raise VoiceError(400, "There is no text to speak.")
    if len(text) > MAX_TEXT_CHARS:
        raise VoiceError(413, f"Send at most {MAX_TEXT_CHARS} characters at a time.")
    persona = persona if persona in PERSONAS else DEFAULT_PERSONA
    spoken_as = resolve_language(text, language if language in LANGUAGES else "auto")
    hit = cached(text, spoken_as, persona)
    if hit is not None:
        return hit, spoken_as, True
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise VoiceError(503, "Natural voice is not available right now.")
    voice = PERSONAS[persona]["voice"]
    try:
        response = httpx.post(
            OPENAI_SPEECH_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": TTS_MODEL, "voice": voice, "input": text,
                "instructions": instructions_for(spoken_as), "response_format": "mp3",
            },
            timeout=TTS_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        logger.warning("tts request failed: %s", type(exc).__name__)
        raise VoiceError(502, "The voice could not be generated. Please try again.") from exc
    if response.status_code != 200 or not response.content:
        # Status only: the error body can echo the request.
        logger.warning("tts returned HTTP %s", response.status_code)
        raise VoiceError(502, "The voice could not be generated. Please try again.")
    audio = response.content
    with _cache_lock:
        _cache[_cache_key(text, spoken_as, voice)] = audio
        while len(_cache) > CACHE_ENTRIES:
            _cache.popitem(last=False)
    logger.info("tts %d chars as %s with %s -> %d bytes", len(text), spoken_as, persona, len(audio))
    return audio, spoken_as, False

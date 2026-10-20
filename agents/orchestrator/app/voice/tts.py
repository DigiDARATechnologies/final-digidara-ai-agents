"""Natural, friendly speech for every agent, in English, Tamil, or both.

One place turns agent text into speech: OpenAI's steerable TTS model, with
one fixed voice (Nila, a friendly Indian teacher) told how to sound -- slow,
simple and clear enough for any student -- instead of a flat reading voice. The browser asks for one or two sentences at a time and
plays them back to back, so speech starts after the first sentence instead
of after the whole reply. Recent results are cached -- in this process and,
when Redis is configured, shared by every worker -- so a repeated prompt (an
interview question read again) is instant and costs nothing.
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
# OpenAI's speech endpoint now and then stalls for half a minute or more
# before its first byte, while a fresh request for the same text answers in
# about a second. So a request that has sent nothing for this long is given up
# and sent again, instead of leaving the learner in silence.
TTS_STALL_SECONDS = 6
TTS_TIMEOUT = httpx.Timeout(TTS_TIMEOUT_SECONDS, read=TTS_STALL_SECONDS)
MAX_TEXT_CHARS = 1200
CACHE_ENTRIES = 300
# The shared cache: the rate limiter's Redis unless VOICE_CACHE_URI says
# otherwise. Sentence-sized audio only, kept half a day.
SHARED_CACHE_SECONDS = 12 * 3600
SHARED_CACHE_MAX_CHARS = 400

# One voice for the whole platform: every agent, every device, every reply is
# the same Indian woman, so learners always hear one familiar character.
# A persona sent by an older client is accepted but always mapped to her.
VOICE = os.environ.get("OPENAI_TTS_VOICE", "nova")
PERSONAS: dict[str, dict[str, str]] = {
    "nila": {"voice": VOICE, "label": "Nila", "description": "Friendly Indian coach"},
}
DEFAULT_PERSONA = "nila"
LANGUAGES = ("auto", "en", "ta")

_BASE_STYLE = (
    "Voice: Nila, a friendly young Indian woman from Chennai who teaches students. Always the same person, "
    "the same sweet, bright voice and the same accent. Speak loudly and clearly with a bright, slightly higher, "
    "sweet tone -- a full, confident, projected voice that is easy to hear in a classroom, never soft, low or "
    "mumbled. Speak slowly, like a patient teacher talking to a ten-year-old student: simple, every word easy "
    "to catch, a short pause after each sentence. Cheerful and encouraging, a big smile in the voice. Never "
    "rushed, never robotic, never like a news reader. Say numbers, scores and technical terms slowly and clearly."
)
_LANGUAGE_STYLE = {
    "en": (
        "Speak simple, clear Indian English with a natural Indian accent, the way a good teacher in an Indian "
        "school speaks. Not an American or British accent."
    ),
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


# Boss's voice conversation is a quick back-and-forth, not a lesson: the same
# voice and accent, said at a brisk conversational pace (speeding the slow
# teacher voice up in the player instead blurs the words).
PACES = ("normal", "brisk")
_BRISK_STYLE = (
    "Voice: Nila, a friendly young Indian woman from Chennai. Always the same person, the same sweet, bright "
    "voice and the same accent. Speak clearly and confidently at a brisk, natural conversational pace, like a "
    "quick friendly chat: no long pauses, no slow teacher voice, every word still easy to catch. Cheerful, "
    "warm, never rushed into mumbling, never robotic."
)


def instructions_for(language: str, pace: str = "normal") -> str:
    base = _BRISK_STYLE if pace == "brisk" else _BASE_STYLE
    return f"{base} {_LANGUAGE_STYLE.get(language, _LANGUAGE_STYLE['en'])}"


_cache: OrderedDict[str, bytes] = OrderedDict()
_cache_lock = threading.Lock()
_shared_client = None


def _shared():
    """The Redis client for the shared cache, or None when not configured."""
    global _shared_client
    uri = (os.environ.get("VOICE_CACHE_URI") or os.environ.get("RATE_LIMIT_STORAGE_URI") or "").strip()
    if not uri.startswith(("redis://", "rediss://")):
        return None
    if _shared_client is None:
        import redis

        _shared_client = redis.Redis.from_url(uri, socket_timeout=0.5, socket_connect_timeout=0.5)
    return _shared_client


def _cache_key(text: str, language: str, voice: str, pace: str = "normal") -> str:
    # The style is part of the key: a changed voice never replays old audio.
    style = hashlib.sha256(instructions_for(language, pace).encode()).hexdigest()[:12]
    return hashlib.sha256(f"{TTS_MODEL}|{voice}|{style}|{language}|{text}".encode()).hexdigest()


def _remember(key: str, audio: bytes, text: str) -> None:
    with _cache_lock:
        _cache[key] = audio
        while len(_cache) > CACHE_ENTRIES:
            _cache.popitem(last=False)
    client = _shared()
    if client is not None and len(text) <= SHARED_CACHE_MAX_CHARS:
        try:
            client.setex(f"voice:{key}", SHARED_CACHE_SECONDS, audio)
        except Exception:
            logger.warning("voice shared cache write failed", exc_info=True)


def cached(text: str, language: str, persona: str, pace: str = "normal") -> bytes | None:
    key = _cache_key(text, language, VOICE, pace)
    with _cache_lock:
        audio = _cache.get(key)
        if audio is not None:
            _cache.move_to_end(key)
            return audio
    client = _shared()
    if client is None:
        return None
    try:
        audio = client.get(f"voice:{key}")
    except Exception:
        logger.warning("voice shared cache read failed", exc_info=True)
        return None
    if audio:
        with _cache_lock:
            _cache[key] = audio
        return audio
    return None


def resolve_language(text: str, requested: str) -> str:
    """The learner's chosen language wins when the text is in that script;
    otherwise the text itself decides (an English reply is never read as Tamil)."""
    detected = detect_language(text)
    if requested == "ta" and detected != "en":
        return "ta" if detected == "ta" else "mixed"
    return detected


def synthesize(text: str, language: str = "auto", persona: str = DEFAULT_PERSONA, pace: str = "normal") -> tuple[bytes, str, bool]:
    """(mp3 bytes, the language it was spoken as, whether it came from cache)."""
    text = " ".join(text.split())
    if not text:
        raise VoiceError(400, "There is no text to speak.")
    if len(text) > MAX_TEXT_CHARS:
        raise VoiceError(413, f"Send at most {MAX_TEXT_CHARS} characters at a time.")
    persona = DEFAULT_PERSONA
    pace = pace if pace in PACES else "normal"
    spoken_as = resolve_language(text, language if language in LANGUAGES else "auto")
    hit = cached(text, spoken_as, persona, pace)
    if hit is not None:
        return hit, spoken_as, True
    voice = VOICE
    response, first, rest = _hedged_open(text, spoken_as, pace)
    try:
        audio = first + b"".join(rest)
    except httpx.HTTPError as exc:
        logger.warning("tts response broke off: %s", type(exc).__name__)
        raise VoiceError(502, "The voice could not be generated. Please try again.") from exc
    finally:
        response.close()
    _remember(_cache_key(text, spoken_as, voice, pace), audio, text)
    logger.info("tts %d chars as %s with %s -> %d bytes", len(text), spoken_as, persona, len(audio))
    return audio, spoken_as, False


# --- Streaming: the browser plays the voice while it is still being made ----
#
# An <audio> element plays an mp3 as it downloads, so the first words are
# heard about as soon as OpenAI starts sending them, instead of after the
# whole sentence has been generated. An <audio> element cannot send the login
# header, so the browser first asks for a ticket (authenticated, and charged
# there), then plays /voice/stream/<ticket>: single use, valid a few minutes.

TICKET_SECONDS = 180
_tickets: dict[str, tuple[float, dict]] = {}
_tickets_lock = threading.Lock()


def prepare(text: str, language: str = "auto") -> tuple[str, str]:
    """(normalised text, the language it will be spoken as), or VoiceError."""
    text = " ".join(text.split())
    if not text:
        raise VoiceError(400, "There is no text to speak.")
    if len(text) > MAX_TEXT_CHARS:
        raise VoiceError(413, f"Send at most {MAX_TEXT_CHARS} characters at a time.")
    return text, resolve_language(text, language if language in LANGUAGES else "auto")


def issue_ticket(text: str, spoken_as: str, pace: str = "normal") -> str:
    import secrets
    import json as _json
    import time as _time

    ticket = secrets.token_urlsafe(24)
    data = {"text": text, "language": spoken_as, "pace": pace if pace in PACES else "normal"}
    client = _shared()
    if client is not None:
        try:
            client.setex(f"voice-ticket:{ticket}", TICKET_SECONDS, _json.dumps(data))
            return ticket
        except Exception:
            logger.warning("voice ticket shared write failed", exc_info=True)
    now = _time.time()
    with _tickets_lock:
        for key in [key for key, (expires, _) in _tickets.items() if expires < now]:
            del _tickets[key]
        _tickets[ticket] = (now + TICKET_SECONDS, data)
    return ticket


def take_ticket(ticket: str) -> dict | None:
    """The ticket's text, once; None if unknown, used or expired."""
    import json as _json
    import time as _time

    client = _shared()
    if client is not None:
        try:
            raw = client.getdel(f"voice-ticket:{ticket}")
            if raw:
                return _json.loads(raw)
        except Exception:
            logger.warning("voice ticket shared read failed", exc_info=True)
    with _tickets_lock:
        entry = _tickets.pop(ticket, None)
    if entry is None or entry[0] < _time.time():
        return None
    return entry[1]


_openai_client: httpx.Client | None = None


def _openai() -> httpx.Client:
    """One kept-alive connection pool to OpenAI for every voice request, so a
    sentence does not pay for a new TLS handshake (a few hundred ms)."""
    global _openai_client
    if _openai_client is None:
        _openai_client = httpx.Client(timeout=TTS_TIMEOUT, limits=httpx.Limits(max_keepalive_connections=8))
    return _openai_client


# OpenAI's gpt-4o-mini-tts answers most voice requests in about 1 s, but 30-60%
# of them (measured on staging, 2026-10-20) send nothing for 6 s or more, at
# random. Waiting out a stall left the learner in silence while Boss's reply
# or an interview question was already on screen. So every sentence is asked
# for twice at once, again at 1.5 s, and finally from tts-1 (slower to start
# and without the accent steering, but it has not been seen to stall); the
# first to send audio is played and the rest are closed.
HEDGE_SCHEDULE: tuple[tuple[float, str], ...] = ((0.0, TTS_MODEL), (0.0, TTS_MODEL), (1.5, TTS_MODEL), (3.0, "tts-1"))
HEDGE_DEADLINE_SECONDS = 20.0


def _hedged_open(text: str, spoken_as: str, pace: str):
    """(open response, its first mp3 chunk, the rest as an iterator) from the
    first of the HEDGE_SCHEDULE requests to send audio, or VoiceError."""
    import queue as _queue
    import time as _time

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise VoiceError(503, "Natural voice is not available right now.")
    client = _openai()
    results: _queue.Queue = _queue.Queue()
    lock = threading.Lock()
    state = {"won": False}

    def attempt(number: int, model: str) -> None:
        payload = {"model": model, "voice": VOICE, "input": text, "response_format": "mp3"}
        if model != "tts-1":  # tts-1 takes no style instructions
            payload["instructions"] = instructions_for(spoken_as, pace)
        response = None
        try:
            request = client.build_request(
                "POST", OPENAI_SPEECH_URL, headers={"Authorization": f"Bearer {api_key}"}, json=payload,
            )
            response = client.send(request, stream=True)
            if response.status_code != 200:
                # Status only: the error body can echo the request.
                logger.warning("tts returned HTTP %s (request %d)", response.status_code, number)
                response.close()
                results.put(("error", number))
                return
            rest = response.iter_bytes(4096)
            first = next(rest, b"")
            with lock:
                won = not state["won"] and bool(first)
                if won:
                    state["won"] = True
            if won:
                results.put(("ok", (response, first, rest, number)))
            else:
                response.close()
                results.put(("error", number))
        except (httpx.HTTPError, OSError) as exc:
            if not state["won"]:
                logger.warning("tts request %d (%s) stalled or failed: %s", number, model, type(exc).__name__)
            if response is not None:
                response.close()
            results.put(("error", number))

    started = _time.monotonic()
    launched = failed = 0
    total = len(HEDGE_SCHEDULE)
    while True:
        elapsed = _time.monotonic() - started
        # Launch every request whose time has come, or the next one at once
        # when everything sent so far has already failed.
        while launched < total and (HEDGE_SCHEDULE[launched][0] <= elapsed or failed == launched):
            launched += 1
            threading.Thread(target=attempt, args=(launched, HEDGE_SCHEDULE[launched - 1][1]), daemon=True).start()
        remaining = HEDGE_DEADLINE_SECONDS - elapsed
        if remaining <= 0 or failed == total:
            raise VoiceError(502, "The voice could not be generated. Please try again.")
        until_next = HEDGE_SCHEDULE[launched][0] - elapsed if launched < total else remaining
        try:
            kind, value = results.get(timeout=max(0.05, min(remaining, until_next)))
        except _queue.Empty:
            continue
        if kind == "ok":
            response, first, rest, number = value
            if number > 2:
                logger.info("tts hedged: request %d (%s) answered first after %.2fs", number, HEDGE_SCHEDULE[number - 1][1], _time.monotonic() - started)
            return response, first, rest
        failed += 1


def open_stream(text: str, spoken_as: str, pace: str = "normal"):
    """An iterator of mp3 bytes as OpenAI produces them (cached once complete),
    or VoiceError before any byte is sent."""
    response, first, rest = _hedged_open(text, spoken_as, pace)

    def chunks():
        parts: list[bytes] = [first]
        complete = False
        try:
            yield first
            for chunk in rest:
                parts.append(chunk)
                yield chunk
            complete = True
        except httpx.HTTPError:
            logger.warning("tts stream broke off", exc_info=True)
        finally:
            response.close()
            if complete and parts:
                audio = b"".join(parts)
                _remember(_cache_key(text, spoken_as, VOICE, pace), audio, text)
                logger.info("tts streamed %d chars as %s -> %d bytes", len(text), spoken_as, len(audio))

    return chunks()

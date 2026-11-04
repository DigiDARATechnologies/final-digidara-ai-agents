"""Speech to text for the general chat's microphone, with OpenAI.

The browser records the question and posts it as base64; this sends it to
OpenAI's transcription API and returns the text, which then goes through the
general chat exactly as if it had been typed (same limits, same guards).
Neither the audio nor the transcript is stored or logged.
"""
from __future__ import annotations

import base64
import binascii
import logging
import os
import time

import httpx

from app.english_only import SPEAK_ENGLISH_MESSAGE, is_english_text

logger = logging.getLogger("orchestrator.transcribe")

OPENAI_TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"
TRANSCRIPTION_MODEL = os.environ.get("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
TRANSCRIPTION_TIMEOUT_SECONDS = 60
# A blip at OpenAI (5xx, a busy-minute 429, a dropped connection) is tried once more.
TRANSIENT_RETRIES = 1
RETRY_DELAY_SECONDS = 1.0
# OpenAI answers 429 with these when the account has no credits; retrying never helps.
QUOTA_CODES = {"insufficient_quota", "credit_balance_exhausted", "billing_hard_limit_reached"}

# A spoken question is seconds long; this is several minutes of compressed
# audio, and well under OpenAI's 25 MB limit.
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_BASE64_CHARS = (MAX_AUDIO_BYTES * 4) // 3 + 4

# What browsers record (MediaRecorder), mapped to the extension OpenAI uses
# to recognise the format. Anything else is refused.
AUDIO_EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/m4a": "m4a",
    "audio/x-m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}

# Helps the model spell the platform's own words right. Only vocabulary --
# never instructions: on silence or a very short recording the model can
# return its prompt as the "transcript", and an instruction would then appear
# in the learner's message box. _is_prompt_echo() removes any echo that remains.
VOCABULARY_HINT = (
    "SkillDARA, Boss, Capstone Project Agent, Coding Practice, CodeForge, Aptitude Trainer, "
    "Mock Interview, Communication Coach, Resume Builder, AI Certification Agent, Job Agent, points, viva, ATS."
)
LANGUAGES = {"auto": None, "en": "en", "ta": "ta"}


class TranscriptionError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def decode_audio(audio_base64: str, mime_type: str) -> tuple[bytes, str]:
    """The audio bytes and file extension, or TranscriptionError(400/413)."""
    base_type = (mime_type or "").split(";", 1)[0].strip().lower()
    extension = AUDIO_EXTENSIONS.get(base_type)
    if extension is None:
        raise TranscriptionError(400, "Unsupported audio format.")
    if len(audio_base64) > MAX_AUDIO_BASE64_CHARS:
        raise TranscriptionError(413, "That recording is too long. Please ask a shorter question.")
    try:
        audio = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise TranscriptionError(400, "The recording could not be read.") from exc
    if not audio:
        raise TranscriptionError(400, "The recording is empty.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise TranscriptionError(413, "That recording is too long. Please ask a shorter question.")
    return audio, extension


def transcribe(audio_base64: str, mime_type: str, language: str = "auto") -> str:
    audio, extension = decode_audio(audio_base64, mime_type)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise TranscriptionError(503, "Voice input is not available right now.")
    base_type = (mime_type or "").split(";", 1)[0].strip().lower()
    response = None
    for attempt in range(1 + TRANSIENT_RETRIES):
        if attempt:
            time.sleep(RETRY_DELAY_SECONDS)
        try:
            response = httpx.post(
                OPENAI_TRANSCRIPTIONS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (f"question.{extension}", audio, base_type)},
                data={
                    "model": TRANSCRIPTION_MODEL, "response_format": "json", "temperature": "0",
                    "prompt": VOCABULARY_HINT,
                    # No forced language: speech is written in the language spoken,
                    # so another language is recognised and refused below instead
                    # of coming back empty ("I couldn't hear any words").
                },
                timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            logger.warning("transcription request failed: %s", type(exc).__name__)
            if attempt < TRANSIENT_RETRIES:
                continue
            raise TranscriptionError(502, "Voice input could not be processed. Please try again or type your question.") from exc
        if response.status_code == 200 or not _is_transient(response) or attempt == TRANSIENT_RETRIES:
            break
        logger.warning("transcription returned HTTP %s; retrying once", response.status_code)
    if response.status_code != 200:
        _raise_for_openai_error(response)
    try:
        text = str(response.json().get("text") or "").strip()
    except ValueError as exc:
        raise TranscriptionError(502, "Voice input could not be processed. Please try again or type your question.") from exc
    if _is_prompt_echo(text):
        # Silence or noise came back as the prompt itself: nothing was said.
        logger.info("transcription of %d bytes was the prompt echoed back; treated as silence", len(audio))
        return ""
    if not is_english_text(text):
        # Every agent works in English only.
        logger.info("transcription of %d bytes was not English; asked the learner to speak English", len(audio))
        raise TranscriptionError(422, SPEAK_ENGLISH_MESSAGE)
    logger.info("transcribed %d bytes of %s into %d chars", len(audio), base_type, len(text))
    return text


def _openai_error_code(response) -> str:
    """OpenAI's error code ("insufficient_quota", "audio_too_short", ...) only:
    its message can echo request details."""
    try:
        error = response.json().get("error") or {}
    except (ValueError, AttributeError):
        return ""
    return str(error.get("code") or error.get("type") or "") if isinstance(error, dict) else ""


def _is_transient(response) -> bool:
    return response.status_code >= 500 or (response.status_code == 429 and _openai_error_code(response) not in QUOTA_CODES)


def _raise_for_openai_error(response) -> None:
    code = _openai_error_code(response)
    if code in QUOTA_CODES or response.status_code in (401, 403):
        # Every recording fails until someone fixes the OpenAI account, so it is
        # logged as an error (Boss reports it with its cause) and the learner is
        # told to type instead.
        logger.error("transcription failed: the OpenAI account cannot be used (HTTP %s, %s)", response.status_code, code or "no code")
        raise TranscriptionError(503, "Voice input is not available right now. Please type your question.")
    if response.status_code == 400:
        # The recording itself: too short, cut off, or not audio OpenAI can read.
        logger.info("transcription refused the recording (HTTP 400, %s)", code or "no code")
        raise TranscriptionError(400, "I couldn't hear any words in that recording. Please try again or type your question.")
    logger.warning("transcription returned HTTP %s (%s)", response.status_code, code or "no code")
    raise TranscriptionError(502, "Voice input could not be processed. Please try again or type your question.")


# Phrases of prompts this service sends (and sent before), which the model
# sometimes returns instead of the speech when it hears nothing.
_ECHO_MARKERS = (
    "transcribe only the main speaker", "ignore background voices", "the learner may speak english",
    "a learner asking the digidara", "context: ###", "digidara ai agents, boss, capstone",
    "a learner asking the skilldara", "skilldara, boss, capstone",
)


def _is_prompt_echo(text: str) -> bool:
    """The transcript is (part of) the prompt rather than anything said: a
    known prompt phrase, or six words in a row straight from the vocabulary."""
    lowered = " ".join(text.lower().split())
    if not lowered:
        return False
    if any(marker in lowered for marker in _ECHO_MARKERS):
        return True
    words = [w.strip(".,;:!?") for w in lowered.split()]
    hint = " ".join(w.strip(".,;:!?") for w in VOCABULARY_HINT.lower().split())
    return any(" ".join(words[i:i + 6]) in hint for i in range(0, max(0, len(words) - 5)))

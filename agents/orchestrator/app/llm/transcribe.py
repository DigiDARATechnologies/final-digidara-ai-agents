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

import httpx

logger = logging.getLogger("orchestrator.transcribe")

OPENAI_TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"
TRANSCRIPTION_MODEL = os.environ.get("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
TRANSCRIPTION_TIMEOUT_SECONDS = 60

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
    "DigiDARA AI Agents, Boss, Capstone Project Agent, Coding Practice, CodeForge, Aptitude Trainer, "
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
    try:
        response = httpx.post(
            OPENAI_TRANSCRIPTIONS_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (f"question.{extension}", audio, base_type)},
            data={
                "model": TRANSCRIPTION_MODEL, "response_format": "json", "temperature": "0",
                "prompt": VOCABULARY_HINT,
                # Every agent works in English: the speech is always written as English.
                "language": "en",
            },
            timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        logger.warning("transcription request failed: %s", type(exc).__name__)
        raise TranscriptionError(502, "Voice input could not be processed. Please try again or type your question.") from exc
    if response.status_code != 200:
        # Status only: OpenAI's error body can echo request details.
        logger.warning("transcription returned HTTP %s", response.status_code)
        raise TranscriptionError(502, "Voice input could not be processed. Please try again or type your question.")
    try:
        text = str(response.json().get("text") or "").strip()
    except ValueError as exc:
        raise TranscriptionError(502, "Voice input could not be processed. Please try again or type your question.") from exc
    if _is_prompt_echo(text):
        # Silence or noise came back as the prompt itself: nothing was said.
        logger.info("transcription of %d bytes was the prompt echoed back; treated as silence", len(audio))
        return ""
    logger.info("transcribed %d bytes of %s into %d chars", len(audio), base_type, len(text))
    return text


# Phrases of prompts this service sends (and sent before), which the model
# sometimes returns instead of the speech when it hears nothing.
_ECHO_MARKERS = (
    "transcribe only the main speaker", "ignore background voices", "the learner may speak english",
    "a learner asking the digidara", "context: ###", "digidara ai agents, boss, capstone",
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

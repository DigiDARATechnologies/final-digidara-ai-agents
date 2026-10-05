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

# Helps the model spell the platform's own words right.
VOCABULARY_HINT = (
    "A learner asking the DigiDARA AI Agents assistant about its agents: Capstone Project Agent, "
    "LeetCode Agent, CodeForge, Aptitude Trainer, Mock Interview, Communication Coach, Resume Builder, "
    "AI Certification Agent, Job Fetching Agent, points, viva, ATS."
)


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


def transcribe(audio_base64: str, mime_type: str) -> str:
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
            data={"model": TRANSCRIPTION_MODEL, "response_format": "json", "temperature": "0", "prompt": VOCABULARY_HINT},
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
    logger.info("transcribed %d bytes of %s into %d chars", len(audio), base_type, len(text))
    return text

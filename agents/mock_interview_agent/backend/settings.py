"""Environment-backed application settings shared by route modules."""

import os
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:5173"
    ).split(",")
    if origin.strip()
]
MAX_AUDIO_UPLOAD_BYTES = (
    int(os.environ.get("MAX_AUDIO_UPLOAD_MB", "10")) * 1024 * 1024
)
ALLOWED_QUESTION_COUNTS = {5, 10}
MAX_SUBJECT_LENGTH = 150
DAILY_ANSWER_LIMIT = 10
DAILY_LIMIT_ENABLED = os.environ.get(
    "DAILY_LIMIT_ENABLED", "false"
).strip().lower() in {"1", "true", "yes", "on"}
DAILY_QUOTA_TIMEZONE_OFFSET_MINUTES = int(
    os.environ.get("DAILY_QUOTA_TIMEZONE_OFFSET_MINUTES", "330")
)
DAILY_QUOTA_TIMEZONE = timezone(
    timedelta(minutes=DAILY_QUOTA_TIMEZONE_OFFSET_MINUTES)
)
DAILY_LIMIT_MESSAGE = (
    "You've reached today's practice limit (10 questions). "
    "Please come back tomorrow to continue practicing."
)

MAX_AVATAR_UPLOAD_BYTES = (
    int(os.environ.get("MAX_AVATAR_UPLOAD_MB", "3")) * 1024 * 1024
)
AVATAR_SIZE = (512, 512)
AVATAR_UPLOAD_DIR = Path(
    os.environ.get(
        "AVATAR_UPLOAD_DIR",
        Path(__file__).resolve().parent / "uploads" / "avatars",
    )
).resolve()
AVATAR_URL_PREFIX = "/api/uploads/avatars/"
ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_AVATAR_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_AVATAR_PIXELS = 40_000_000

AUDIO_UPLOAD_DIR = Path(
    os.environ.get(
        "AUDIO_UPLOAD_DIR",
        Path(__file__).resolve().parent / "uploads" / "audio",
    )
).resolve()
AUDIO_URL_PREFIX = "/api/uploads/audio/"
ALLOWED_AUDIO_TYPES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}

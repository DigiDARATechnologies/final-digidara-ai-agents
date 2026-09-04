import os
import re
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=True)


# No fallback string: a placeholder default here is a placeholder default
# everywhere it doesn't get overridden, which is how session/JWT forgery
# happens in practice. Generate a real secret per environment with
# `openssl rand -hex 32`. create_app() below refuses to boot outside of
# TESTING if either is missing or still one of these known placeholders.
PLACEHOLDER_SECRETS = {"dev-only-secret", "dev-only-jwt-secret", "dev-only-insecure-secret-change-me"}


class Config:
    DEBUG = os.getenv("FLASK_ENV") == "development"
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/communication_module"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    PROFILE_UPLOAD_FOLDER = os.getenv("PROFILE_UPLOAD_FOLDER", str(BASE_DIR / "uploads"))

    AI_PROVIDER = os.getenv("AI_PROVIDER", "auto").strip().lower()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TRANSCRIPTION_MODEL = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_TRANSCRIPTION_MODEL = os.getenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3-turbo")
    GROQ_USAGE_LOGGING = os.getenv("GROQ_USAGE_LOGGING", "true")
    GROQ_PRICE_CURRENCY = os.getenv("GROQ_PRICE_CURRENCY", os.getenv("GROQ_COST_CURRENCY", "USD"))
    GROQ_INPUT_PRICE_PER_1M = os.getenv("GROQ_INPUT_PRICE_PER_1M", os.getenv("GROQ_INPUT_COST_PER_1M"))
    GROQ_OUTPUT_PRICE_PER_1M = os.getenv("GROQ_OUTPUT_PRICE_PER_1M", os.getenv("GROQ_OUTPUT_COST_PER_1M"))
    GROQ_PRICING_EFFECTIVE_DATE = os.getenv("GROQ_PRICING_EFFECTIVE_DATE")
    GROQ_PRICING_SOURCE = os.getenv("GROQ_PRICING_SOURCE", "https://console.groq.com/docs/models")
    ANSWER_RATE_LIMIT = os.getenv("ANSWER_RATE_LIMIT", "12 per minute")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    FRONTEND_ORIGIN = [
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",")
        if origin.strip()
    ] + [
        re.compile(r"^https://[a-zA-Z0-9-]+-5173\.inc1\.devtunnels\.ms$"),
        re.compile(r"^https://[a-zA-Z0-9-]+-5174\.inc1\.devtunnels\.ms$"),
    ]
    PORT = int(os.getenv("PORT", "5001"))

from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache
import os
from pathlib import Path


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_USER: str = "root"
    DB_PASSWORD: str
    DB_NAME: str = "career_agent_db"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Web-search-grounded questions: a portion of each exam is generated using
    # OpenAI's built-in web_search tool so questions reflect real, current
    # interview questions (e.g. "Python full stack interview questions asked
    # at TCS/Infosys") instead of only the model's own memorized knowledge.
    ENABLE_WEB_SEARCH_QUESTIONS: bool = True
    WEB_SEARCH_QUESTION_RATIO: float = 0.2   # ~20% of an exam, e.g. 6/30
    WEB_SEARCH_MIN_QUESTIONS: int = 5
    WEB_SEARCH_MAX_QUESTIONS: int = 8
    WEB_SEARCH_CACHE_TTL_HOURS: int = 24
    WEB_SEARCH_CACHE_POOL_SIZE: int = 15
    TRUST_PROXY_HEADERS: bool = False

    PASS_SCORE: float = 70.0
    MAX_ATTEMPTS: int = 3
    CERTIFICATES_DIR: str = "certificates"

    # Optional SMTP delivery for official certificate PDFs. These values are
    # intentionally not required at startup: downloading certificates works
    # without email, while a send request reports a clear setup error if SMTP
    # has not been configured yet.
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str | None = None
    SMTP_USE_TLS: bool = True
    CERTIFICATE_EMAIL_VERIFICATION_TTL_MINUTES: int = 10
    CERTIFICATE_EMAIL_VERIFICATION_MAX_ATTEMPTS: int = 5

    @model_validator(mode="after")
    def validate_secrets(self):
        missing = []
        if not self.SECRET_KEY or "change_in_production" in self.SECRET_KEY or self.SECRET_KEY.startswith("your_"):
            missing.append("SECRET_KEY")
        if not self.OPENAI_API_KEY or self.OPENAI_API_KEY.startswith("your_"):
            missing.append("OPENAI_API_KEY")
        if not self.DB_PASSWORD or self.DB_PASSWORD.startswith("your_"):
            missing.append("DB_PASSWORD")
        
        if missing:
            raise ValueError(
                f"Missing or invalid required secret environment variable(s): {', '.join(missing)}. "
                "Please configure them in your .env file."
            )
        return self

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


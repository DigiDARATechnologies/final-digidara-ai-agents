import os
from dotenv import load_dotenv

load_dotenv()


def flag(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_ENV = os.getenv("APP_ENV", "development").lower()
    DEBUG = flag("DEBUG", APP_ENV == "development")
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True, "pool_recycle": 280,
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_timeout": 30,
    }
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    APP_TIMEZONE_OFFSET_MINUTES = int(os.getenv("APP_TIMEZONE_OFFSET_MINUTES", "330"))
    JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "aptitude-ai")
    JWT_ISSUER = os.getenv("JWT_ISSUER", "aptidara")
    AUTH_TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "43200"))
    SINGLE_USER_MODE = flag("SINGLE_USER_MODE", True)
    LOCAL_USER_ID = os.getenv("LOCAL_USER_ID", "demo-student-001").strip()
    LOCAL_USER_EMAIL = os.getenv("LOCAL_USER_EMAIL", "kiruthika@example.edu").strip().lower()
    LOCAL_USER_NAME = os.getenv("LOCAL_USER_NAME", "Kiruthika").strip()
    ALLOW_DEMO_QUESTIONS = flag("ALLOW_DEMO_QUESTIONS", True)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_FALLBACK_MODELS = tuple(model.strip() for model in os.getenv("OPENAI_FALLBACK_MODELS", "").split(",") if model.strip())
    # Learner-facing OpenAI calls are strictly bounded. In-memory question
    # prefetch may use the full background deadline because it never blocks
    # the learner response that started it.
    OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "12"))
    OPENAI_BACKGROUND_TIMEOUT_SECONDS = float(os.getenv("OPENAI_BACKGROUND_TIMEOUT_SECONDS", "20"))
    # One call normally finishes in 2-12 seconds. Leave enough shared budget
    # for one quality retry/topic rotation when a candidate is rejected as a
    # recent duplicate.
    LIVE_QUESTION_DEADLINE_SECONDS = float(os.getenv("LIVE_QUESTION_DEADLINE_SECONDS", "30"))
    HINT_TIMEOUT_SECONDS = float(os.getenv("HINT_TIMEOUT_SECONDS", "5"))
    RECOMMENDATION_TIMEOUT_SECONDS = max(1.0, min(8.0, float(os.getenv("RECOMMENDATION_TIMEOUT_SECONDS", "7"))))
    HINT_MAX_COMPLETION_TOKENS = max(64, min(128, int(os.getenv("HINT_MAX_COMPLETION_TOKENS", "96"))))
    # OpenAI reasoning models default to 1,024 completion tokens. That can
    # truncate the hidden reasoning plus the JSON document before the closing
    # brace, producing json_validate_failed even for a single question.
    OPENAI_JSON_MAX_COMPLETION_TOKENS = max(1024, int(os.getenv("OPENAI_JSON_MAX_COMPLETION_TOKENS", "2048")))
    # A single aptitude question does not need the generic 4K JSON budget.
    # Keeping this below the provider TPM limit materially reduces 429s while
    # still leaving room for hidden reasoning and a complete JSON document.
    QUESTION_GENERATION_MAX_COMPLETION_TOKENS = max(1024, min(2048, int(os.getenv("QUESTION_GENERATION_MAX_COMPLETION_TOKENS", "1536"))))
    OPENAI_CIRCUIT_FAILURE_THRESHOLD = max(1, int(os.getenv("OPENAI_CIRCUIT_FAILURE_THRESHOLD", "5")))
    OPENAI_CIRCUIT_COOLDOWN_SECONDS = max(1, int(os.getenv("OPENAI_CIRCUIT_COOLDOWN_SECONDS", "90")))
    OPENAI_INPUT_COST_PER_MILLION = float(os.getenv("OPENAI_INPUT_COST_PER_MILLION", "0.15"))
    OPENAI_OUTPUT_COST_PER_MILLION = float(os.getenv("OPENAI_OUTPUT_COST_PER_MILLION", "0.60"))
    BANK_OPENAI_CALL_INTERVAL_SECONDS = max(0.0, float(os.getenv("BANK_OPENAI_CALL_INTERVAL_SECONDS", "2")))
    QUESTION_SECONDS = int(os.getenv("QUESTION_SECONDS", "60"))
    QUESTION_SECONDS_EASY = int(os.getenv("QUESTION_SECONDS_EASY", str(QUESTION_SECONDS)))
    QUESTION_SECONDS_MEDIUM = int(os.getenv("QUESTION_SECONDS_MEDIUM", "90"))
    QUESTION_SECONDS_HARD = int(os.getenv("QUESTION_SECONDS_HARD", "120"))
    HINTS_PER_TEST = max(0, int(os.getenv("HINTS_PER_TEST", "3")))
    # Local development commonly creates many short-lived attempts while UI
    # and generation behavior are tested. Production keeps the tighter abuse
    # limit unless explicitly overridden.
    START_TEST_RATE_LIMIT = max(1, int(os.getenv("START_TEST_RATE_LIMIT", "100" if APP_ENV == "development" else "10")))
    START_TEST_RATE_WINDOW_SECONDS = max(60, int(os.getenv("START_TEST_RATE_WINDOW_SECONDS", "3600")))
    TIMEOUT_GRACE_SECONDS = int(os.getenv("TIMEOUT_GRACE_SECONDS", "3"))
    ABANDON_AFTER_SECONDS = int(os.getenv("ABANDON_AFTER_SECONDS", "180"))
    WORKER_POLL_SECONDS = float(os.getenv("WORKER_POLL_SECONDS", "2"))
    MAX_JOB_ATTEMPTS = int(os.getenv("MAX_JOB_ATTEMPTS", "3"))
    WORKER_HEARTBEAT_SECONDS = max(2, int(os.getenv("WORKER_HEARTBEAT_SECONDS", "10")))
    WORKER_STALE_SECONDS = max(10, int(os.getenv("WORKER_STALE_SECONDS", "45")))
    RECENT_QUESTION_HISTORY_LIMIT = max(1, int(os.getenv("RECENT_QUESTION_HISTORY_LIMIT", "30")))
    QUESTION_PREFETCH_ENABLED = flag("QUESTION_PREFETCH_ENABLED", True)
    QUESTION_PREFETCH_TTL_SECONDS = max(15, int(os.getenv("QUESTION_PREFETCH_TTL_SECONDS", "120")))
    QUESTION_PREFETCH_TIMEOUT_SECONDS = max(1.0, float(os.getenv("QUESTION_PREFETCH_TIMEOUT_SECONDS", "9")))
    QUESTION_PREFETCH_WORKERS = max(1, min(4, int(os.getenv("QUESTION_PREFETCH_WORKERS", "2"))))

    @classmethod
    def validate(cls, app):
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if not uri.startswith("mysql+pymysql://"):
            raise RuntimeError("DATABASE_URL must use MySQL with the mysql+pymysql:// scheme")
        configured_models=(app.config.get("OPENAI_MODEL",""),*app.config.get("OPENAI_FALLBACK_MODELS",()))
        if not all(configured_models):
            raise RuntimeError("OPENAI_MODEL must be configured")
        if app.config["APP_ENV"] == "production":
            errors = []
            if app.config["SECRET_KEY"] == "development-only-change-me": errors.append("SECRET_KEY")
            if app.config["JWT_SECRET"] == "dev-secret-change-me": errors.append("JWT_SECRET")
            if app.config["SINGLE_USER_MODE"]: errors.append("SINGLE_USER_MODE must be false")
            # Demo fixtures are never acceptable in the production live-
            # generation architecture.
            if app.config["ALLOW_DEMO_QUESTIONS"]: errors.append("ALLOW_DEMO_QUESTIONS must be false")
            if errors:
                raise RuntimeError("Unsafe production configuration: " + ", ".join(errors))

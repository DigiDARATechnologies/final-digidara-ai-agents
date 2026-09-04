import os
from pathlib import Path


def _local_judge_value(key, default=""):
    try:
        base = Path(__file__).resolve().parents[3]
    except IndexError:
        return default
    path = base / "judge0" / "judge0.conf"
    if not path.exists():
        return default
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip() or default
    return default


class Config:
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "leetcode")
    MYSQL_USER = os.getenv("MYSQL_USER", "")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    LMS_API_SHARED_SECRET = os.getenv("LMS_API_SHARED_SECRET", "")
    CODING_PRACTICE_ENABLED = os.getenv("CODING_PRACTICE_ENABLED", "false").lower() == "true"
    SIGNATURE_MAX_AGE_SECONDS = int(os.getenv("SIGNATURE_MAX_AGE_SECONDS", "300"))
    SESSION_DAYS = int(os.getenv("SESSION_DAYS", "7"))
    JUDGE0_URL = os.getenv("JUDGE0_URL", "http://127.0.0.1:2358")
    JUDGE0_AUTHN_HEADER = os.getenv("JUDGE0_AUTHN_HEADER", _local_judge_value("AUTHN_HEADER", "X-Auth-Token"))
    JUDGE0_AUTHN_TOKEN = os.getenv("JUDGE0_AUTHN_TOKEN", _local_judge_value("AUTHN_TOKEN"))
    JUDGE0_AUTHZ_HEADER = os.getenv("JUDGE0_AUTHZ_HEADER", _local_judge_value("AUTHZ_HEADER", "X-Auth-User"))
    JUDGE0_AUTHZ_TOKEN = os.getenv("JUDGE0_AUTHZ_TOKEN", _local_judge_value("AUTHZ_TOKEN"))
    JUDGE0_TIMEOUT_SECONDS = int(os.getenv("JUDGE0_TIMEOUT_SECONDS", "15"))
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TIMEOUT_SECONDS = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "12"))

    @classmethod
    def validate(cls):
        missing = [
            name
            for name in ("MYSQL_USER", "MYSQL_PASSWORD", "LMS_API_SHARED_SECRET")
            if not getattr(cls, name)
        ]
        if missing:
            raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")

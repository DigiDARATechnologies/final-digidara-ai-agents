import os

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

ENV = os.environ.get("ENV", "dev")
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    if ENV != "dev":
        raise RuntimeError("DATABASE_URL is not set. Configure it before starting the orchestrator outside of ENV=dev.")
    DATABASE_URL = "mysql+pymysql://root:root@localhost:3306/digidara_registry"  # local dev only

# An agent must have heartbeated within this window to be treated as live.
# Never trust the `status` column alone — a crashed agent can leave it
# "healthy" forever otherwise.
HEARTBEAT_TTL_SECONDS = _int("HEARTBEAT_TTL_SECONDS", 90)
HEARTBEAT_INTERVAL_SECONDS = _int("HEARTBEAT_INTERVAL_SECONDS", 30)

AGENT_CALL_TIMEOUT_SECONDS = _int("AGENT_CALL_TIMEOUT_SECONDS", 30)
APTITUDE_CREATE_TEST_TIMEOUT_SECONDS = _int("APTITUDE_CREATE_TEST_TIMEOUT_SECONDS", 210)

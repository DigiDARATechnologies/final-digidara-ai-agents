import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


# Resume uploads: stored as-is, never parsed — a resume parser is a real
# feature (accuracy + a much larger untrusted-file attack surface) better
# scoped as its own later milestone than bundled into profile collection.
UPLOAD_DIR = Path(os.getenv("JOBS_UPLOAD_DIR", str(Path(__file__).parent / "uploads")))
RESUME_MAX_BYTES = int(os.getenv("JOBS_RESUME_MAX_BYTES", str(5 * 1024 * 1024)))
ALLOWED_RESUME_EXTENSIONS = {".pdf", ".doc", ".docx"}

SCRAPER_USER_AGENT = os.getenv(
    "JOBS_SCRAPER_USER_AGENT",
    "DigiDARAJobsBot/1.0 (+https://digidara.com; jobs@digidara.com)",
)
SCRAPER_TIMEOUT_SECONDS = int(os.getenv("JOBS_SCRAPER_TIMEOUT_SECONDS", "20"))
SCRAPER_MAX_BYTES = int(os.getenv("JOBS_SCRAPER_MAX_BYTES", str(5 * 1024 * 1024)))
# Greenhouse gets its own, higher limit rather than reusing SCRAPER_MAX_BYTES:
# it's a trusted, structured JSON API (not an arbitrary scraped page), and a
# handful of large boards (many jobs, long HTML descriptions with
# content=true) legitimately exceed the generic scraper's 5MB ceiling.
GREENHOUSE_MAX_RESPONSE_BYTES = int(os.getenv("JOBS_GREENHOUSE_MAX_RESPONSE_BYTES", str(15 * 1024 * 1024)))
WORKER_POLL_SECONDS = max(5, int(os.getenv("JOBS_WORKER_POLL_SECONDS", "15")))
# A worker restart recovers only runs older than this threshold. Individual
# source calls are normally bounded by the scraper timeout, so 30 minutes is
# deliberately conservative and avoids duplicate processing.
RUN_STALE_SECONDS = max(300, int(os.getenv("JOBS_RUN_STALE_SECONDS", "1800")))

# The continuous worker loop (worker.py) touches this file every poll
# iteration. Docker's HEALTHCHECK for the job-worker container reads its
# freshness via `python -m job_agent.worker --healthcheck` — that container
# runs no web server, so it can't reuse job-agent's HTTP health endpoint.
WORKER_HEARTBEAT_FILE = os.getenv("JOBS_WORKER_HEARTBEAT_FILE", "/tmp/job_worker_heartbeat")
WORKER_HEARTBEAT_STALE_SECONDS = max(
    120, int(os.getenv("JOBS_WORKER_HEARTBEAT_STALE_SECONDS", str(WORKER_POLL_SECONDS * 4 + 60)))
)

# Daily Greenhouse collection is deliberately owned by the ingestion worker,
# never an HTTP request. The administrator can enable/disable it in Sources;
# time and timezone remain deployment configuration.
JOBS_AUTOMATION_TIME = os.getenv("JOBS_AUTOMATION_TIME", "09:00").strip()
JOBS_AUTOMATION_TIMEZONE = os.getenv("JOBS_AUTOMATION_TIMEZONE", "Asia/Kolkata").strip()
JOBS_AUTOMATION_DEFAULT_ENABLED = os.getenv("JOBS_AUTOMATION_DEFAULT_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
try:
    datetime.strptime(JOBS_AUTOMATION_TIME, "%H:%M")
except ValueError as exc:
    raise RuntimeError("JOBS_AUTOMATION_TIME must use 24-hour HH:MM format, for example 09:00") from exc
try:
    ZoneInfo(JOBS_AUTOMATION_TIMEZONE)
except Exception as exc:
    raise RuntimeError("JOBS_AUTOMATION_TIMEZONE must be a valid IANA timezone, for example Asia/Kolkata") from exc

# SaaS plan tiers this service understands. `free` is the default assigned to
# every new profile; `admin_users_update_plan` (routes.py) is the only way a
# profile ever changes tier — there is no self-serve upgrade flow yet, that
# lives in the orchestrator's billing module once wired up.
PLAN_TIERS = ("free", "pro")
DEFAULT_PLAN_TIER = "free"

# Dynamic SaaS Token & Daily Free Quota Defaults (can be overridden by DB or .env)
DEFAULT_FREE_DAILY_FEED_LIMIT = int(os.getenv("JOBS_FREE_DAILY_FEED_LIMIT", "20"))
DEFAULT_FREE_DAILY_CHAT_TURNS = int(os.getenv("JOBS_FREE_DAILY_CHAT_TURNS", "10"))
DEFAULT_TOKENS_PER_EXTRA_FEED = int(os.getenv("JOBS_TOKENS_PER_EXTRA_FEED", "2000"))
DEFAULT_TOKENS_PER_CHAT_TURN = int(os.getenv("JOBS_TOKENS_PER_CHAT_TURN", "500"))

# Backwards compatibility
FREE_TIER_DAILY_FEED_LIMIT = DEFAULT_FREE_DAILY_FEED_LIMIT


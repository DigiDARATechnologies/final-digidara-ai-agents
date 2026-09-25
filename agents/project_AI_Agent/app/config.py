import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()

ENV = os.environ.get("ENV", "dev")
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    if ENV != "dev":
        raise RuntimeError("DATABASE_URL is not set. Configure it before starting this agent outside of ENV=dev.")
    DATABASE_URL = "mysql+pymysql://root:root@localhost:3306/capstone_agent"  # local dev only

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "./uploads")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SUBMISSION_WINDOW_DAYS = _int("SUBMISSION_WINDOW_DAYS", 7)
PASS_THRESHOLD = _int("PASS_THRESHOLD", 70)

MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 50)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_ZIP_FILES = _int("MAX_ZIP_FILES", 1000)

# How much of the student's source code the reviewers read, in characters.
# Every file is sent in full while the whole zip fits; past this the biggest
# files are trimmed (fairly, and flagged as trimmed to the model). ~160k chars
# is roughly 40k tokens -- comfortably inside the model's context and cheap.
CODE_REVIEW_CHAR_BUDGET = _int("CODE_REVIEW_CHAR_BUDGET", 160_000)

# File extensions treated as readable source/text inside a submitted zip.
CODE_TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".c", ".h",
    ".cpp", ".hpp", ".cs", ".rs", ".json", ".yaml", ".yml", ".toml", ".md", ".txt",
    ".html", ".css", ".scss", ".sql", ".sh", ".env.example", ".gitignore",
    ".ipynb", ".xml", ".ini", ".cfg",
}

# Folders whose contents are dependency/build clutter, not submitted source.
ZIP_IGNORE_DIR_NAMES = {
    "node_modules", "venv", ".venv", "__pycache__", ".git", "dist", "build",
    ".idea", ".vscode", "target", ".pytest_cache", "env",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

# CodeExecutionNode — supplementary "does it actually run" evidence for a
# submission's Python entry point, executed inside Judge0's sandbox (the
# same isolated service agents/codeforge_agent already depends on) rather
# than on this process's own host. Judge0 not reachable just means no
# execution evidence for that submission, not a failure — see
# app/execution/judge0_client.py.
JUDGE0_URL = os.environ.get("JUDGE0_URL", "http://127.0.0.1:2358")
CODE_EXECUTION_CPU_SECONDS = _int("CODE_EXECUTION_CPU_SECONDS", 5)
CODE_EXECUTION_WALL_SECONDS = _int("CODE_EXECUTION_WALL_SECONDS", 10)
CODE_EXECUTION_MEMORY_KB = _int("CODE_EXECUTION_MEMORY_KB", 128000)

# Same "supplementary, best-effort evidence" role as Judge0 above, for static
# HTML/CSS/JS submissions that have nothing Judge0 can execute — see
# app/execution/browser_check.py.
BROWSER_CHECK_TIMEOUT_MS = _int("BROWSER_CHECK_TIMEOUT_MS", 10000)

# topic_generator_node web search — grounds free-topic ("TCS interview prep",
# "Python developer role", etc.) project generation in real, current
# information instead of guessing from training data alone. Scoped to just
# that one call (see llm/client.py's call_json(..., web_search=True)), not
# every LLM call in the app, to control the extra cost/latency it adds.
ENABLE_TOPIC_WEB_SEARCH = os.environ.get("ENABLE_TOPIC_WEB_SEARCH", "true").strip().lower() != "false"
# Verified reachable against the live OpenAI API for this account — the
# older gpt-4o(-mini)-search-preview models are deprecated (404) there;
# gpt-5-search-api is the current chat-completions-compatible search-grounded
# model. It does not accept `temperature` (see llm/client.py). Override via
# the env var if your account's available model lineup differs.
WEB_SEARCH_LLM_MODEL = os.environ.get("WEB_SEARCH_LLM_MODEL", "gpt-5-search-api")
# OpenAI's own token/cost lever for web search: "low" | "medium" | "high" —
# how much search-result content gets pulled into the model's context. "low"
# is enough to steer two short topic ideas; it doesn't need a research report.
WEB_SEARCH_CONTEXT_SIZE = os.environ.get("WEB_SEARCH_CONTEXT_SIZE", "low")

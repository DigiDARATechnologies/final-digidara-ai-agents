"""Carries the verified DigiDARA user id (`X-DigiDARA-User-Id`, set by the
orchestrator gateway from a validated JWT — see gateway/routes.py) down to
code that has no access to the FastAPI `Request`, such as app/llm/client.py's
usage-logging helper. Bound per-request by the middleware in app/api/main.py.
"""
from contextvars import ContextVar

current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)

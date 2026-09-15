"""Carries request-scoped state down to code that has no access to the
FastAPI `Request`, such as app/llm/client.py's usage-logging helper. Bound
per-request by the middleware in app/api/main.py.
"""
from contextvars import ContextVar


class TokenCounter:
    """A mutable box, not a plain int: route handlers here run via
    starlette's run_in_threadpool, which executes them inside a *copy* of
    the current context (contextvars.copy_context()). ContextVar.set()
    calls made inside that copy never propagate back to the caller's
    context, so the middleware below could never observe an updated int
    reassigned that way. A copy is shallow, though — it points at the same
    referenced object — so mutating this object's `.total` attribute from
    inside the threadpool call *is* visible to the middleware afterward.
    """

    __slots__ = ("total",)

    def __init__(self) -> None:
        self.total = 0


# Verified DigiDARA user id (`X-DigiDARA-User-Id`, set by the orchestrator
# gateway from a validated JWT — see gateway/routes.py).
current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)

# Running total of real LLM tokens spent so far in the current request,
# reported back to the orchestrator gateway as the X-Tokens-Used response
# header so it can bill actual cost instead of a flat per-call guess.
current_request_tokens: ContextVar["TokenCounter | None"] = ContextVar("current_request_tokens", default=None)

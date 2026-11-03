"""Records this server's own failed requests. Agent calls are recorded by the
gateway, which knows the agent and action."""
import json

from app.monitoring import service

_SKIPPED = ("/gateway/", "/health")
_MAX_BODY = 64_000


def _reason(body: bytes, status: int) -> str:
    """The error's words only. A validation error can repeat what was sent
    (a learner's whole chat), so raw response text is never kept."""
    try:
        detail = json.loads(body).get("detail")
    except (ValueError, AttributeError):
        return f"HTTP {status}"
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        words = [item.get("msg", "") for item in detail if isinstance(item, dict)]
        return "; ".join(dict.fromkeys(word for word in words if word)) or f"HTTP {status}"
    return f"HTTP {status}"


class IssueMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].startswith(_SKIPPED):
            await self.app(scope, receive, send)
            return
        status = 0
        body = b""

        async def watch(message):
            nonlocal status, body
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body" and (status == 422 or status >= 500) and len(body) < _MAX_BODY:
                body += message.get("body", b"")
            await send(message)

        # A route's id is not part of the problem: /chats/sync, not one learner's URL.
        def report(code: int, reason: str) -> None:
            path = "/".join(part for part in scope["path"].split("/")[:3])
            service.record("server", service.ERROR if code >= 500 else service.WARNING, reason,
                           agent="orchestrator", action=path, status=code)

        try:
            await self.app(scope, receive, watch)
        except Exception:
            report(500, "Unhandled server error")
            raise
        if status == 422 or status >= 500:
            report(status, _reason(body, status))

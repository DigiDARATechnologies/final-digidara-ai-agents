"""Job Agent personal-data bridge used by platform export and erasure."""
from urllib.parse import urlparse

import httpx

from app import config
from app.gateway.routes import ALLOWED_AGENT_HOSTS
from app.registry import service as registry_service


class JobDataUnavailable(RuntimeError):
    pass


def _invoke(action: str, user_id: str) -> dict:
    agent = registry_service.resolve_healthy("job_agent")
    if agent is None:
        raise JobDataUnavailable("Job Agent is temporarily unavailable. Please try again.")
    if urlparse(agent.endpoint).hostname not in ALLOWED_AGENT_HOSTS:
        raise JobDataUnavailable("Job Agent endpoint is not allowed by the gateway policy.")
    try:
        response = httpx.post(
            agent.endpoint,
            json={"action": action, "payload": {}},
            headers={"X-Digidara-User-Id": user_id, "X-Digidara-Is-Admin": "false"},
            timeout=config.AGENT_CALL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise JobDataUnavailable("Job Agent could not complete the personal-data request.") from exc
    if not isinstance(payload, dict):
        raise JobDataUnavailable("Job Agent returned an invalid personal-data response.")
    return payload


def export_user_data(user_id: str) -> dict:
    return _invoke("export_user_data", user_id)


def delete_user_data(user_id: str) -> None:
    _invoke("delete_user_data", user_id)

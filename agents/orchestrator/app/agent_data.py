"""Personal-data bridge to the learner-facing agents (DPDP export and erasure).

Job Agent has its own bridge (job_data.py). Aptitude, Mock Interview and
Capstone each hold learner data in their own databases; without this module
a platform account export/deletion silently skipped them.

Fails closed like job_data.py: if any agent cannot be reached, the request is
refused with a message naming it, so an incomplete export or erasure can
never look complete. Erasure checks every agent is healthy *before* deleting
from any of them, so an outage cannot leave the account half-erased.
"""
from urllib.parse import urlparse

import httpx

from app import config
from app.gateway.routes import ALLOWED_AGENT_HOSTS
from app.registry import service as registry_service

# Registry name -> key used in the export document.
PRIVACY_AGENTS = {
    "aptitude_agent": "aptitude_agent",
    "mock_interview_agent": "mock_interview_agent",
    "capstone_project_agent": "capstone_project_agent",
}


class AgentDataUnavailable(RuntimeError):
    pass


def _endpoint(agent_name: str) -> str:
    agent = registry_service.resolve_healthy(agent_name)
    if agent is None:
        raise AgentDataUnavailable(f"{agent_name} is temporarily unavailable. Please try again.")
    if urlparse(agent.endpoint).hostname not in ALLOWED_AGENT_HOSTS:
        raise AgentDataUnavailable(f"{agent_name} endpoint is not allowed by the gateway policy.")
    return agent.endpoint


def _invoke(agent_name: str, endpoint: str, action: str, user_id: str, email: str) -> dict:
    try:
        response = httpx.post(
            endpoint,
            json={"action": action, "payload": {"email": email}},
            headers={"X-Digidara-User-Id": user_id, "X-Digidara-Is-Admin": "false"},
            timeout=config.AGENT_CALL_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AgentDataUnavailable(f"{agent_name} could not complete the personal-data request.") from exc
    if not isinstance(payload, dict):
        raise AgentDataUnavailable(f"{agent_name} returned an invalid personal-data response.")
    return payload


def export_user_data(user_id: str, email: str) -> dict:
    endpoints = {name: _endpoint(name) for name in PRIVACY_AGENTS}
    return {
        key: _invoke(name, endpoints[name], "export_user_data", user_id, email)
        for name, key in PRIVACY_AGENTS.items()
    }


def delete_user_data(user_id: str, email: str) -> None:
    endpoints = {name: _endpoint(name) for name in PRIVACY_AGENTS}
    for name in PRIVACY_AGENTS:
        _invoke(name, endpoints[name], "delete_user_data", user_id, email)

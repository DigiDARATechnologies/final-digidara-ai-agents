"""Read-only startup/API smoke checks; run separately from browser tests."""
import json
import os
import math
import time
from urllib.error import URLError
from urllib.request import Request, urlopen, build_opener, ProxyHandler
from urllib.parse import urlsplit

import pytest

# Service name: (local port, identity returned by /api/invoke).
AGENTS = {
    "orchestrator": (8100, None),
    "capstone-agent": (8000, "capstone_project_agent"),
    "codeforge-agent": (4000, "codeforge_agent"),
    "communication-agent": (5001, "communication_agent"),
    "aptitude-agent": (5000, "aptitude_agent"),
    "resume-builder-agent": (5010, "resume_builder_agent"),
    "certificate-agent": (8008, "certificate_agent"),
    "job-agent": (5020, "job_agent"),
}


def selected_agents():
    selected = os.getenv("AGENT_NAME", "all")
    if selected == "all":
        return list(AGENTS)
    if selected not in AGENTS:
        raise pytest.UsageError(f"Unknown AGENT_NAME={selected!r}; choose all or {', '.join(AGENTS)}")
    return [selected]


def check_health(url, identity, timeout):
    # Local agent traffic must not be sent through a machine-wide proxy.
    opener = build_opener(ProxyHandler({})).open if urlsplit(url).hostname in {"127.0.0.1", "localhost", "::1"} else urlopen
    deadline = time.monotonic() + timeout
    last_error = "No response"
    while True:
        try:
            request = Request(
                url,
                data=json.dumps({"action": "health"}).encode() if identity else None,
                headers={"Content-Type": "application/json"},
            )
            with opener(request, timeout=min(5, max(0.1, deadline - time.monotonic()))) as response:
                assert response.status == 200, f"HTTP {response.status}"
                assert "application/json" in response.headers.get("Content-Type", ""), "Expected JSON content type"
                body = json.load(response)
            assert isinstance(body, dict), f"Expected JSON object, got {body!r}"
            assert body.get("status") == "ok", f"Unhealthy response: {body!r}"
            if identity:
                assert body.get("agent_name") == identity, f"Wrong agent response: {body!r}"
            return
        except (URLError, OSError, ValueError, AssertionError) as exc:
            last_error = str(exc)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(
                f"Health check failed at {url}: {last_error}. "
                "Run npm run test:agents to build/start an isolated test stack, "
                "or start the agent and set its *_URL to an accessible address. "
                "The production Compose stack does not publish agent ports."
            )
        time.sleep(min(1, remaining))


@pytest.mark.parametrize("agent", selected_agents())
def test_agent_health(agent):
    port, identity = AGENTS[agent]
    env_key = agent.upper().replace("-", "_") + "_URL"
    base_url = os.getenv(env_key, f"http://127.0.0.1:{port}").rstrip("/")
    timeout = float(os.getenv("AGENT_HEALTH_TIMEOUT", "5"))
    assert math.isfinite(timeout) and timeout > 0, "AGENT_HEALTH_TIMEOUT must be positive"
    path = "/api/invoke" if identity else "/health"
    check_health(base_url + path, identity, timeout)

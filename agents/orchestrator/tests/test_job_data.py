import json
from types import SimpleNamespace

import httpx
import pytest

from app import job_data


def test_job_data_bridge_forwards_only_server_identity(monkeypatch):
    monkeypatch.setattr(
        job_data.registry_service,
        "resolve_healthy",
        lambda name: SimpleNamespace(endpoint="http://localhost:5020/api/invoke") if name == "job_agent" else None,
    )
    captured = {}

    def fake_post(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return httpx.Response(
            200,
            json={"profile": None, "job_actions": []},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(job_data.httpx, "post", fake_post)
    result = job_data.export_user_data("verified-user")

    assert result == {"profile": None, "job_actions": []}
    headers = captured["headers"]
    assert headers["X-Digidara-User-Id"] == "verified-user"
    assert headers["X-Digidara-Is-Admin"] == "false"
    assert headers["x-digidara-signature"] and headers["x-digidara-agent"] == "job_agent"
    assert json.loads(captured["content"])["action"] == "export_user_data"


def test_job_data_bridge_fails_closed_when_agent_is_unavailable(monkeypatch):
    monkeypatch.setattr(job_data.registry_service, "resolve_healthy", lambda name: None)
    with pytest.raises(job_data.JobDataUnavailable):
        job_data.delete_user_data("verified-user")

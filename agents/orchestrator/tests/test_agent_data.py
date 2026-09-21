from types import SimpleNamespace

import httpx
import pytest

from app import agent_data


def _registry(monkeypatch, healthy):
    monkeypatch.setattr(
        agent_data.registry_service,
        "resolve_healthy",
        lambda name: SimpleNamespace(endpoint=f"http://localhost:1/{name}/api/invoke") if name in healthy else None,
    )


def test_export_collects_every_privacy_agent_with_server_identity(monkeypatch):
    _registry(monkeypatch, set(agent_data.PRIVACY_AGENTS))
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={"profile": {"from": url}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(agent_data.httpx, "post", fake_post)
    result = agent_data.export_user_data("user-1", "a@b.com")

    assert set(result) == set(agent_data.PRIVACY_AGENTS)
    assert len(calls) == 3
    for _, kwargs in calls:
        assert kwargs["headers"] == {"X-Digidara-User-Id": "user-1", "X-Digidara-Is-Admin": "false"}
        assert kwargs["json"] == {"action": "export_user_data", "payload": {"email": "a@b.com"}}


def test_erasure_deletes_nothing_when_any_agent_is_down(monkeypatch):
    _registry(monkeypatch, {"aptitude_agent", "capstone_project_agent"})  # mock interview down
    monkeypatch.setattr(agent_data.httpx, "post", lambda *a, **k: pytest.fail("must not call any agent"))
    with pytest.raises(agent_data.AgentDataUnavailable, match="mock_interview_agent"):
        agent_data.delete_user_data("user-1", "a@b.com")


def test_agent_failure_fails_closed(monkeypatch):
    _registry(monkeypatch, set(agent_data.PRIVACY_AGENTS))

    def fake_post(url, **kwargs):
        return httpx.Response(500, request=httpx.Request("POST", url))

    monkeypatch.setattr(agent_data.httpx, "post", fake_post)
    with pytest.raises(agent_data.AgentDataUnavailable):
        agent_data.export_user_data("user-1", "a@b.com")

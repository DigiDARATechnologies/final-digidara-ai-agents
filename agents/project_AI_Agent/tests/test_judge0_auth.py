"""The Capstone agent sends Judge0's access token, like the CodeForge agent."""
import httpx

from app import config
from app.execution import judge0_client


def test_every_judge0_request_carries_the_access_token(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"status": {"id": 3, "description": "Accepted"}, "stdout": None})

    real_client = httpx.Client
    monkeypatch.setattr(judge0_client.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(config, "JUDGE0_AUTHN_TOKEN", "secret-token")
    monkeypatch.setattr(config, "JUDGE0_AUTHZ_TOKEN", "")
    result = judge0_client.run_python_submission({"main.py": "print(1)"}, "main.py")
    assert result["status"] == "Accepted"
    assert seen["x-auth-token"] == "secret-token" and "x-auth-user" not in seen


def test_python_runs_use_per_process_limits(monkeypatch):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        sent.update(json.loads(request.content))
        return httpx.Response(200, json={"status": {"id": 3, "description": "Accepted"}})

    real_client = httpx.Client
    monkeypatch.setattr(judge0_client.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    judge0_client.run_python_submission({"main.py": "print(1)"}, "main.py")
    assert sent["enable_per_process_and_thread_time_limit"] is True
    assert sent["enable_per_process_and_thread_memory_limit"] is True

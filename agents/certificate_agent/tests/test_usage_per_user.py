"""Settings > Usage must show each learner only their own certificate-agent usage."""
import json
import threading
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from cert_app.main import app
from cert_app.services import usage_service
from tests.test_gateway_signing_real_app import SECRET, sign


def fake_connection(fetchone=None, fetchall=()):
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = list(fetchall)
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_no_user_means_zero_usage_without_touching_the_database(monkeypatch):
    get_connection = MagicMock()
    monkeypatch.setattr(usage_service, "get_connection", get_connection)
    for user in (None, "", "   "):
        summary = usage_service.get_usage_summary(user)
        assert (summary["total_requests"], summary["total_tokens"], summary["by_request_type"]) == (0, 0, {})
    get_connection.assert_not_called()


def test_summary_counts_only_the_given_user(monkeypatch):
    conn, cursor = fake_connection(
        {"total_requests": 4, "total_tokens": 1200, "prompt_tokens": 900, "completion_tokens": 300},
        [{"action_name": "send_chat_message", "request_count": 4}],
    )
    monkeypatch.setattr(usage_service, "get_connection", lambda: conn)
    summary = usage_service.get_usage_summary("user-a")
    assert summary["total_tokens"] == 1200 and summary["total_requests"] == 4
    assert summary["by_request_type"] == {"send_chat_message": 4}
    for call in cursor.execute.call_args_list:
        assert "digidara_user_id = %s" in call.args[0]
        assert call.args[1] == ("user-a",)


def test_recorded_events_carry_the_current_user_even_from_worker_threads(monkeypatch):
    conn, cursor = fake_connection()
    monkeypatch.setattr(usage_service, "get_connection", lambda: conn)
    token = usage_service.set_usage_user("user-a")
    try:
        usage_service.record_request("start_chat")
        worker = threading.Thread(target=usage_service.carry_usage_user(
            lambda: usage_service.record_llm_usage("question_generation", MagicMock(usage={"total_tokens": 50}))
        ))
        worker.start()
        worker.join()
    finally:
        usage_service.reset_usage_user(token)
    owners = [call.args[1][-1] for call in cursor.execute.call_args_list]
    assert owners == ["user-a", "user-a"]


def test_usage_summary_action_reports_the_signed_in_user(monkeypatch):
    seen = []
    monkeypatch.setattr("cert_app.api.invoke.get_usage_summary", lambda user: seen.append(user) or {"agent_name": "certificate_agent"})
    monkeypatch.setenv("AGENT_SHARED_SECRET", SECRET)
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    client = TestClient(app, raise_server_exceptions=False)
    body = json.dumps({"action": "usage_summary", "payload": {}}).encode()
    response = client.post("/api/invoke", content=body, headers=sign(body, user_id="new-learner"))
    assert response.status_code == 200
    assert seen == ["new-learner"]

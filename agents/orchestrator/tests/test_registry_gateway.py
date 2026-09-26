import hashlib
import hmac
import io
import json
import time
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from app import config
from app.auth import service_auth
from app.auth.security import create_access_token
from app.gateway import routes as gateway
from app.models import AgentRegistry, User
from app.registry import service
from app.schemas import AgentRegisterRequest

PAYLOAD = dict(agent_name="test-agent", version="v1", endpoint="http://localhost:8000/api/invoke", description="Test agent", input_schema={})

def signed(client, method, path, payload=None, age=0, headers=None):
    body = json.dumps(payload).encode() if payload is not None else b""
    timestamp, request_id = str(int(time.time()) - age), uuid.uuid4().hex
    canonical = "\n".join((timestamp, request_id, method, path.split("?")[0], hashlib.sha256(body).hexdigest()))
    signature = hmac.new(service_auth.AGENT_SHARED_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    signed_headers = {"content-type": "application/json", "x-agent-timestamp": timestamp, "x-agent-request-id": request_id, "x-agent-signature": signature}
    signed_headers.update(headers or {})
    return client.request(method, path, content=body, headers=signed_headers)

def test_registration_upsert_and_deregistration(client):
    assert signed(client, "POST", "/registry/register", PAYLOAD).status_code == 201
    updated = dict(PAYLOAD, endpoint="http://localhost:9000/api/invoke")
    assert signed(client, "POST", "/registry/register", updated).status_code == 201
    rows = signed(client, "GET", "/registry/agents").json()
    assert len(rows) == 1
    assert rows[0]["endpoint"] == updated["endpoint"]
    path = "/registry/deregister?agent_name=test-agent&version=v1"
    assert signed(client, "DELETE", path).status_code == 200
    assert signed(client, "DELETE", path).status_code == 404
    assert service.resolve_healthy("test-agent") is None

def test_heartbeat_resyncs_a_stale_endpoint(client):
    """register() only runs once at process boot -- a long-lived agent whose
    AGENT_PUBLIC_URL was corrected after it last started must self-heal via
    its next heartbeat, not stay stuck on the endpoint it booted with."""
    assert signed(client, "POST", "/registry/register", PAYLOAD).status_code == 201
    heartbeat_payload = {"agent_name": "test-agent", "version": "v1", "endpoint": "http://job-agent:5020/api/invoke"}
    assert signed(client, "POST", "/registry/heartbeat", heartbeat_payload).status_code == 200
    rows = signed(client, "GET", "/registry/agents").json()
    assert rows[0]["endpoint"] == "http://job-agent:5020/api/invoke"

def test_heartbeat_without_endpoint_leaves_it_unchanged(client):
    """Older/unpatched agent clients that don't send `endpoint` in their
    heartbeat body must keep working exactly as before."""
    assert signed(client, "POST", "/registry/register", PAYLOAD).status_code == 201
    assert signed(client, "POST", "/registry/heartbeat", {"agent_name": "test-agent", "version": "v1"}).status_code == 200
    rows = signed(client, "GET", "/registry/agents").json()
    assert rows[0]["endpoint"] == PAYLOAD["endpoint"]

@pytest.mark.parametrize("method,path", [("POST", "/registry/register"), ("POST", "/registry/heartbeat"), ("GET", "/registry/agents"), ("DELETE", "/registry/deregister?agent_name=x&version=v1")])
def test_registry_requires_signature(client, method, path):
    assert client.request(method, path, json=PAYLOAD).status_code == 401

@pytest.mark.parametrize("age,headers", [(1000, {}), (-1000, {}), (0, {"x-agent-signature": "invalid"}), (0, {"x-agent-timestamp": "bad"})])
def test_invalid_registry_signatures(client, age, headers):
    assert signed(client, "POST", "/registry/register", PAYLOAD, age, headers).status_code == 401
    assert service.list_all() == []

def test_replay_and_body_tampering(client):
    response = signed(client, "POST", "/registry/register", PAYLOAD)
    request = response.request
    assert client.request("POST", request.url, content=request.content, headers=request.headers).status_code == 401
    assert client.request("POST", request.url, content=b"{}", headers=request.headers).status_code == 401

def test_stale_and_unhealthy_agents_excluded_until_heartbeat(client, database):
    service.register(AgentRegisterRequest(**PAYLOAD))
    with database() as session:
        row = session.get(AgentRegistry, ("test-agent", "v1"))
        row.last_heartbeat = datetime.utcnow() - timedelta(seconds=config.HEARTBEAT_TTL_SECONDS + 10)
        session.commit()
    assert service.resolve_healthy("test-agent") is None
    assert signed(client, "GET", "/registry/agents?healthy_only=true").json() == []
    assert signed(client, "POST", "/registry/heartbeat", {"agent_name": "test-agent", "version": "v1"}).status_code == 200
    assert service.resolve_healthy("test-agent") is not None
    service.mark_unhealthy("test-agent", "v1")
    assert service.list_healthy() == []
    assert signed(client, "POST", "/registry/heartbeat", {"agent_name": "missing", "version": "v1"}).status_code == 404

@pytest.fixture
def upstream(client, database, monkeypatch):
    service.register(AgentRegisterRequest(**PAYLOAD))
    with database() as session:
        session.add(User(id="learner", name="Learner", email="learner@example.test", token_balance=1000))
        session.commit()
    remote = SimpleNamespace(calls=[], timeouts=[], response=httpx.Response(200, json={"ok": True}), error=None)
    class FakeClient:
        def __init__(self, **kwargs): remote.timeouts.append(kwargs.get("timeout"))
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            remote.calls.append((url, kwargs))
            if remote.error: raise remote.error
            return remote.response
    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(gateway, "ALLOWED_AGENT_HOSTS", {"localhost"})
    return remote

def invoke(client, action="generate", token=True, **kwargs):
    headers = kwargs.pop("headers", {})
    if token: headers["authorization"] = "Bearer " + create_access_token("learner")
    return client.post("/gateway/agents/test-agent/invoke", json={"action": action, **kwargs}, headers=headers)

@pytest.mark.parametrize("headers", [{}, {"authorization": "Bearer forged"}])
def test_gateway_rejects_missing_or_invalid_token(client, upstream, headers):
    assert invoke(client, token=False, headers=headers).status_code == 401
    assert upstream.calls == []

def test_public_health_does_not_forward_forged_identity_or_charge(client, upstream, database):
    assert invoke(client, "health", token=False, headers={"x-digidara-user-id": "victim"}).status_code == 200
    assert "x-digidara-user-id" not in upstream.calls[0][1]["headers"]
    with database() as session:
        assert session.get(User, "learner").token_balance == 1000

def test_identity_bridge_overwrites_client_identity(client, upstream, database):
    assert invoke(client, "ensure_session", payload={"user_id": "victim", "email": "fake"}).status_code == 200
    forwarded = upstream.calls[0][1]
    assert forwarded["headers"]["x-digidara-user-id"] == "learner"
    assert "authorization" not in forwarded["headers"]
    assert json.loads(forwarded["content"])["payload"]["email"] == "learner@example.test"
    assert json.loads(forwarded["content"])["payload"]["user_id"] == "learner"
    with database() as session:
        assert session.get(User, "learner").token_balance == 1000


def test_gateway_derives_admin_header_from_platform_user(client, upstream, database):
    assert invoke(client, "get_profile", headers={"x-digidara-is-admin": "true"}).status_code == 200
    assert upstream.calls[-1][1]["headers"]["x-digidara-is-admin"] == "false"

    with database() as session:
        session.get(User, "learner").is_admin = True
        session.commit()

    assert invoke(client, "admin_list_jobs").status_code == 200
    assert upstream.calls[-1][1]["headers"]["x-digidara-is-admin"] == "true"


@pytest.mark.parametrize(
    "action",
    ["get_saved_jobs", "get_hidden_jobs", "admin_get_automation", "admin_update_automation"],
)
def test_job_database_actions_are_not_billed(client, upstream, database, action):
    assert invoke(client, action).status_code == 200
    with database() as session:
        assert session.get(User, "learner").token_balance == 1000

FREE_APTITUDE_AND_MOCK_ACTIONS = [
    "dashboard", "history", "history_detail", "profile", "analytics", "mixed_test_config",
    "save_mixed_test_config", "daily_usage", "active_interview", "status", "download_report",
    "record_focus_event", "question", "answer", "skip", "abandon", "exit_interview",
]
LLM_ACTIONS = ["create_test", "hint", "results", "start_interview", "submit_answer", "end_interview"]


@pytest.mark.parametrize("action", FREE_APTITUDE_AND_MOCK_ACTIONS)
def test_aptitude_and_mock_interview_non_llm_actions_are_not_billed(client, upstream, database, action):
    assert invoke(client, action).status_code == 200
    with database() as session:
        assert session.get(User, "learner").token_balance == 1000


@pytest.mark.parametrize("action", FREE_APTITUDE_AND_MOCK_ACTIONS)
def test_free_actions_still_work_with_an_empty_balance(client, upstream, database, action):
    with database() as session:
        session.get(User, "learner").token_balance = 0
        session.commit()
    assert invoke(client, action).status_code == 200


@pytest.mark.parametrize("action", LLM_ACTIONS)
def test_llm_actions_stay_billable(client, upstream, database, action):
    assert action not in gateway.FREE_ACTIONS
    assert invoke(client, action).status_code == 200
    with database() as session:
        assert session.get(User, "learner").token_balance == 1000 - gateway.TOKEN_COST_PER_CALL


@pytest.mark.parametrize("reported,cost", [("25", 25), ("bad", gateway.TOKEN_COST_PER_CALL), ("0", gateway.TOKEN_COST_PER_CALL)])
def test_billing_and_binary_response_forwarding(client, upstream, database, reported, cost):
    upstream.response = httpx.Response(201, content=b"%PDF-test", headers={"content-type": "application/pdf", "content-disposition": "attachment; filename=report.pdf", "x-tokens-used": reported})
    response = invoke(client)
    assert response.status_code == 201 and response.content == b"%PDF-test"
    assert response.headers["content-type"] == "application/pdf"
    assert "report.pdf" in response.headers["content-disposition"]
    assert upstream.calls[0][0] == PAYLOAD["endpoint"]
    with database() as session:
        assert session.get(User, "learner").token_balance == 1000 - cost


def test_gateway_forwards_multipart_upload_bytes_unchanged(client, upstream):
    response = client.post(
        "/gateway/agents/test-agent/invoke",
        data={
            "action": "analyze_upload",
            "payload": '{"user_id":"learner"}',
        },
        files={
            "file": ("resume.txt", io.BytesIO(b"resume upload bytes"), "text/plain"),
        },
        headers={"authorization": "Bearer " + create_access_token("learner")},
    )

    assert response.status_code == 200
    forwarded = upstream.calls[-1][1]
    assert forwarded["headers"]["content-type"].startswith("multipart/form-data")
    assert b"resume upload bytes" in forwarded["content"]

@pytest.mark.parametrize("condition,status", [("unhealthy", 503), ("host", 403), ("balance", 402), ("deleted", 401)])
def test_gateway_blocks_unavailable_or_unauthorized_calls(client, upstream, database, condition, status):
    with database() as session:
        if condition == "unhealthy": session.get(AgentRegistry, ("test-agent", "v1")).status = "unhealthy"
        if condition == "host": session.get(AgentRegistry, ("test-agent", "v1")).endpoint = "http://untrusted.test/invoke"
        if condition == "balance": session.get(User, "learner").token_balance = 0
        if condition == "deleted": session.delete(session.get(User, "learner"))
        session.commit()
    assert invoke(client).status_code == status
    assert upstream.calls == []

def test_unreachable_agent_returns_502_without_charge(client, upstream, database):
    upstream.error = httpx.ConnectError("offline")
    assert invoke(client).status_code == 502
    with database() as session:
        assert session.get(User, "learner").token_balance == 1000


def test_agent_timeout_reports_timeout_without_charge(client, upstream, database):
    upstream.error = httpx.ReadTimeout("batch still running")
    response = invoke(client, "create_test", payload={})
    assert response.status_code == 504
    assert "did not complete" in response.json()["detail"]
    with database() as session:
        assert session.get(User, "learner").token_balance == 1000


def test_batch_create_uses_longer_gateway_timeout(client, upstream, monkeypatch):
    monkeypatch.setattr(gateway, "ALLOWED_AGENT_HOSTS", {"localhost"})
    service.register(AgentRegisterRequest(**dict(PAYLOAD, agent_name="aptitude_agent")))
    response = client.post(
        "/gateway/agents/aptitude_agent/invoke",
        json={"action": "create_test", "payload": {}},
        headers={"authorization": "Bearer " + create_access_token("learner")},
    )
    assert response.status_code == 200
    assert upstream.timeouts[-1] == config.APTITUDE_CREATE_TEST_TIMEOUT_SECONDS
    assert invoke(client, "health", token=False).status_code == 200
    assert upstream.timeouts[-1] == config.AGENT_CALL_TIMEOUT_SECONDS


def test_mock_interview_generation_uses_longer_gateway_timeout(client, upstream, monkeypatch):
    monkeypatch.setattr(gateway, "ALLOWED_AGENT_HOSTS", {"localhost"})
    service.register(AgentRegisterRequest(**dict(PAYLOAD, agent_name="mock_interview_agent")))
    headers = {"authorization": "Bearer " + create_access_token("learner")}
    for action in ("start_interview", "end_interview"):
        response = client.post(
            "/gateway/agents/mock_interview_agent/invoke",
            json={"action": action, "payload": {}},
            headers=headers,
        )
        assert response.status_code == 200
        assert upstream.timeouts[-1] == config.MOCK_INTERVIEW_GENERATION_TIMEOUT_SECONDS


def test_capstone_grading_and_new_viva_attempts_get_the_long_timeout_but_other_actions_do_not(client, upstream, monkeypatch):
    monkeypatch.setattr(gateway, "ALLOWED_AGENT_HOSTS", {"localhost"})
    service.register(AgentRegisterRequest(**dict(PAYLOAD, agent_name="capstone_project_agent")))
    headers = {"authorization": "Bearer " + create_access_token("learner")}
    url = "/gateway/agents/capstone_project_agent/invoke"

    assert client.post(url, files={"docx_file": ("r.docx", b"x")}, data={"action": "upload_submission"}, headers=headers).status_code == 200
    assert upstream.timeouts[-1] == config.CAPSTONE_LONG_ACTION_TIMEOUT_SECONDS
    assert client.post(url, json={"action": "start_viva_attempt", "payload": {}}, headers=headers).status_code == 200
    assert upstream.timeouts[-1] == config.CAPSTONE_LONG_ACTION_TIMEOUT_SECONDS
    assert client.post(url, json={"action": "submit_viva_answer", "payload": {}}, headers=headers).status_code == 200
    assert upstream.timeouts[-1] == config.AGENT_CALL_TIMEOUT_SECONDS


def test_gateway_resolves_freshest_healthy_version(client, upstream, database):
    service.register(AgentRegisterRequest(**dict(PAYLOAD, version="v2", endpoint="http://localhost:9000/api/invoke")))
    with database() as session:
        session.get(AgentRegistry, ("test-agent", "v1")).last_heartbeat = datetime.utcnow() - timedelta(seconds=1)
        session.commit()
    assert invoke(client, "health", token=False).status_code == 200
    assert upstream.calls[-1][0] == "http://localhost:9000/api/invoke"
    service.mark_unhealthy("test-agent", "v2")
    assert invoke(client, "health", token=False).status_code == 200
    assert upstream.calls[-1][0] == PAYLOAD["endpoint"]

import hashlib
import hmac
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
    remote = SimpleNamespace(calls=[], response=httpx.Response(200, json={"ok": True}), error=None)
    class FakeClient:
        def __init__(self, **kwargs): pass
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

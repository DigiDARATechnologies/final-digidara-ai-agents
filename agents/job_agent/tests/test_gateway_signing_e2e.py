"""End to end: a forged admin header is rejected by the real Job Agent app once enforcing."""
import hashlib
import hmac
import json
import time
import uuid

import pytest

from job_agent.app import create_app

SECRET = "dev-only-agent-shared-secret"


def sign(body, user_id="", is_admin=""):
    timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
    key = hmac.new(SECRET.encode(), b"digidara-invoke-v1", hashlib.sha256).digest()
    canonical = "\n".join(("digidara-invoke-v1", timestamp, nonce, "POST", "/api/invoke", "job_agent", user_id, is_admin, hashlib.sha256(body).hexdigest()))
    headers = {
        "x-digidara-timestamp": timestamp, "x-digidara-nonce": nonce, "x-digidara-agent": "job_agent",
        "x-digidara-signature": hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest(),
        "content-type": "application/json",
    }
    if user_id:
        headers["x-digidara-user-id"] = user_id
    if is_admin:
        headers["x-digidara-is-admin"] = is_admin
    return headers


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AGENT_SHARED_SECRET", SECRET)
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    return create_app(testing=True).test_client()


def post(client, payload, headers):
    return client.post("/api/invoke", data=json.dumps(payload).encode(), headers=headers)


def test_forged_admin_headers_without_a_signature_are_rejected(client):
    response = client.post(
        "/api/invoke", json={"action": "admin_list_users"},
        headers={"x-digidara-user-id": "attacker", "x-digidara-is-admin": "true"},
    )
    assert response.status_code == 401
    assert response.get_json()["code"] == "invalid_service_signature"


def test_the_direct_admin_rest_route_is_protected_too(client):
    response = client.get("/api/jobs/admin/users", headers={"x-digidara-user-id": "attacker", "x-digidara-is-admin": "true"})
    assert response.status_code == 401
    assert response.get_json()["code"] == "invalid_service_signature"


def test_a_learners_signed_request_cannot_be_upgraded_to_admin(client):
    payload = {"action": "admin_list_users"}
    body = json.dumps(payload).encode()
    headers = sign(body, user_id="learner-1", is_admin="false") | {"x-digidara-is-admin": "true"}
    response = client.post("/api/invoke", data=body, headers=headers)
    assert response.status_code == 401


def test_a_signed_request_is_accepted(client):
    body = json.dumps({"action": "health"}).encode()
    response = client.post("/api/invoke", data=body, headers=sign(body, user_id="learner-1", is_admin="false"))
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_docker_healthcheck_still_works_while_enforcing(client):
    assert client.post("/api/invoke", data=b'{"action":"health"}', headers={"content-type": "application/json"}).status_code == 200
    assert client.get("/health").status_code == 200

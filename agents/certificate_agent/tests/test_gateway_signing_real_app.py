"""The real certificate_agent app: /api/invoke re-enters its own routes in-process (httpx ASGITransport)."""
import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from cert_app.main import app

SECRET = "dev-only-agent-shared-secret"


def sign(body: bytes, user_id="learner-1", is_admin="false"):
    timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
    key = hmac.new(SECRET.encode(), b"digidara-invoke-v1", hashlib.sha256).digest()
    canonical = "\n".join(("digidara-invoke-v1", timestamp, nonce, "POST", "/api/invoke", "certificate_agent", user_id, is_admin, hashlib.sha256(body).hexdigest()))
    return {
        "x-digidara-timestamp": timestamp, "x-digidara-nonce": nonce, "x-digidara-agent": "certificate_agent",
        "x-digidara-signature": hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest(),
        "x-digidara-user-id": user_id, "x-digidara-is-admin": is_admin, "content-type": "application/json",
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AGENT_SHARED_SECRET", SECRET)
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    return TestClient(app, raise_server_exceptions=False)  # no lifespan: no registration, no DB bootstrap


def test_signed_action_reaches_its_internal_route_instead_of_failing_the_signature_check(client):
    body = json.dumps({"action": "get_history", "payload": {}}).encode()
    response = client.post("/api/invoke", content=body, headers=sign(body))
    # The internal /api/exam/history route answers (its own auth error is fine); what must not
    # happen is the middleware rejecting the handler's unsigned in-process call.
    assert "invalid_service_signature" not in response.text


def test_the_same_action_unsigned_is_rejected(client):
    response = client.post("/api/invoke", json={"action": "get_history", "payload": {}})
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_service_signature"

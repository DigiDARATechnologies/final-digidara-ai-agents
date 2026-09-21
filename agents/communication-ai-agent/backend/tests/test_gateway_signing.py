"""Gateway signature verification (communication_agent). Kept in step with orchestrator/tests/test_agent_signing.py."""
from flask import Flask, jsonify, request

from integration import agent_signing as signing

AGENT = "communication_agent"

import hashlib
import hmac
import json
import uuid

import pytest

GOLDEN_SECRET = "dev-only-agent-shared-secret"
GOLDEN_SIGNATURE = "02fb570ee471394bbc062959e8df853d4e5ac04c231a182c0359f37afddbcdee"
GOLDEN_HEADERS = {
    "x-digidara-timestamp": "1700000000",
    "x-digidara-nonce": "0123456789abcdef0123456789abcdef",
    "x-digidara-agent": "job_agent",
    "x-digidara-signature": GOLDEN_SIGNATURE,
    "x-digidara-user-id": "user-1",
    "x-digidara-is-admin": "false",
}
GOLDEN_BODY = b'{"action":"health"}'


@pytest.fixture(autouse=True)
def signing_env(monkeypatch):
    monkeypatch.setenv("AGENT_SHARED_SECRET", GOLDEN_SECRET)
    monkeypatch.delenv("AGENT_SIGNATURE_MODE", raising=False)


def sign(body=b"{}", method="POST", path="/api/invoke", user_id="", is_admin="", now=None, nonce=None, agent=None):
    """Independent re-implementation of the orchestrator's signer."""
    import time
    timestamp = str(int(now if now is not None else time.time()))
    nonce = nonce or uuid.uuid4().hex
    agent = agent or AGENT
    key = hmac.new(GOLDEN_SECRET.encode(), b"digidara-invoke-v1", hashlib.sha256).digest()
    canonical = "\n".join(("digidara-invoke-v1", timestamp, nonce, method, path, agent, user_id, is_admin, hashlib.sha256(body).hexdigest()))
    headers = {
        "x-digidara-timestamp": timestamp, "x-digidara-nonce": nonce, "x-digidara-agent": agent,
        "x-digidara-signature": hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest(),
    }
    if user_id:
        headers["x-digidara-user-id"] = user_id
    if is_admin:
        headers["x-digidara-is-admin"] = is_admin
    return headers


def verify(headers, body=b"{}", method="POST", path="/api/invoke", agent=None, now=None):
    return signing.check(headers.get, method, path, body, agent or AGENT, now=now)


def test_golden_vector_matches_the_orchestrator():
    assert verify(GOLDEN_HEADERS, GOLDEN_BODY, agent="job_agent", now=1700000000) is None


def test_valid_signature_is_accepted_once_then_seen_as_replay():
    headers = sign(user_id="u1", is_admin="false")
    assert verify(headers) is None
    assert verify(headers) == "replay"


@pytest.mark.parametrize("drop", ["x-digidara-timestamp", "x-digidara-nonce", "x-digidara-signature", "x-digidara-agent"])
def test_missing_header_is_reported(drop):
    headers = sign()
    headers.pop(drop)
    assert verify(headers) == "missing"


def test_malformed_timestamp_and_nonce():
    assert verify({**sign(), "x-digidara-timestamp": "yesterday"}) == "malformed"
    assert verify({**sign(), "x-digidara-nonce": "short"}) == "malformed"


def test_expired_and_future_timestamps_are_rejected():
    import time
    now = time.time()
    assert verify(sign(now=now - 61)) == "expired"
    assert verify(sign(now=now + 61)) == "expired"
    assert verify(sign(now=now - 55)) is None


def test_signature_for_another_agent_is_rejected():
    assert verify(sign(agent="some_other_agent")) == "wrong_recipient"


@pytest.mark.parametrize("tamper", [
    {"x-digidara-is-admin": "true"}, {"x-digidara-user-id": "victim"}, {"x-digidara-signature": "0" * 64},
])
def test_tampering_with_signed_headers_is_rejected(tamper):
    headers = {**sign(user_id="u1", is_admin="false"), **tamper}
    assert verify(headers) == "bad_signature"


def test_tampering_with_body_method_or_path_is_rejected():
    assert verify(sign(body=b'{"a":1}'), body=b'{"a":2}') == "bad_signature"
    assert verify(sign(method="POST"), method="GET") == "bad_signature"
    assert verify(sign(path="/api/invoke"), path="/api/jobs/admin/users") == "bad_signature"


def test_adding_an_admin_header_to_a_request_signed_without_one_is_rejected():
    headers = {**sign(), "x-digidara-is-admin": "true"}
    assert verify(headers) == "bad_signature"


def test_wrong_secret_is_rejected(monkeypatch):
    headers = sign()
    monkeypatch.setenv("AGENT_SHARED_SECRET", "a-different-secret")
    assert verify(headers) == "bad_signature"


def test_mode_defaults_to_warn_and_rejects_garbage(monkeypatch):
    assert signing.mode() == "warn"
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    assert signing.mode() == "enforce"
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "sometimes")
    assert signing.mode() == "warn"


def test_unsigned_health_probe_shape_is_narrow():
    assert signing.is_unsigned_health_probe("POST", b'{"action": "health"}')
    assert not signing.is_unsigned_health_probe("GET", b'{"action": "health"}')
    assert not signing.is_unsigned_health_probe("POST", b'{"action": "ensure_session"}')
    assert not signing.is_unsigned_health_probe("POST", b'{"action": "health", "payload": {"x": 1}}')
    assert not signing.is_unsigned_health_probe("POST", b'{"action": "health", "admin": true}')
    assert not signing.is_unsigned_health_probe("POST", b"not json")


def make_client():
    app = Flask(__name__)
    signing.install(app, AGENT)

    @app.post("/api/invoke")
    def invoke():
        return jsonify(admin=request.headers.get("x-digidara-is-admin"), body=request.get_json(silent=True))

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    return app.test_client()


def test_warn_mode_serves_unsigned_requests_but_logs_them(monkeypatch, caplog):
    client = make_client()
    with caplog.at_level("WARNING", logger="digidara.signing"):
        response = client.post("/api/invoke", json={"action": "x"}, headers={"x-digidara-is-admin": "true"})
    assert response.status_code == 200
    assert "gateway_signature_invalid reason=missing mode=warn" in caplog.text


def test_enforce_rejects_a_forged_admin_header(monkeypatch):
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    response = make_client().post("/api/invoke", json={"action": "admin_list_users"}, headers={"x-digidara-is-admin": "true", "x-digidara-user-id": "attacker"})
    assert response.status_code == 401
    assert response.get_json()["code"] == "invalid_service_signature"


def test_enforce_accepts_a_correctly_signed_request_and_preserves_the_body(monkeypatch):
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    body = json.dumps({"action": "get_profile", "payload": {}}).encode()
    headers = sign(body, user_id="u1", is_admin="false") | {"content-type": "application/json"}
    response = make_client().post("/api/invoke", data=body, headers=headers)
    assert response.status_code == 200
    assert response.get_json() == {"admin": "false", "body": {"action": "get_profile", "payload": {}}}


def test_enforce_rejects_a_signed_request_whose_admin_flag_was_flipped(monkeypatch):
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    body = b'{"action": "admin_list_users"}'
    headers = sign(body, user_id="u1", is_admin="false") | {"x-digidara-is-admin": "true", "content-type": "application/json"}
    assert make_client().post("/api/invoke", data=body, headers=headers).status_code == 401


def test_enforce_rejects_a_replayed_request(monkeypatch):
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    client = make_client()
    body = b"{}"
    headers = sign(body) | {"content-type": "application/json"}
    assert client.post("/api/invoke", data=body, headers=headers).status_code == 200
    assert client.post("/api/invoke", data=body, headers=headers).status_code == 401


def test_enforce_still_allows_the_docker_healthcheck_and_health_route(monkeypatch):
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "enforce")
    client = make_client()
    assert client.post("/api/invoke", data=b'{"action": "health"}', headers={"content-type": "application/json"}).status_code == 200
    assert client.get("/health").status_code == 200


def test_off_mode_skips_verification(monkeypatch):
    monkeypatch.setenv("AGENT_SIGNATURE_MODE", "off")
    assert make_client().post("/api/invoke", json={}).status_code == 200

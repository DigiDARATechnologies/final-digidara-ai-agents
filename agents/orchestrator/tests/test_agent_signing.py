import json

import pytest
from app.auth import agent_signing as signing

from test_registry_gateway import invoke, upstream  # noqa: F401  (fixture reuse)

# Copied verbatim into every agent's signing tests: the signer and each verifier
# must agree on these exact bytes.
GOLDEN_SECRET = "dev-only-agent-shared-secret"
GOLDEN_SIGNATURE = "02fb570ee471394bbc062959e8df853d4e5ac04c231a182c0359f37afddbcdee"


@pytest.fixture
def golden_secret(monkeypatch):
    monkeypatch.setattr(signing, "AGENT_SHARED_SECRET", GOLDEN_SECRET)


def golden(**overrides):
    args = dict(
        agent_name="job_agent", method="POST", endpoint="http://job-agent:5020/api/invoke",
        body=b'{"action":"health"}', user_id="user-1", is_admin="false",
        now=1700000000, nonce="0123456789abcdef0123456789abcdef",
    )
    args.update(overrides)
    return signing.sign_headers(
        args["agent_name"], args["method"], args["endpoint"], args["body"], args["user_id"], args["is_admin"],
        now=args["now"], nonce=args["nonce"],
    )


def test_golden_vector(golden_secret):
    assert golden()["x-digidara-signature"] == GOLDEN_SIGNATURE


@pytest.mark.parametrize("change", [
    {"agent_name": "aptitude_agent"}, {"method": "GET"}, {"endpoint": "http://job-agent:5020/api/other"},
    {"body": b'{"action":"health2"}'}, {"user_id": "user-2"}, {"is_admin": "true"}, {"is_admin": None},
    {"now": 1700000001}, {"nonce": "ffffffffffffffffffffffffffffffff"},
])
def test_every_signed_field_changes_the_signature(golden_secret, change):
    assert golden(**change)["x-digidara-signature"] != GOLDEN_SIGNATURE


def test_query_string_is_not_part_of_the_signed_path(golden_secret):
    assert golden(endpoint="http://job-agent:5020/api/invoke?x=1") == golden()


def test_invoke_key_is_not_the_registration_key(golden_secret):
    # A registration-style signature (raw secret, different canonical form) must not verify as an invoke one.
    import hashlib
    import hmac
    registration = hmac.new(GOLDEN_SECRET.encode(), b"anything", hashlib.sha256).hexdigest()
    assert registration != GOLDEN_SIGNATURE
    assert signing._key() != GOLDEN_SECRET.encode()


def test_gateway_signs_forwarded_calls_over_the_exact_identity_headers(client, upstream, database):  # noqa: F811
    assert invoke(client, "generate").status_code == 200
    url, kwargs = upstream.calls[0]
    headers = kwargs["headers"]
    assert headers["x-digidara-agent"] == "test-agent"
    canonical = signing.canonical_string(
        headers["x-digidara-timestamp"], headers["x-digidara-nonce"], "POST", "/api/invoke", "test-agent",
        headers["x-digidara-user-id"], headers["x-digidara-is-admin"], kwargs["content"],
    )
    assert headers["x-digidara-signature"] == signing.signature_for(signing._key(), canonical)


def test_gateway_signs_unauthenticated_health_with_empty_identity(client, upstream):  # noqa: F811
    assert invoke(client, "health", token=False).status_code == 200
    headers = upstream.calls[0][1]["headers"]
    canonical = signing.canonical_string(
        headers["x-digidara-timestamp"], headers["x-digidara-nonce"], "POST", "/api/invoke", "test-agent",
        "", "", upstream.calls[0][1]["content"],
    )
    assert headers["x-digidara-signature"] == signing.signature_for(signing._key(), canonical)


def test_each_forwarded_call_has_a_fresh_nonce(client, upstream):  # noqa: F811
    invoke(client, "generate")
    invoke(client, "generate")
    nonces = {call[1]["headers"]["x-digidara-nonce"] for call in upstream.calls}
    assert len(nonces) == 2


def test_body_is_signed_after_ensure_session_rewrites_it(client, upstream):  # noqa: F811
    invoke(client, "ensure_session", payload={"user_id": "victim", "email": "fake"})
    headers, sent = upstream.calls[0][1]["headers"], upstream.calls[0][1]["content"]
    assert json.loads(sent)["payload"]["user_id"] == "learner"
    canonical = signing.canonical_string(
        headers["x-digidara-timestamp"], headers["x-digidara-nonce"], "POST", "/api/invoke", "test-agent",
        "learner", "false", sent,
    )
    assert headers["x-digidara-signature"] == signing.signature_for(signing._key(), canonical)

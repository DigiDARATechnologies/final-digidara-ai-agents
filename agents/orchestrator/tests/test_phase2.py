"""Phase 2: learner profile and levels, the A2A hub, readiness, organizations."""
import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.a2a import routes as a2a_routes
from app.auth import routes as auth_routes
from app.auth import service as auth_service
from app.auth import service_auth
from app.auth.security import create_access_token
from app.gateway import routes as gateway
from app.learner import routes as learner_routes
from app.learner import service as learner_service
from app.models import A2ATask, AgentLevel, LearnerProfile, OrganizationMember, ReadinessSnapshot, User
from app.organizations import routes as org_routes
from app.registry import routes as registry_routes
from app.registry import service as registry_service
from app.schemas import AgentRegisterRequest

AGENTS = (
    "codeforge_agent", "mock_interview_agent", "aptitude_agent", "communication_agent",
    "resume_builder_agent", "capstone_project_agent", "certificate_agent", "job_agent",
)
# What each fake agent reports for get_student_summary; None = action unknown.
SUMMARY_SCORES = {"codeforge_agent": 80, "mock_interview_agent": 60, "aptitude_agent": 70}


def auth(user_id="learner"):
    return {"authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def app_client(database):
    app = FastAPI()
    for module in (registry_routes, gateway, learner_routes, org_routes, a2a_routes, auth_routes):
        app.include_router(module.router)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def users(database):
    with database() as session:
        for user_id, name in (("learner", "Learner"), ("admin", "Org Admin"), ("other", "Other")):
            session.add(User(id=user_id, name=name, email=f"{user_id}@example.test", email_verified=True,
                             token_balance=1000, password_hash="x"))
        session.commit()


@pytest.fixture
def agents(app_client, database, monkeypatch, users):
    for name in AGENTS:
        registry_service.register(AgentRegisterRequest(
            agent_name=name, version="v1", endpoint=f"http://localhost:9000/{name}",
            description=f"{name} description", input_schema={},
        ))
    remote = SimpleNamespace(calls=[])

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            body = json.loads(kwargs["content"])
            agent = url.rsplit("/", 1)[-1]
            remote.calls.append((agent, body, kwargs["headers"]))
            if body["action"] == "get_student_summary":
                score = SUMMARY_SCORES.get(agent)
                if score is None:
                    return httpx.Response(400, json={"error": "Unknown action"})
                return httpx.Response(200, json={
                    "schema": "digidara.student_summary.v1", "score": score, "activity_count": 3,
                    "strengths": ["Arrays"], "gaps": ["Dynamic programming"], "metrics": {"tests": 3},
                })
            if body["action"] == "report":
                return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})
            return httpx.Response(200, json={"ok": True, "echo": body.get("payload")})

    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(gateway, "ALLOWED_AGENT_HOSTS", {"localhost"})
    return remote


def rpc(method, params, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def send(action, payload=None, **message):
    return rpc("message/send", {"message": {
        "kind": "message", "role": "user", "messageId": uuid.uuid4().hex,
        "parts": [{"kind": "data", "data": {"action": action, "payload": payload or {}}}], **message,
    }})


# --- learner profile and levels -------------------------------------------

def test_every_agent_starts_at_beginner(app_client, users):
    body = app_client.get("/learner/profile", headers=auth()).json()
    assert {level["level"] for level in body["levels"]} == {"beginner"}
    assert len(body["levels"]) == 8
    assert body["profile"]["onboarding_completed"] is False


def test_saving_the_profile_completes_onboarding_and_cleans_skills(app_client, users):
    body = app_client.put("/learner/profile", headers=auth(), json={
        "target_role": "  Data   Analyst ", "degree": "B.Sc", "skills": ["SQL", "sql", " Python ", ""], "experience": "fresher",
    }).json()
    assert body["profile"]["target_role"] == "Data Analyst"
    assert body["profile"]["skills"] == ["SQL", "Python"]
    assert body["profile"]["onboarding_completed"] is True


def test_level_changes_are_validated(app_client, users):
    assert app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "hard"}).json()["level"] == "hard"
    assert app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "expert"}).status_code == 400
    assert app_client.put("/learner/levels/unknown_agent", headers=auth(), json={"level": "hard"}).status_code == 400


def test_gateway_sends_learner_context_and_fills_difficulty(app_client, agents):
    learner_service.save_profile("learner", "Backend Developer", "B.E", ["Java"], "fresher")
    learner_service.set_level("learner", "mock_interview_agent", "medium", "self")
    response = app_client.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(),
                               json={"action": "start_interview", "payload": {"role": "SDE"}})
    assert response.status_code == 200
    _, body, _ = agents.calls[-1]
    assert body["learner"]["target_role"] == "Backend Developer"
    assert body["learner"]["level"] == "medium"
    assert body["payload"]["difficulty"] == "intermediate"


def test_a_difficulty_the_browser_chose_is_kept(app_client, agents):
    learner_service.set_level("learner", "mock_interview_agent", "hard", "self")
    app_client.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(),
                    json={"action": "start_interview", "payload": {"difficulty": "beginner"}})
    assert agents.calls[-1][1]["payload"]["difficulty"] == "beginner"


def test_difficulty_is_only_filled_for_actions_that_take_it(app_client, agents):
    app_client.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(), json={"action": "history", "payload": {}})
    assert "difficulty" not in agents.calls[-1][1]["payload"]
    assert agents.calls[-1][1]["learner"]["level"] == "beginner"


# --- A2A hub ----------------------------------------------------------------

def test_hub_and_agent_cards(app_client, agents):
    hub = app_client.get("/.well-known/agent-card.json").json()
    assert hub["protocolVersion"] == "0.3.0"
    assert {skill["id"] for skill in hub["skills"]} >= set(AGENTS) | {"readiness"}
    card = app_client.get("/a2a/mock_interview_agent/.well-known/agent-card.json").json()
    assert card["url"].endswith("/a2a/mock_interview_agent")
    assert "get_student_summary" in {skill["id"] for skill in card["skills"]}
    assert app_client.get("/a2a/missing/.well-known/agent-card.json").status_code == 404


def test_message_send_runs_the_action_and_tasks_get_returns_it(app_client, agents):
    reply = app_client.post("/a2a/aptitude_agent", headers=auth(), json=send("dashboard", {"x": 1})).json()
    task = reply["result"]
    assert task["kind"] == "task" and task["status"]["state"] == "completed"
    assert task["artifacts"][0]["parts"][0]["data"]["echo"] == {"x": 1}
    assert agents.calls[-1][2]["x-digidara-user-id"] == "learner"
    fetched = app_client.post("/a2a/aptitude_agent", headers=auth(), json=rpc("tasks/get", {"id": task["id"]})).json()
    assert fetched["result"]["id"] == task["id"]
    stranger = app_client.post("/a2a/aptitude_agent", headers=auth("other"), json=rpc("tasks/get", {"id": task["id"]})).json()
    assert stranger["error"]["code"] == -32001


def test_binary_results_come_back_as_file_parts(app_client, agents):
    task = app_client.post("/a2a/mock_interview_agent", headers=auth(), json=send("report")).json()["result"]
    part = task["artifacts"][0]["parts"][0]
    assert part["kind"] == "file" and part["file"]["mimeType"] == "application/pdf"


def test_agent_errors_become_failed_tasks(app_client, agents):
    task = app_client.post("/a2a/job_agent", headers=auth(), json=send("get_student_summary")).json()["result"]
    assert task["status"]["state"] == "failed"
    assert task["status"]["message"]["parts"][0]["text"] == "Unknown action"


@pytest.mark.parametrize("body, code", [
    ({"jsonrpc": "1.0", "id": 1, "method": "message/send"}, -32600),
    (rpc("message/stream", {}), -32004),
    (rpc("tasks/unknown", {}), -32601),
    (rpc("message/send", {"message": {"parts": []}}), -32602),
    (rpc("tasks/cancel", {"id": "nope"}), -32001),
])
def test_protocol_errors(app_client, agents, body, code):
    assert app_client.post("/a2a/aptitude_agent", headers=auth(), json=body).json()["error"]["code"] == code


def test_a2a_requires_a_login(app_client, agents):
    assert app_client.post("/a2a/aptitude_agent", json=send("dashboard")).status_code == 401


def _signed(client, path, payload, headers):
    body = json.dumps(payload).encode()
    timestamp, request_id = str(int(time.time())), uuid.uuid4().hex
    canonical = "\n".join((timestamp, request_id, "POST", path, hashlib.sha256(body).hexdigest()))
    signature = hmac.new(service_auth.AGENT_SHARED_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return client.post(path, content=body, headers={
        "content-type": "application/json", "x-agent-timestamp": timestamp,
        "x-agent-request-id": request_id, "x-agent-signature": signature, **headers,
    })


def test_agent_to_agent_call_on_a_learners_behalf(app_client, agents):
    reply = _signed(app_client, "/a2a/resume_builder_agent", send("analyze_job_description"), {
        "x-digidara-caller-agent": "job_agent", "x-digidara-on-behalf-of": "learner",
    }).json()
    assert reply["result"]["status"]["state"] == "completed"
    _, body, headers = agents.calls[-1]
    assert body["caller"] == "job_agent" and headers["x-digidara-user-id"] == "learner"


def test_agent_to_agent_call_needs_a_registered_caller(app_client, agents):
    response = _signed(app_client, "/a2a/resume_builder_agent", send("x"), {
        "x-digidara-caller-agent": "not_an_agent", "x-digidara-on-behalf-of": "learner",
    })
    assert response.status_code == 403


# --- readiness ----------------------------------------------------------------

def test_readiness_weights_untested_areas_as_zero(app_client, agents):
    body = app_client.get("/learner/readiness?refresh=true", headers=auth()).json()
    # coding 80*25 + interview 60*20 + aptitude 70*15 = 4250 / 100
    assert body["overall"] == 42.5
    assert body["band"] == "developing"
    assert body["coverage"] == {"assessed": 3, "total": 7}
    statuses = {a["agent_name"]: a["status"] for a in body["areas"]}
    assert statuses["codeforge_agent"] == "assessed" and statuses["resume_builder_agent"] == "unavailable"
    coding = next(a for a in body["areas"] if a["agent_name"] == "codeforge_agent")
    assert coding["suggested_level"] == "hard" and coding["gaps"] == ["Dynamic programming"]
    assert body["next_steps"]


def test_readiness_is_cached_then_recomputed_on_request(app_client, agents):
    app_client.get("/learner/readiness?refresh=true", headers=auth())
    calls = len(agents.calls)
    cached = app_client.get("/learner/readiness", headers=auth()).json()
    assert cached["cached"] is True and len(agents.calls) == calls
    assert len(app_client.get("/learner/readiness/history", headers=auth()).json()) == 1


def test_a_summary_request_cannot_name_someone_else(app_client, agents):
    app_client.post("/gateway/agents/aptitude_agent/invoke", headers=auth(),
                    json={"action": "get_student_summary", "payload": {"email": "other@example.test", "user_id": "other"}})
    payload = agents.calls[-1][1]["payload"]
    assert payload["email"] == "learner@example.test" and payload["user_id"] == "learner"


def test_other_agents_can_read_readiness_over_a2a(app_client, agents):
    reply = _signed(app_client, "/a2a/readiness", send("get_readiness"), {
        "x-digidara-caller-agent": "job_agent", "x-digidara-on-behalf-of": "learner",
    }).json()
    assert reply["result"]["artifacts"][0]["parts"][0]["data"]["overall"] == 42.5


# --- organizations ----------------------------------------------------------

def _make_org(client):
    return client.post("/organizations", headers=auth("admin"), json={"name": "Anna University", "kind": "college"}).json()


def test_register_join_and_share(app_client, users):
    org = _make_org(app_client)
    assert org["role"] == "owner"
    code = org["organization"]["join_code"]
    joined = app_client.post("/organizations/join", headers=auth(), json={"join_code": code.lower(), "share_progress": False}).json()
    assert joined["role"] == "member" and joined["progress_shared"] is False
    assert "join_code" not in joined["organization"]
    assert app_client.post("/organizations/join", headers=auth(), json={"join_code": code}).status_code == 409
    assert app_client.put("/organizations/me/sharing", headers=auth(), json={"share": True}).json()["progress_shared"] is True


def test_org_sees_progress_only_with_the_members_consent(app_client, agents):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]})
    members = {m["user_id"]: m for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json()}
    assert "readiness" not in members["learner"]
    member_id = members["learner"]["member_id"]
    level_url = f"/organizations/{org_id}/members/{member_id}/levels/aptitude_agent"
    assert app_client.put(level_url, headers=auth("admin"), json={"level": "hard"}).status_code == 403
    app_client.put("/organizations/me/sharing", headers=auth(), json={"share": True})
    assert app_client.put(level_url, headers=auth("admin"), json={"level": "hard"}).json()["source"] == "organization"
    refreshed = app_client.post(f"/organizations/{org_id}/members/{member_id}/readiness", headers=auth("admin")).json()
    assert refreshed["overall"] == 42.5
    member = next(m for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json() if m["user_id"] == "learner")
    assert member["readiness"]["overall"] == 42.5 and member["levels"]["aptitude_agent"] == "hard"
    summary = app_client.get(f"/organizations/{org_id}/summary", headers=auth("admin")).json()
    assert summary["sharing"] == 1 and summary["levels"]["aptitude_agent"]["hard"] == 1


def test_members_cannot_manage_the_org(app_client, users):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]})
    assert app_client.get(f"/organizations/{org_id}/members", headers=auth()).status_code == 403
    assert app_client.get(f"/organizations/{org_id}/members", headers=auth("other")).status_code == 403


def test_bulk_add_creates_accounts_once(app_client, users, database):
    org_id = _make_org(app_client)["organization"]["id"]
    results = app_client.post(f"/organizations/{org_id}/members", headers=auth("admin"), json={"members": [
        {"name": "New Student", "email": "new@example.test", "external_id": "21CS001"},
        {"email": "other@example.test"},
        {"email": "not-an-email"},
    ]}).json()["results"]
    statuses = {r["email"]: r for r in results}
    assert statuses["new@example.test"]["status"] == "created" and statuses["new@example.test"]["temporary_password"]
    assert statuses["other@example.test"]["status"] == "attached" and statuses["other@example.test"]["temporary_password"] is None
    assert statuses["not-an-email"]["status"] == "invalid_email"
    with database() as session:
        created = session.query(User).filter_by(email="new@example.test").one()
        assert created.consent_accepted_at is None
    again = app_client.post(f"/organizations/{org_id}/members", headers=auth("admin"), json={"members": [{"email": "new@example.test"}]}).json()
    assert again["results"][0]["status"] == "already_in_organization"


def test_created_member_gives_their_own_consent(app_client, users, database):
    org_id = _make_org(app_client)["organization"]["id"]
    app_client.post(f"/organizations/{org_id}/members", headers=auth("admin"), json={"members": [{"email": "new@example.test"}]})
    with database() as session:
        new_id = session.query(User).filter_by(email="new@example.test").one().id
    assert app_client.get("/learner/profile", headers=auth(new_id)).json()["consent_required"] is True
    body = app_client.post("/learner/consent", headers=auth(new_id), json={"consent": True, "share_progress": True}).json()
    assert body["consent_required"] is False and body["membership"]["progress_shared"] is True


def test_the_last_owner_cannot_leave(app_client, users):
    _make_org(app_client)
    assert app_client.delete("/organizations/me", headers=auth("admin")).status_code == 409


# --- DPDP export and erasure ------------------------------------------------

def test_export_and_erasure_cover_phase2_data(app_client, agents, database):
    learner_service.save_profile("learner", "Analyst", "", [], "fresher")
    learner_service.set_level("learner", "aptitude_agent", "hard", "self")
    org = _make_org(app_client)
    app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"], "share_progress": True})
    app_client.get("/learner/readiness?refresh=true", headers=auth())
    app_client.post("/a2a/aptitude_agent", headers=auth(), json=send("dashboard"))
    exported = auth_service.export_user_data("learner")
    assert exported["learner_profile"]["target_role"] == "Analyst"
    assert exported["organization"]["organization"]["name"] == "Anna University"
    assert "join_code" not in exported["organization"]["organization"]
    assert len(exported["readiness_history"]) == 1
    auth_service.delete_user("learner")
    with database() as session:
        for model in (LearnerProfile, AgentLevel, ReadinessSnapshot, OrganizationMember, A2ATask):
            assert session.query(model).filter_by(user_id="learner").count() == 0

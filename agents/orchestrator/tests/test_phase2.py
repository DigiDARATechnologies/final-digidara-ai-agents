"""Phase 2: learner profile and levels, the A2A hub, readiness, organizations."""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta
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
from app.readiness import service as readiness_service
from app.registry import routes as registry_routes
from app.registry import service as registry_service
from app.schemas import AgentRegisterRequest

AGENTS = (
    "codeforge_agent", "mock_interview_agent", "aptitude_agent", "communication_agent",
    "resume_builder_agent", "capstone_project_agent", "certificate_agent", "job_agent",
)
# What each fake agent reports for get_student_summary; None = action unknown.
SUMMARY_SCORES = {"codeforge_agent": 80, "mock_interview_agent": 60, "aptitude_agent": 70}
# Extra summary fields per agent, for tests that need them.
SUMMARY_EXTRA: dict[str, dict] = {}


def auth(user_id="learner"):
    return {"authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def app_client(database, monkeypatch):
    from app.admin import routes as admin_routes

    from app.rate_limit import limiter

    # The platform admin check reads users through its own session import.
    monkeypatch.setattr(admin_routes, "get_session", database)
    # Join and assistant calls are rate limited per caller; every test starts fresh.
    limiter.reset()
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
        # DigiDARA's own platform admin, who creates organizations.
        session.add(User(id="platform", name="DigiDARA", email="platform@example.test", email_verified=True,
                         token_balance=1000, password_hash="x", is_admin=True))
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
                    **SUMMARY_EXTRA.get(agent, {}),
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
    assert body["profile"]["target_role"] == "data analyst"
    assert body["profile"]["skills"] == ["sql", "python"]
    assert body["profile"]["onboarding_completed"] is True


def test_level_changes_are_validated(app_client, users):
    # Moving up needs progress at the current level; moving down never does.
    up = app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "medium"})
    assert up.status_code == 409 and "not started" in up.json()["detail"]
    jump = app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "hard"})
    assert jump.status_code == 409 and "one level at a time" in jump.json()["detail"]
    learner_service.set_level("learner", "aptitude_agent", "hard", "organization")
    assert app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "beginner"}).json()["level"] == "beginner"
    assert app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "expert"}).status_code == 400
    assert app_client.put("/learner/levels/unknown_agent", headers=auth(), json={"level": "hard"}).status_code == 400


def test_gateway_sends_learner_context_and_fills_difficulty(app_client, agents):
    learner_service.save_profile("learner", "Backend Developer", "B.E", ["Java"], "fresher")
    learner_service.set_level("learner", "mock_interview_agent", "medium", "self")
    response = app_client.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(),
                               json={"action": "start_interview", "payload": {"role": "SDE"}})
    assert response.status_code == 200
    _, body, _ = agents.calls[-1]
    assert body["learner"]["target_role"] == "backend developer"
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
    (rpc("tasks/resubscribe", {}), -32004),
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
    # Only completed levels score: 80%, 60% and 70% of Beginner complete none.
    assert body["overall"] == 0
    assert body["band"] == "not_ready"
    assert body["coverage"] == {"assessed": 3, "total": 7}
    statuses = {a["agent_name"]: a["status"] for a in body["areas"]}
    assert statuses["codeforge_agent"] == "assessed" and statuses["resume_builder_agent"] == "unavailable"
    coding = next(a for a in body["areas"] if a["agent_name"] == "codeforge_agent")
    # Without a level measure the score is the progress. Coding unlocks Medium
    # only when all of Beginner is done; other agents unlock it at 50%.
    assert coding["level_progress"] == 80 and coding["level_progress_basis"] == "score"
    assert coding["can_level_up"] is False and coding["suggested_level"] is None and coding["unlock_at"] == 100
    aptitude = next(a for a in body["areas"] if a["agent_name"] == "aptitude_agent")
    assert aptitude["can_level_up"] is True and aptitude["suggested_level"] == "medium" and aptitude["unlock_at"] == 50
    assert coding["gaps"] == ["Dynamic programming"]
    assert coding["score"] == 0 and coding["quality_score"] == 80 and coding["levels_completed"] == []
    assert body["next_steps"]


def test_moving_up_needs_half_of_the_current_level(app_client, agents, monkeypatch):
    monkeypatch.setitem(SUMMARY_EXTRA, "codeforge_agent", {"level_scores": {"easy": 30, "medium": 0, "hard": 0}})
    app_client.get("/learner/readiness?refresh=true", headers=auth())
    assert agents.calls[-7:] and any(
        body["payload"].get("difficulty") == "easy" for agent, body, _ in agents.calls if agent == "codeforge_agent")
    blocked = app_client.put("/learner/levels/codeforge_agent", headers=auth(), json={"level": "medium"})
    assert blocked.status_code == 409 and "30%" in blocked.json()["detail"]
    assert app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "medium"}).status_code == 200
    # The 70% was measured at Beginner, so it does not also unlock Hard.
    assert app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "hard"}).status_code == 409


def test_a_level_change_is_measured_again_at_once(app_client, agents):
    app_client.get("/learner/readiness?refresh=true", headers=auth())
    # 80% of Beginner Coding is not enough: every Beginner problem must be solved first.
    assert app_client.put("/learner/levels/codeforge_agent", headers=auth(), json={"level": "medium"}).status_code == 409
    assert app_client.put("/learner/levels/aptitude_agent", headers=auth(), json={"level": "medium"}).status_code == 200
    calls = len(agents.calls)
    body = app_client.get("/learner/readiness?refresh=true", headers=auth()).json()
    aptitude = next(a for a in body["areas"] if a["agent_name"] == "aptitude_agent")
    assert len(agents.calls) > calls and aptitude["level"] == "medium" and aptitude["next_level"] == "hard"
    # Without asking for a refresh, the stored Beginner progress is not shown as Medium's.
    cached = next(a for a in app_client.get("/learner/readiness", headers=auth()).json()["areas"]
                  if a["agent_name"] == "aptitude_agent")
    assert cached["level"] == "medium"


def test_completing_a_level_moves_up_once(app_client, agents, monkeypatch):
    monkeypatch.setitem(SUMMARY_EXTRA, "codeforge_agent", {
        "level_scores": {"easy": 100, "medium": 0, "hard": 0}, "last_activity_at": datetime.utcnow().isoformat()})
    body = app_client.get("/learner/readiness?refresh=true", headers=auth()).json()
    coding = next(a for a in body["areas"] if a["agent_name"] == "codeforge_agent")
    assert coding["level"] == "medium" and coding["promoted_from"] == "beginner"
    # Medium is measured on its own results, so it starts at 0.
    assert coding["level_scores"]["beginner"] == 100 and coding["level_scores"]["medium"] == 0
    level = learner_service.get_levels("learner")["codeforge_agent"]
    assert level["level"] == "medium" and level["source"] == "readiness"
    # No new practice since the change: a full score does not carry it on to Hard.
    monkeypatch.setattr(readiness_service, "REFRESH_MIN_AGE", timedelta(0))
    calls = len(agents.calls)
    again = app_client.get("/learner/readiness?refresh=true", headers=auth()).json()
    assert len(agents.calls) > calls and "cached" not in again
    assert learner_service.get_levels("learner")["codeforge_agent"]["level"] == "medium"


def test_organization_levels_are_not_moved_automatically(app_client, agents, monkeypatch):
    learner_service.set_level("learner", "codeforge_agent", "beginner", "organization")
    monkeypatch.setitem(SUMMARY_EXTRA, "codeforge_agent", {
        "level_scores": {"easy": 100, "medium": 0, "hard": 0}, "last_activity_at": datetime.utcnow().isoformat()})
    app_client.get("/learner/readiness?refresh=true", headers=auth())
    assert learner_service.get_levels("learner")["codeforge_agent"]["level"] == "beginner"


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
    assert reply["result"]["artifacts"][0]["parts"][0]["data"]["overall"] == 0


# --- organizations ----------------------------------------------------------

def _make_org(client):
    """The platform admin creates the organization with "admin" as its owner;
    returns the owner's membership."""
    created = client.post("/organizations/platform", headers=auth("platform"), json={
        "name": "Anna University", "kind": "college", "admin_email": "admin@example.test"})
    assert created.status_code == 201, created.text
    return client.get("/organizations/me", headers=auth("admin")).json()["membership"]


def test_register_join_and_share(app_client, users):
    org = _make_org(app_client)
    assert org["role"] == "owner"
    code = org["organization"]["join_code"]
    # Joining is consent: an old client's share_progress=False is ignored.
    joined = app_client.post("/organizations/join", headers=auth(), json={"join_code": code.lower(), "share_progress": False}).json()
    assert joined["role"] == "member" and joined["progress_shared"] is True
    assert "join_code" not in joined["organization"]
    assert app_client.post("/organizations/join", headers=auth(), json={"join_code": code}).status_code == 409


def test_org_sees_progress_only_with_the_members_consent(app_client, agents, database):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]})
    # A member who joined before joining meant consent, and never agreed.
    session = database()
    session.query(OrganizationMember).filter_by(user_id="learner").update({"progress_shared_at": None})
    session.commit()
    session.close()
    members = {m["user_id"]: m for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json()}
    assert "readiness" not in members["learner"]
    member_id = members["learner"]["member_id"]
    level_url = f"/organizations/{org_id}/members/{member_id}/levels/aptitude_agent"
    assert app_client.put(level_url, headers=auth("admin"), json={"level": "hard"}).status_code == 403
    app_client.put("/organizations/me/sharing", headers=auth(), json={"share": True})
    assert app_client.put(level_url, headers=auth("admin"), json={"level": "hard"}).json()["source"] == "organization"
    refreshed = app_client.post(f"/organizations/{org_id}/members/{member_id}/readiness", headers=auth("admin")).json()
    # Aptitude set to Hard: Beginner and Medium count as done (50); 70% of Hard is not.
    # 50 over the seven areas = 7.1.
    assert refreshed["overall"] == 7.1
    member = next(m for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json() if m["user_id"] == "learner")
    assert member["readiness"]["overall"] == 7.1 and member["levels"]["aptitude_agent"] == "hard"
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
    assert exported["learner_profile"]["target_role"] == "analyst"
    assert exported["organization"]["organization"]["name"] == "Anna University"
    assert "join_code" not in exported["organization"]["organization"]
    assert len(exported["readiness_history"]) == 1
    auth_service.delete_user("learner")
    with database() as session:
        for model in (LearnerProfile, AgentLevel, ReadinessSnapshot, OrganizationMember, A2ATask):
            assert session.query(model).filter_by(user_id="learner").count() == 0


# --- resume facts ---------------------------------------------------------------

def test_resume_facts_join_the_profile_and_what_agents_report(app_client, agents, monkeypatch):
    learner_service.save_profile("learner", "Data Analyst", "B.Sc Computer Science", ["SQL", "Excel"], "fresher")
    monkeypatch.setitem(SUMMARY_EXTRA, "codeforge_agent", {"resume": {
        "skills": ["Python", "sql"],
        "achievements": [{"title": "Solved 20 Python coding problems", "description": "DigiDARA Coding Practice", "x": "dropped"}],
        "projects": [{"description": "no title, dropped"}],
    }})
    facts = app_client.get("/learner/resume-facts", headers=auth()).json()
    assert facts["name"] == "Learner" and facts["email"] == "learner@example.test" and facts["target_role"] == "data analyst"
    assert facts["skills"] == ["sql", "excel", "python"]
    assert facts["projects"] == [] and "project" in facts["missing"] and "phone" in facts["missing"]
    titles = [a["title"] for a in facts["achievements"]]
    # Aptitude 70 earns a line; the interview's 60 does not.
    assert titles == ["Solved 20 Python coding problems", "Aptitude: 70% average"]
    assert "x" not in facts["achievements"][0]
    assert facts["sources"] == ["Coding", "Aptitude"]


def test_completed_levels_go_on_the_resume(app_client, agents, monkeypatch):
    monkeypatch.setitem(SUMMARY_EXTRA, "codeforge_agent", {"level_scores": {"easy": 100, "medium": 100, "hard": 20}})
    facts = app_client.get("/learner/resume-facts", headers=auth()).json()
    assert "Coding: completed Beginner and Medium levels" in [a["title"] for a in facts["achievements"]]


def test_a_new_target_role_starts_from_zero_and_switching_back_restores_it(app_client, agents):
    save = lambda role: app_client.put("/learner/profile", headers=auth(), json={
        "target_role": role, "degree": "M.Sc", "skills": ["Python", "python ", "SQL"], "experience": "fresher"}).json()
    body = save("AI Engineer")
    assert body["profile"]["target_role"] == "ai engineer" and body["profile"]["degree"] == "m.sc"
    assert body["profile"]["skills"] == ["python", "sql"]
    learner_service.set_level("learner", "aptitude_agent", "medium", "self")
    # Before any switch, every activity counts: no periods go to the agents.
    app_client.get("/learner/readiness?refresh=true", headers=auth())
    summary_calls = [body for _, body, _ in agents.calls if body["action"] == "get_student_summary"]
    assert summary_calls and all("periods" not in call["payload"] for call in summary_calls)
    assert readiness_service.latest("learner") is not None

    # Same role in other words: not a change.
    assert save("  AI   engineer")["role_history"] == []

    body = save("Data Scientist")
    assert {level["level"] for level in body["levels"]} == {"beginner"}
    assert body["role_history"][0]["role"] in {"ai engineer", "data scientist"}
    assert {r["role"]: r["levels"] for r in body["role_history"]}["ai engineer"] == {"aptitude_agent": "medium"}
    # The old role keeps the skills the learner had for it.
    assert {r["role"]: r["skills"] for r in body["role_history"]}["ai engineer"] == ["python", "sql"]
    # The new role has no readiness yet, and agents are asked only for its period.
    assert readiness_service.latest("learner") is None
    agents.calls.clear()
    app_client.get("/learner/readiness?refresh=true", headers=auth())
    periods = next(body for _, body, _ in agents.calls if body["action"] == "get_student_summary")["payload"]["periods"]
    assert len(periods) == 1 and periods[0]["start"] and periods[0]["end"] is None

    body = save("AI Engineer")
    assert {level["agent_name"]: level["level"] for level in body["levels"]}["aptitude_agent"] == "medium"
    assert len(readiness_service.history("learner")) == 1
    periods = learner_service.role_periods("learner")
    # Its first period ran from the start until the switch; the second is open.
    assert periods[0]["start"] is None and periods[0]["end"] and periods[1]["end"] is None


def test_every_completed_level_adds_25_points(app_client, agents, monkeypatch):
    # Coding measures each level: Beginner done, nothing at Medium yet.
    monkeypatch.setitem(SUMMARY_EXTRA, "codeforge_agent", {"level_scores": {"easy": 100, "medium": 0, "hard": 0}})
    monkeypatch.setitem(SUMMARY_SCORES, "mock_interview_agent", None)
    monkeypatch.setitem(SUMMARY_SCORES, "aptitude_agent", None)
    body = app_client.get("/learner/readiness?refresh=true", headers=auth()).json()
    coding = next(a for a in body["areas"] if a["agent_name"] == "codeforge_agent")
    # Completing Beginner moved the learner up to Medium, with 0% there yet: 25 points.
    assert coding["level"] == "medium" and coding["score"] == 25 and coding["levels_completed"] == ["beginner"]
    # One agent's Beginner out of seven: 25 / 7.
    assert body["overall"] == 3.6
    monkeypatch.setitem(SUMMARY_EXTRA, "codeforge_agent", {"level_scores": {"easy": 100, "medium": 40, "hard": 0}})
    monkeypatch.setattr(readiness_service, "REFRESH_MIN_AGE", timedelta(0))
    coding = next(a for a in app_client.get("/learner/readiness?refresh=true", headers=auth()).json()["areas"]
                  if a["agent_name"] == "codeforge_agent")
    # 40% of Medium is not a completed level yet.
    assert coding["score"] == 25


def test_overall_is_25_only_when_every_agent_completed_beginner(app_client, agents, monkeypatch):
    for name, _, _ in readiness_service.AREAS:
        monkeypatch.setitem(SUMMARY_SCORES, name, 90)
        monkeypatch.setitem(SUMMARY_EXTRA, name, {"level_scores": {"easy": 100, "medium": 0, "hard": 0}})
    monkeypatch.setitem(SUMMARY_EXTRA, "certificate_agent", {"level_scores": {"easy": 60, "medium": 0, "hard": 0}})
    body = app_client.get("/learner/readiness?refresh=true", headers=auth()).json()
    # Six of seven agents finished Beginner: 150 / 7.
    assert body["overall"] == 21.4
    monkeypatch.setitem(SUMMARY_EXTRA, "certificate_agent", {"level_scores": {"easy": 100, "medium": 0, "hard": 0}})
    monkeypatch.setattr(readiness_service, "REFRESH_MIN_AGE", timedelta(0))
    assert app_client.get("/learner/readiness?refresh=true", headers=auth()).json()["overall"] == 25


def test_job_fetching_follows_the_average_of_the_other_levels(app_client, users):
    levels = lambda: {level["agent_name"]: level for level in app_client.get("/learner/profile", headers=auth()).json()["levels"]}
    assert levels()["job_agent"]["level"] == "beginner" and levels()["job_agent"]["source"] == "derived"
    # Six at Beginner and one at Professional averages below Medium: still Beginner.
    learner_service.set_level("learner", "aptitude_agent", "professional", "self")
    assert levels()["job_agent"]["level"] == "beginner"
    for agent in ("codeforge_agent", "communication_agent", "mock_interview_agent"):
        learner_service.set_level("learner", agent, "medium", "self")
    # (3 + 1 + 1 + 1) / 7 rounds down to Beginner; one more Medium makes it Medium.
    assert levels()["job_agent"]["level"] == "beginner"
    learner_service.set_level("learner", "resume_builder_agent", "medium", "self")
    learner_service.set_level("learner", "capstone_project_agent", "medium", "self")
    assert levels()["job_agent"]["level"] == "medium"
    assert learner_service.learner_context("learner", "job_agent")["level"] == "medium"
    blocked = app_client.put("/learner/levels/job_agent", headers=auth(), json={"level": "hard"})
    assert blocked.status_code == 400 and "follows" in blocked.json()["detail"]


# --- organization SaaS: platform-created orgs, class join codes, insights ----

def test_only_the_platform_admin_creates_organizations(app_client, users):
    assert app_client.post("/organizations", headers=auth("admin"), json={"name": "Self Made"}).status_code == 403
    assert app_client.post("/organizations/platform", headers=auth("admin"), json={
        "name": "X College", "admin_email": "x@example.test"}).status_code == 403
    created = app_client.post("/organizations/platform", headers=auth("platform"), json={
        "name": "New College", "kind": "college", "admin_name": "Dean", "admin_email": "Dean@NewCollege.edu",
        "member_limit": 50}).json()
    assert created["admin"]["status"] == "created" and created["admin"]["email"] == "dean@newcollege.edu"
    assert len(created["admin"]["temporary_password"]) >= 10
    assert created["organization"]["member_limit"] == 50 and created["organization"]["status"] == "active"
    listed = app_client.get("/organizations/all", headers=auth("platform")).json()
    assert listed[0]["admins"] == [{"name": "Dean", "email": "dean@newcollege.edu"}] and listed[0]["active_codes"] == 1
    # The same person cannot own a second organization.
    again = app_client.post("/organizations/platform", headers=auth("platform"), json={
        "name": "Second", "admin_email": "dean@newcollege.edu"})
    assert again.status_code == 409


def test_a_class_code_places_the_learner_and_a_general_code_lets_them_choose(app_client, users):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    code = app_client.post(f"/organizations/{org_id}/codes", headers=auth("admin"), json={
        "department": "M.Sc Computer Science", "year": "1st year", "section": "A"}).json()
    assert code["label"] == "M.Sc Computer Science · 1st year · A" and code["active"] is True
    preview = app_client.get(f"/organizations/join-code/{code['code'].lower()}", headers=auth()).json()
    assert preview["organization"]["name"] == "Anna University"
    assert preview["code"]["department"] == "M.Sc Computer Science"
    assert "M.Sc Computer Science" in preview["options"]["department"] and "2nd year" in preview["options"]["year"]
    # The code's class wins over anything the learner sends.
    joined = app_client.post("/organizations/join", headers=auth(), json={
        "join_code": code["code"], "department": "Other", "section": "Z"}).json()
    assert (joined["department"], joined["year"], joined["section"]) == ("M.Sc Computer Science", "1st year", "A")

    general = org["organization"]["join_code"]
    other = app_client.post("/organizations/join", headers=auth("other"), json={
        "join_code": general, "department": "  B.Sc   Physics ", "year": "3rd year"}).json()
    assert (other["department"], other["year"], other["section"]) == ("B.Sc Physics", "3rd year", None)
    options = app_client.get(f"/organizations/{org_id}/options", headers=auth("admin")).json()
    assert "B.Sc Physics" in options["department"]
    codes = {c["code"]: c for c in app_client.get(f"/organizations/{org_id}/codes", headers=auth("admin")).json()}
    assert codes[code["code"]]["members"] == 1 and codes[general]["members"] == 1
    # A deactivated code stops working.
    app_client.patch(f"/organizations/{org_id}/codes/{code['id']}", headers=auth("admin"), json={"active": False})
    assert app_client.get(f"/organizations/join-code/{code['code']}", headers=auth()).status_code == 410
    # Learners cannot manage codes.
    assert app_client.post(f"/organizations/{org_id}/codes", headers=auth(), json={"label": "Mine"}).status_code == 403


def test_a_suspended_organization_locks_its_admins_and_codes_but_not_the_platform(app_client, users):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    app_client.patch(f"/organizations/platform/{org_id}", headers=auth("platform"), json={"status": "suspended"})
    assert app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).status_code == 403
    assert app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]}).status_code == 403
    assert app_client.get(f"/organizations/{org_id}/members", headers=auth("platform")).status_code == 200


def test_admins_filter_drill_down_and_every_look_is_logged(app_client, agents, database):
    from app.models import Conversation, ConversationMessage

    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    cs = app_client.post(f"/organizations/{org_id}/codes", headers=auth("admin"), json={"department": "CSE", "year": "2nd year"}).json()
    app_client.post("/organizations/join", headers=auth(), json={"join_code": cs["code"]})
    app_client.post("/organizations/join", headers=auth("other"), json={"join_code": org["organization"]["join_code"], "department": "ECE"})
    app_client.get("/learner/readiness?refresh=true", headers=auth())
    with database() as session:
        session.add(Conversation(id="c1", user_id="learner", agent_id="mock-interview", title="Mock interview", updated_at_ms=1))
        session.add(ConversationMessage(conversation_id="c1", user_id="learner", position=0, role="user", content="hello", display_time="10:00"))
        session.commit()

    everyone = app_client.get(f"/organizations/{org_id}/analytics", headers=auth("admin")).json()
    assert everyone["totals"]["learners"] == 2
    assert {g["name"] for g in everyone["breakdown"]["department"]} == {"CSE", "ECE"}
    cse = app_client.get(f"/organizations/{org_id}/analytics?department=CSE", headers=auth("admin")).json()
    assert cse["totals"]["learners"] == 1
    listed = app_client.get(f"/organizations/{org_id}/members?year=2nd%20year", headers=auth("admin")).json()
    assert [m["name"] for m in listed] == ["Learner"] and listed[0]["join_code"]["code"] == cs["code"]

    member_id = listed[0]["member_id"]
    detail = app_client.get(f"/organizations/{org_id}/members/{member_id}/detail", headers=auth("admin")).json()
    assert detail["member"]["department"] == "CSE" and detail["readiness"] is not None
    assert detail["conversations"][0]["title"] == "Mock interview" and detail["conversations"][0]["messages"] == 1
    chat = app_client.get(f"/organizations/{org_id}/members/{member_id}/conversations/c1", headers=auth("admin")).json()
    assert chat["messages"][0]["content"] == "hello"
    log = app_client.get(f"/organizations/{org_id}/access-log", headers=auth("admin")).json()
    assert [entry["action"] for entry in log] == ["conversation", "profile"] and log[0]["viewer"] == "Org Admin"
    # The learner sees who looked.
    mine = app_client.get("/organizations/me/access-log", headers=auth()).json()
    assert mine[0]["target"] == "Mock interview" and mine[0]["subject"] == "Learner"
    # A member of the organization cannot drill into anyone.
    assert app_client.get(f"/organizations/{org_id}/members/{member_id}/detail", headers=auth("other")).status_code == 403


# --- organization assistant ---------------------------------------------------

def _fake_model(monkeypatch, script):
    """Replays `script`: each entry is ("tool", name, args) or ("text", reply)."""
    from app.organizations import assistant

    calls = []

    def completion(**kwargs):
        calls.append(list(kwargs["messages"]))
        step = script.pop(0)
        usage = SimpleNamespace(total_tokens=100)
        if step[0] == "tool":
            call = SimpleNamespace(id=f"call{len(calls)}", function=SimpleNamespace(name=step[1], arguments=json.dumps(step[2])))
            message = SimpleNamespace(content="", tool_calls=[call])
        else:
            message = SimpleNamespace(content=step[1], tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)

    monkeypatch.setattr(assistant.litellm, "completion", completion)
    monkeypatch.setattr(assistant.assistant_memory, "recall", lambda *_a, **_k: ["Looks after the CSE batch"])
    monkeypatch.setattr(assistant.assistant_memory, "remember", lambda *_a, **_k: None)
    return calls


def test_the_assistant_answers_with_the_admins_own_tools_and_charges_tokens(app_client, agents, monkeypatch):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    cs = app_client.post(f"/organizations/{org_id}/codes", headers=auth("admin"), json={"department": "CSE"}).json()
    app_client.post("/organizations/join", headers=auth(), json={"join_code": cs["code"]})
    calls = _fake_model(monkeypatch, [
        ("tool", "find_learners", {"department": "CSE", "sort": "readiness_low"}),
        ("tool", "create_join_code", {"department": "CSE", "year": "2nd year"}),
        ("text", "Learner is the only CSE learner. I made a code for CSE 2nd year."),
    ])
    before = auth_service.get_by_id("admin").token_balance
    reply = app_client.post(f"/organizations/{org_id}/assistant", headers=auth("admin"),
                            json={"message": "Who in CSE needs help? Also make a code for CSE 2nd year.", "filters": {"department": "CSE"}}).json()
    assert reply["reply"].startswith("Learner is the only CSE learner")
    assert reply["actions"][0].startswith("Created join code") and reply["tokens"] == 300
    assert auth_service.get_by_id("admin").token_balance == before - 300
    # The model saw the organization, the dashboard filter and the remembered fact, and got compact tool results.
    system = calls[0][0]["content"]
    assert "Anna University" in system and '"department": "CSE"' in system and "Looks after the CSE batch" in system
    tool_result = calls[1][-1]["content"]
    assert '"learners":[["Learner","CSE"' in tool_result
    assert any(c["label"] == "CSE · 2nd year" for c in app_client.get(f"/organizations/{org_id}/codes", headers=auth("admin")).json())
    history = app_client.get(f"/organizations/{org_id}/assistant/history", headers=auth("admin")).json()
    assert [h["role"] for h in history] == ["user", "assistant"] and history[1]["actions"]


def test_the_assistant_needs_confirmation_to_remove_and_stays_inside_its_organization(app_client, agents, monkeypatch):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]})
    calls = _fake_model(monkeypatch, [
        ("tool", "remove_learner", {"learner": "Learner", "confirmed": False}),
        ("text", "Do you want me to remove Learner?"),
    ])
    reply = app_client.post(f"/organizations/{org_id}/assistant", headers=auth("admin"), json={"message": "remove Learner"}).json()
    assert reply["actions"] == [] and "needs_confirmation" in calls[1][-1]["content"]
    assert any(m["user_id"] == "learner" for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json())
    # A learner of the organization cannot use its assistant.
    assert app_client.post(f"/organizations/{org_id}/assistant", headers=auth(), json={"message": "hi"}).status_code == 403


def test_only_the_admins_own_yes_can_remove_a_learner(app_client, agents, monkeypatch):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]})
    url = f"/organizations/{org_id}/assistant"
    # The model claims confirmation on its own (e.g. talked into it by text in a chat): refused.
    _fake_model(monkeypatch, [("tool", "remove_learner", {"learner": "Learner", "confirmed": True}), ("text", "Should I remove Learner?")])
    assert app_client.post(url, headers=auth("admin"), json={"message": "summarise Learner's chats"}).json()["actions"] == []
    # The admin answers yes to that question: now it happens.
    _fake_model(monkeypatch, [("tool", "remove_learner", {"learner": "Learner", "confirmed": True}), ("text", "Done.")])
    done = app_client.post(url, headers=auth("admin"), json={"message": "yes"}).json()
    assert done["actions"] == ["Removed Learner from the organization"]

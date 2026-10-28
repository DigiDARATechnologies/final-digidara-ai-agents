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
        # SkillDARA's own platform admin, who creates organizations.
        session.add(User(id="platform", name="SkillDARA", email="platform@example.test", email_verified=True,
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
    # Progress inside a level counts: 80%, 60% and 70% of Beginner are worth
    # 20 + 15 + 17.5 points, over the seven areas = 7.5.
    assert body["overall"] == 7.5
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
    assert coding["score"] == 20 and coding["quality_score"] == 80 and coding["levels_completed"] == []
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
    # Below zero: MySQL rounds the stored time to the second, so "just now" can look a moment ahead.
    monkeypatch.setattr(readiness_service, "REFRESH_MIN_AGE", timedelta(seconds=-5))
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
    assert reply["result"]["artifacts"][0]["parts"][0]["data"]["overall"] == 7.5


# --- organizations ----------------------------------------------------------

def _list_students(org_id, *emails):
    """Puts emails on the organization's student list (without auto-joining
    anyone), so a join code lets those learners straight in."""
    from app import db
    from app.models import OrgRosterEntry

    session = db.get_session()
    session.add_all([OrgRosterEntry(organization_id=org_id, email=email) for email in emails])
    session.commit()
    session.close()


def _make_org(client, listed=("learner@example.test", "other@example.test")):
    """The platform admin creates the organization with "admin" as its owner;
    returns the owner's membership. The test learners are on its student list."""
    created = client.post("/organizations/platform", headers=auth("platform"), json={
        "name": "Anna University", "kind": "college", "admin_email": "admin@example.test"})
    assert created.status_code == 201, created.text
    membership = client.get("/organizations/me", headers=auth("admin")).json()["membership"]
    _list_students(membership["organization"]["id"], *listed)
    return membership


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
    # Aptitude set to Hard: Beginner and Medium count as done (50) plus 70% of
    # Hard (17.5); Coding 80% (20) and Communication 60% (15) of Beginner.
    # 102.5 over the seven areas = 14.6.
    assert refreshed["overall"] == 14.6
    member = next(m for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json() if m["user_id"] == "learner")
    assert member["readiness"]["overall"] == 14.6 and member["levels"]["aptitude_agent"] == "hard"
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
        "achievements": [{"title": "Solved 20 Python coding problems", "description": "SkillDARA Coding Practice", "x": "dropped"}],
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


def test_each_level_adds_up_to_25_points_as_it_is_done(app_client, agents, monkeypatch):
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
    # Below zero: MySQL rounds the stored time to the second, so "just now" can look a moment ahead.
    monkeypatch.setattr(readiness_service, "REFRESH_MIN_AGE", timedelta(seconds=-5))
    coding = next(a for a in app_client.get("/learner/readiness?refresh=true", headers=auth()).json()["areas"]
                  if a["agent_name"] == "codeforge_agent")
    # 40% of Medium adds 40% of its 25 points: 25 + 10.
    assert coding["score"] == 35 and coding["levels_completed"] == ["beginner"]


def test_overall_grows_with_each_agents_progress(app_client, agents, monkeypatch):
    for name, _, _ in readiness_service.AREAS:
        monkeypatch.setitem(SUMMARY_SCORES, name, 90)
        monkeypatch.setitem(SUMMARY_EXTRA, name, {"level_scores": {"easy": 100, "medium": 0, "hard": 0}})
    monkeypatch.setitem(SUMMARY_EXTRA, "certificate_agent", {"level_scores": {"easy": 60, "medium": 0, "hard": 0}})
    body = app_client.get("/learner/readiness?refresh=true", headers=auth()).json()
    # Five of the six leveled agents finished Beginner (25 each), Certification
    # is 60% through it (15); the Resume Builder has no levels and scores its
    # own result, 90: (125 + 15 + 90) / 7.
    assert body["overall"] == 32.9
    resume = next(a for a in body["areas"] if a["agent_name"] == "resume_builder_agent")
    assert resume["leveled"] is False and resume["score"] == 90 and resume["level"] is None
    assert resume["levels_completed"] == [] and resume["can_level_up"] is False
    monkeypatch.setitem(SUMMARY_EXTRA, "certificate_agent", {"level_scores": {"easy": 100, "medium": 0, "hard": 0}})
    # Below zero: MySQL rounds the stored time to the second, so "just now" can look a moment ahead.
    monkeypatch.setattr(readiness_service, "REFRESH_MIN_AGE", timedelta(seconds=-5))
    assert app_client.get("/learner/readiness?refresh=true", headers=auth()).json()["overall"] == 34.3


def test_job_fetching_follows_the_average_of_the_other_levels(app_client, users):
    levels = lambda: {level["agent_name"]: level for level in app_client.get("/learner/profile", headers=auth()).json()["levels"]}
    assert levels()["job_agent"]["level"] == "beginner" and levels()["job_agent"]["source"] == "derived"
    # Six at Beginner and one at Professional averages below Medium: still Beginner.
    learner_service.set_level("learner", "aptitude_agent", "professional", "self")
    assert levels()["job_agent"]["level"] == "beginner"
    for agent in ("codeforge_agent", "communication_agent", "mock_interview_agent"):
        learner_service.set_level("learner", agent, "medium", "self")
    # (3 + 1 + 1 + 1) / 6 is Medium: the Resume Builder has no levels and is not averaged.
    assert levels()["job_agent"]["level"] == "medium"
    learner_service.set_level("learner", "resume_builder_agent", "professional", "self")
    assert levels()["job_agent"]["level"] == "medium"
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
    # Both looks happened within the same second (MySQL keeps whole seconds), so either may be listed first.
    assert sorted(entry["action"] for entry in log) == ["conversation", "profile"] and log[0]["viewer"] == "Org Admin"
    # The learner sees who looked.
    mine = app_client.get("/organizations/me/access-log", headers=auth()).json()
    assert any(entry["target"] == "Mock interview" and entry["subject"] == "Learner" for entry in mine)
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


def test_coding_professional_progress_comes_from_passed_assessments(app_client, agents, monkeypatch):
    monkeypatch.setitem(SUMMARY_EXTRA, "codeforge_agent", {"level_scores": {"easy": 100, "medium": 100, "hard": 100, "professional": 33.3}})
    learner_service.set_level("learner", "codeforge_agent", "professional", "self")
    body = app_client.get("/learner/readiness?refresh=true", headers=auth()).json()
    coding = next(a for a in body["areas"] if a["agent_name"] == "codeforge_agent")
    # Professional is not Hard's 100% again: one of three assessments is passed.
    assert coding["level"] == "professional" and coding["level_progress"] == 33.3
    # Three levels done (75) plus a third of Professional (8.3).
    assert coding["levels_completed"] == ["beginner", "medium", "hard"] and coding["score"] == 83.3


def test_an_agents_dated_recent_activity_is_kept_cleaned_and_capped():
    rows = [{"date": "2026-09-28T06:51:28", "title": "Aptitude test", "level": "easy", "score": 173, "x": "dropped"},
            {"title": "no date"}, "not a row"] + [{"date": f"2026-09-{day:02d}"} for day in range(1, 20)]
    recent = readiness_service.summarize_reply({"score": 50, "recent": rows})["recent"]
    assert recent[0] == {"date": "2026-09-28T06:51:28", "title": "Aptitude test", "level": "easy", "score": 100.0}
    assert len(recent) <= readiness_service.RECENT_LIMIT
    assert readiness_service.summarize_reply({"score": 50})["recent"] == []


def _area(agent_name, level, progress, scores=None, basis="level"):
    return {"agent_name": agent_name, "label": agent_name, "weight": 10, "status": "assessed", "leveled": True,
            "level": level, "level_progress": progress, "level_progress_basis": basis,
            "level_scores": scores or {}, "quality_score": progress, "gaps": []}


def test_area_scores_follow_progress_in_every_level():
    # The screenshots that were wrong: Interview at Medium with 96% of Beginner,
    # Aptitude 34% into Beginner, Projects done with Medium and half of Hard.
    interview = _area("mock_interview_agent", "medium", 0, {"beginner": 96, "medium": 0, "hard": 0, "professional": 0})
    aptitude = _area("aptitude_agent", "beginner", 34, {"beginner": 34, "medium": 0, "hard": 0, "professional": 0})
    projects = _area("capstone_project_agent", "hard", 50, {"beginner": 100, "medium": 100, "hard": 50, "professional": 50})
    assert readiness_service.level_score(interview) == 24.0
    assert readiness_service.level_score(aptitude) == 8.5
    assert readiness_service.level_score(projects) == 62.5
    # An agent that does not measure each level: the levels moved past count in full.
    assert readiness_service.level_score(_area("certificate_agent", "medium", 40, basis="score")) == 35.0
    # A Professional score that copies Hard's is not counted twice below Professional.
    assert readiness_service.level_score(_area("aptitude_agent", "hard", 0, {"beginner": 100, "medium": 100, "hard": 0, "professional": 0})) == 50.0


def test_a_snapshot_saved_under_the_old_rules_is_shown_with_the_new_scores(app_client, agents, database):
    from app.models import ReadinessSnapshot
    old = _area("aptitude_agent", "beginner", 34, {"beginner": 34, "medium": 0, "hard": 0, "professional": 0})
    old.update({"score": 0, "levels_completed": []})                     # what the old rules stored
    session = database()
    session.add(ReadinessSnapshot(user_id="learner", overall=0, band="not_ready", role_key="",
                                  areas={"areas": [old], "next_steps": ["Improve Aptitude (0/100)."]}))
    session.commit()
    snapshot = session.query(ReadinessSnapshot).filter_by(user_id="learner").one()
    session.close()
    result = readiness_service.scored(snapshot)
    assert result["areas"][0]["score"] == 8.5 and result["overall"] == round(8.5 / 7, 1)
    assert result["next_steps"] == ["Improve aptitude_agent (8/100)."]     # rewritten with the new score
    assert readiness_service.area_scores(snapshot)["aptitude_agent"]["score"] == 8.5
    assert readiness_service.history("learner")[-1]["overall"] == 1.2


# --- staff logins, student lists and join requests ---------------------------

def _xlsx(rows):
    import io

    from openpyxl import Workbook

    book = Workbook()
    for row in rows:
        book.active.append(row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def test_a_code_from_someone_not_on_the_list_waits_for_staff_approval(app_client, users):
    org = _make_org(app_client, listed=())
    org_id, code = org["organization"]["id"], org["organization"]["join_code"]
    reply = app_client.post("/organizations/join", headers=auth(), json={"join_code": code}).json()
    assert reply["membership"] is None and reply["pending"]["organization"]["name"] == "Anna University"
    # No access and nothing shared while waiting.
    assert app_client.get("/organizations/me", headers=auth()).json()["membership"] is None
    assert app_client.post("/organizations/join", headers=auth(), json={"join_code": code}).status_code == 409
    waiting = app_client.get(f"/organizations/{org_id}/requests", headers=auth("admin")).json()
    assert [r["email"] for r in waiting] == ["learner@example.test"]
    # A learner cannot approve themselves.
    assert app_client.post(f"/organizations/{org_id}/requests/{waiting[0]['id']}", headers=auth(), json={"approve": True}).status_code == 403
    assert app_client.post(f"/organizations/{org_id}/requests/{waiting[0]['id']}", headers=auth("admin"), json={"approve": True}).status_code == 204
    membership = app_client.get("/organizations/me", headers=auth()).json()["membership"]
    # They agreed to share on the join screen when they asked.
    assert membership["role"] == "member" and membership["progress_shared"] is True
    assert app_client.get("/organizations/me/request", headers=auth()).json()["pending"] is None


def test_a_declined_or_cancelled_request_gives_no_access(app_client, users):
    org = _make_org(app_client, listed=())
    org_id, code = org["organization"]["id"], org["organization"]["join_code"]
    app_client.post("/organizations/join", headers=auth(), json={"join_code": code})
    request_id = app_client.get(f"/organizations/{org_id}/requests", headers=auth("admin")).json()[0]["id"]
    app_client.post(f"/organizations/{org_id}/requests/{request_id}", headers=auth("admin"), json={"approve": False})
    assert app_client.get("/organizations/me", headers=auth()).json()["membership"] is None
    app_client.post("/organizations/join", headers=auth("other"), json={"join_code": code})
    assert app_client.delete("/organizations/me/request", headers=auth("other")).status_code == 204
    assert app_client.get(f"/organizations/{org_id}/requests", headers=auth("admin")).json() == []


def _staff_login(app_client, database, org_id, email="priya@college.edu", name="Priya"):
    """An owner creates a staff login; returns the staff user id (email verified)."""
    created = app_client.post(f"/organizations/{org_id}/staff", headers=auth("admin"), json={"name": name, "email": email}).json()
    assert created["status"] in ("created", "attached", "made_staff")
    session = database()
    staff_user = session.query(User).filter_by(email=email).one()
    staff_user.email_verified = True
    session.commit()
    staff_id = staff_user.id
    session.close()
    return staff_id


def test_a_staff_code_lets_in_only_students_on_that_staff_list(app_client, users, database):
    org = _make_org(app_client, listed=())
    org_id = org["organization"]["id"]
    staff_id = _staff_login(app_client, database, org_id)
    assert app_client.get("/organizations/me", headers=auth(staff_id)).json()["membership"]["role"] == "staff"
    code = app_client.post(f"/organizations/{org_id}/codes", headers=auth(staff_id), json={"label": "CSE A"}).json()["code"]

    # "other" asks first, before the list arrives: waiting.
    assert app_client.post("/organizations/join", headers=auth("other"), json={"join_code": code}).json()["pending"]
    data = _xlsx([["S.No", "Student Name", "Mobile Number", "Email ID"],
                  [1, "Learner One", 9876543210, "Learner@Example.test"],
                  [2, "Other", "98765 43211", "other@example.test"],
                  [3, "Bad row", "", "not-an-email"]])
    result = app_client.post(f"/organizations/{org_id}/roster/upload", headers=auth(staff_id),
                             files={"file": ("students.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}).json()
    assert result["added"] == 2 and result["invalid_count"] == 1 and result["invalid"][0]["row"] == 4
    assert result["joined"] == 0 and result["approved"] == 1            # nobody joins without a code; the waiting request matches now
    # On the list, but signing in alone does not join: the student enters the code.
    assert app_client.get("/learner/profile", headers=auth()).json()["membership"] is None
    joined = app_client.post("/organizations/join", headers=auth(), json={"join_code": code}).json()
    assert joined["role"] == "member" and joined["progress_shared"] is True
    roster = {e["email"]: e for e in app_client.get(f"/organizations/{org_id}/roster", headers=auth(staff_id)).json()}
    assert roster["learner@example.test"]["mobile"] == "9876543210" and roster["learner@example.test"]["status"] == "joined"
    assert app_client.get("/organizations/me", headers=auth("other")).json()["membership"]["progress_shared"] is True


def test_a_student_on_another_staff_list_waits_for_this_staff(app_client, users, database):
    org = _make_org(app_client, listed=())
    org_id = org["organization"]["id"]
    priya = _staff_login(app_client, database, org_id)
    ravi = _staff_login(app_client, database, org_id, email="ravi@college.edu", name="Ravi")
    priya_code = app_client.post(f"/organizations/{org_id}/codes", headers=auth(priya), json={}).json()["code"]
    csv_data = "Name,Mobile,Email\nLearner,9876543210,learner@example.test\n".encode()
    app_client.post(f"/organizations/{org_id}/roster/upload", headers=auth(ravi), files={"file": ("list.csv", csv_data, "text/csv")})
    # Listed by Ravi, but used Priya's code: Priya decides.
    assert app_client.post("/organizations/join", headers=auth(), json={"join_code": priya_code}).json()["pending"]
    assert [r["email"] for r in app_client.get(f"/organizations/{org_id}/requests", headers=auth(priya)).json()] == ["learner@example.test"]
    assert app_client.get(f"/organizations/{org_id}/requests", headers=auth(ravi)).json() == []
    # Each staff member sees their own list.
    assert [e["email"] for e in app_client.get(f"/organizations/{org_id}/roster", headers=auth(ravi)).json()] == ["learner@example.test"]
    assert app_client.get(f"/organizations/{org_id}/roster", headers=auth(priya)).json() == []
    # The owner's general code matches any list in the organization.
    app_client.delete("/organizations/me/request", headers=auth())
    assert app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]}).json()["role"] == "member"


def test_every_new_join_code_is_unique(app_client, users, monkeypatch):
    from app.organizations import service as org_service

    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    issued = iter([org["organization"]["join_code"], "FRESH234"])
    monkeypatch.setattr(org_service, "_new_join_code", lambda: next(issued))
    # The first code drawn is already the organization's: a new one is drawn.
    assert app_client.post(f"/organizations/{org_id}/codes", headers=auth("admin"), json={}).json()["code"] == "FRESH234"


def test_the_student_list_template_downloads(app_client, users):
    import io

    from openpyxl import load_workbook

    org = _make_org(app_client)
    reply = app_client.get(f"/organizations/{org['organization']['id']}/roster/template", headers=auth("admin"))
    assert reply.status_code == 200 and "attachment" in reply.headers["content-disposition"]
    rows = list(load_workbook(io.BytesIO(reply.content)).active.iter_rows(values_only=True))
    assert rows[0] == ("Name", "Mobile", "Email") and len(rows) == 3
    assert app_client.get(f"/organizations/{org['organization']['id']}/roster/template", headers=auth()).status_code == 403


def test_staff_see_and_look_after_only_their_own_students(app_client, users, database):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    staff_id = _staff_login(app_client, database, org_id)
    code = app_client.post(f"/organizations/{org_id}/codes", headers=auth(staff_id), json={"label": "CSE"}).json()["code"]
    app_client.post(f"/organizations/{org_id}/roster/upload", headers=auth(staff_id),
                    files={"file": ("list.csv", "Name,Mobile,Email\nLearner,9876543210,learner@example.test\n".encode(), "text/csv")})
    app_client.post("/organizations/join", headers=auth(), json={"join_code": code})                         # staff student
    app_client.post("/organizations/join", headers=auth("other"), json={"join_code": org["organization"]["join_code"]})  # owner student
    mine = {m["user_id"]: m for m in app_client.get(f"/organizations/{org_id}/members", headers=auth(staff_id)).json()}
    assert list(mine) == ["learner"]
    everyone = {m["user_id"] for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json()}
    assert {"learner", "other", "admin", staff_id} <= everyone
    assert app_client.get(f"/organizations/{org_id}/analytics", headers=auth(staff_id)).json()["totals"]["learners"] == 1
    other_member = next(m["member_id"] for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json() if m["user_id"] == "other")
    assert app_client.get(f"/organizations/{org_id}/members/{other_member}/detail", headers=auth(staff_id)).status_code == 404
    assert app_client.put(f"/organizations/{org_id}/members/{other_member}/levels/aptitude_agent", headers=auth(staff_id),
                          json={"level": "medium"}).status_code == 404
    learner_member = mine["learner"]["member_id"]
    assert app_client.get(f"/organizations/{org_id}/members/{learner_member}/detail", headers=auth(staff_id)).status_code == 200
    assert app_client.put(f"/organizations/{org_id}/members/{learner_member}/levels/aptitude_agent", headers=auth(staff_id),
                          json={"level": "medium"}).status_code == 200
    # Their own codes only.
    assert [c["code"] for c in app_client.get(f"/organizations/{org_id}/codes", headers=auth(staff_id)).json()] == [code]
    # Not theirs to do:
    assert app_client.post(f"/organizations/{org_id}/staff", headers=auth(staff_id), json={"email": "x@example.test"}).status_code == 403
    assert app_client.delete(f"/organizations/{org_id}/members/{learner_member}", headers=auth(staff_id)).status_code == 403
    assert app_client.post(f"/organizations/{org_id}/members", headers=auth(staff_id),
                           json={"members": [{"email": "y@example.test"}]}).status_code == 403
    assert app_client.patch(f"/organizations/{org_id}/members/{learner_member}", headers=auth(staff_id), json={"role": "admin"}).status_code == 403
    assert {s["role"] for s in app_client.get(f"/organizations/{org_id}/staff", headers=auth("admin")).json()} == {"owner", "staff"}


def test_a_csv_without_a_header_is_read_by_its_columns():
    from app.organizations import roster

    # A gmail address contains "mail", but the row is still a student, not a header.
    rows = roster.parse_upload("list.csv", "Asha,asha@gmail.com,9876543210\nRavi,ravi@x.io,9123456780\n".encode())
    assert rows == [{"name": "Asha", "mobile": "9876543210", "email": "asha@gmail.com"},
                    {"name": "Ravi", "mobile": "9123456780", "email": "ravi@x.io"}]
    with pytest.raises(roster.OrgError):
        roster.parse_upload("old.xls", b"\xd0\xcf\x11\xe0")


# --- leaderboards ---------------------------------------------------------------

def _score(database, user_id, overall, minutes_ago=0):
    from app.readiness import leaderboard

    session = database()
    session.add(ReadinessSnapshot(user_id=user_id, overall=overall, band="developing", areas={}, role_key="",
                                  computed_at=datetime.utcnow() - timedelta(minutes=minutes_ago)))
    session.commit()
    session.close()
    leaderboard.clear_cache()


def _add_user(database, user_id, name):
    session = database()
    session.add(User(id=user_id, name=name, email=f"{user_id}@example.test", email_verified=True, token_balance=10, password_hash="x"))
    session.commit()
    session.close()


def test_students_see_the_platform_student_board_by_readiness(app_client, users, database):
    _make_org(app_client)                                    # "admin" owns an organization: staff, not a student
    _add_user(database, "third", "Third Person")
    _score(database, "learner", 40)
    _score(database, "other", 70)
    _score(database, "third", 70, minutes_ago=5)            # same score, reached earlier: ranks first
    _score(database, "admin", 90)
    _score(database, "platform", 99)                         # SkillDARA staff never rank
    body = app_client.get("/learner/leaderboard", headers=auth()).json()
    assert body["group"] == "students" and body["allowed_groups"] == ["students"]
    assert [(e["user_id"], e["rank"]) for e in body["entries"]] == [("third", 1), ("other", 2), ("learner", 3)]
    assert body["top"][0]["name"] == "Third P." and body["me"] == {"rank": 3, "score": 40.0}
    assert body["top"][2]["is_me"] is True
    # The staff board is not for students.
    assert app_client.get("/learner/leaderboard?group=staff", headers=auth()).status_code == 403


def test_admins_see_both_boards_of_their_organization_only(app_client, users, database):
    org = _make_org(app_client)
    app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]})
    _score(database, "learner", 40)
    _score(database, "other", 70)                            # not in the organization
    admin_view = app_client.get("/learner/leaderboard", headers=auth("admin")).json()
    assert admin_view["scope"] == "organization" and admin_view["allowed_scopes"] == ["organization"]
    assert admin_view["allowed_groups"] == ["students", "staff"] and admin_view["organization"]["name"] == "Anna University"
    assert [e["user_id"] for e in admin_view["entries"]] == ["learner"]
    assert app_client.get("/learner/leaderboard?scope=platform", headers=auth("admin")).status_code == 403
    # A member who stops sharing leaves the organization board.
    app_client.put("/organizations/me/sharing", headers=auth(), json={"share": False})
    assert app_client.get("/learner/leaderboard?scope=organization", headers=auth("admin")).json()["entries"] == []
    # Students in an organization see it and the platform; others only the platform.
    student = app_client.get("/learner/leaderboard", headers=auth()).json()
    assert student["scope"] == "organization" and student["allowed_scopes"] == ["organization", "platform"]
    assert app_client.get("/learner/leaderboard", headers=auth("other")).json()["scope"] == "platform"
    assert app_client.get("/learner/leaderboard?scope=organization", headers=auth("other")).status_code == 404


def test_staff_are_ranked_on_their_students_readiness_and_activity(app_client, users, database):
    from app.models import TokenUsageEvent

    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    priya = _staff_login(app_client, database, org_id)
    ravi = _staff_login(app_client, database, org_id, email="ravi@college.edu", name="Ravi Kumar")
    priya_code = app_client.post(f"/organizations/{org_id}/codes", headers=auth(priya), json={}).json()["code"]
    ravi_code = app_client.post(f"/organizations/{org_id}/codes", headers=auth(ravi), json={}).json()["code"]
    for staff_id, email in ((priya, "learner@example.test"), (ravi, "other@example.test")):
        app_client.post(f"/organizations/{org_id}/roster/upload", headers=auth(staff_id),
                        files={"file": ("list.csv", f"Name,Mobile,Email\nX,9876543210,{email}\n".encode(), "text/csv")})
    app_client.post("/organizations/join", headers=auth(), json={"join_code": priya_code})
    app_client.post("/organizations/join", headers=auth("other"), json={"join_code": ravi_code})
    _score(database, "learner", 50)
    _score(database, "other", 60)
    session = database()
    session.add(TokenUsageEvent(user_id="learner", agent_name="aptitude_agent", action="start", tokens=10))   # Priya's student is active
    session.commit()
    session.close()
    body = app_client.get("/learner/leaderboard", headers=auth(priya)).json()
    assert body["group"] == "staff" and body["allowed_groups"] == ["staff"] and body["allowed_scopes"] == ["organization"]
    # Priya: 0.7 x 50 + 0.3 x 100 = 65. Ravi: 0.7 x 60 + 0 = 42.
    assert [(e["user_id"], e["score"]) for e in body["entries"]] == [(priya, 65.0), (ravi, 42.0)]
    assert body["entries"][0]["staff"] == {"students": 1, "average_readiness": 50.0, "active_percent": 100}
    assert app_client.get("/learner/leaderboard?group=students", headers=auth(priya)).status_code == 403
    assert app_client.get("/learner/leaderboard?scope=platform", headers=auth(priya)).status_code == 403
    assert [e["user_id"] for e in app_client.get("/learner/leaderboard?group=staff", headers=auth("admin")).json()["entries"]] == [priya, ravi]


def test_someone_breaking_into_the_top_3_is_new_and_learners_can_hide(app_client, users, database):
    for user_id, name in (("s1", "Asha One"), ("s2", "Ravi Two"), ("s3", "Kavi Three"), ("s4", "Nila Four")):
        _add_user(database, user_id, name)
    for user_id, score in (("s1", 90), ("s2", 80), ("s3", 70), ("s4", 10)):
        _score(database, user_id, score)
    first = app_client.get("/learner/leaderboard", headers=auth()).json()
    assert [e["user_id"] for e in first["top"]] == ["s1", "s2", "s3"]
    assert not any(e["new_in_top"] for e in first["top"])    # the first top 3 ever seen broke into nothing
    _score(database, "s4", 85, minutes_ago=-1)          # later than the first (MySQL keeps whole seconds)
    second = app_client.get("/learner/leaderboard", headers=auth()).json()
    assert [(e["user_id"], e["new_in_top"]) for e in second["top"]] == [("s1", False), ("s4", True), ("s2", False)]
    app_client.put("/learner/leaderboard/visibility", headers=auth("s4"), json={"hidden": True})
    third = app_client.get("/learner/leaderboard", headers=auth("s4")).json()
    assert "s4" not in [e["user_id"] for e in third["entries"]] and third["hidden"] is True and third["me"] is None


def test_an_admin_puts_an_existing_student_under_a_staff_member(app_client, users, database):
    org = _make_org(app_client)
    org_id = org["organization"]["id"]
    staff_id = _staff_login(app_client, database, org_id)
    # Joined with the owner's general code: under no staff member yet.
    app_client.post("/organizations/join", headers=auth(), json={"join_code": org["organization"]["join_code"]})
    assert app_client.get(f"/organizations/{org_id}/members", headers=auth(staff_id)).json() == []
    members = {m["user_id"]: m for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json()}
    assert members["learner"]["staff_user_id"] is None
    staff_member = next(s["member_id"] for s in app_client.get(f"/organizations/{org_id}/staff", headers=auth("admin")).json() if s["user_id"] == staff_id)
    url = f"/organizations/{org_id}/members/{members['learner']['member_id']}/staff"
    assert app_client.put(url, headers=auth(staff_id), json={"staff_member_id": staff_member}).status_code == 403   # staff cannot
    assert app_client.put(url, headers=auth("admin"), json={"staff_member_id": staff_member}).status_code == 200
    assert [m["user_id"] for m in app_client.get(f"/organizations/{org_id}/members", headers=auth(staff_id)).json()] == ["learner"]
    members = {m["user_id"]: m for m in app_client.get(f"/organizations/{org_id}/members", headers=auth("admin")).json()}
    assert members["learner"]["staff_user_id"] == staff_id
    # And back under no one.
    assert app_client.put(url, headers=auth("admin"), json={"staff_member_id": None}).status_code == 200
    assert app_client.get(f"/organizations/{org_id}/members", headers=auth(staff_id)).json() == []

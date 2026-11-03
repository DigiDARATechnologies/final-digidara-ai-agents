"""Proctoring (Hard/Professional interviews and vivas) and assessment links."""
import base64
import json
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.gateway import routes as gateway
from app.models import ProctorSession, ProctorSnapshot, User
from app.organizations import routes as org_routes
from app.proctoring import routes as proctoring_routes
from app.proctoring import service
from app.registry import service as registry_service
from app.schemas import AgentRegisterRequest

JPEG = base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 200).decode()


def auth(user_id="learner"):
    return {"authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def api(database, monkeypatch):
    from app.admin import routes as admin_routes
    from app.rate_limit import limiter

    monkeypatch.setattr(admin_routes, "get_session", database)
    limiter.reset()
    with database() as session:
        for user_id in ("learner", "admin", "other"):
            session.add(User(id=user_id, name=user_id.title(), email=f"{user_id}@example.test", email_verified=True,
                             token_balance=1000, password_hash="x"))
        session.add(User(id="platform", name="SkillDARA", email="platform@example.test", email_verified=True,
                         token_balance=1000, password_hash="x", is_admin=True))
        session.commit()
    app = FastAPI()
    for module in (gateway, org_routes, proctoring_routes):
        app.include_router(module.router)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def interview_agent(api, monkeypatch):
    """A fake mock interview agent that records what it was asked."""
    for name in ("mock_interview_agent", "capstone_project_agent"):
        registry_service.register(AgentRegisterRequest(
            agent_name=name, version="v1", endpoint=f"http://localhost:9000/{name}",
            description=name, input_schema={}))
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            body = json.loads(kwargs["content"])
            calls.append(body)
            action = body["action"]
            if action == "start_interview":
                return httpx.Response(200, json={"interview_id": 77, "question_order": 1, "question": "Q1"})
            if action == "end_interview":
                return httpx.Response(200, json={"total_marks": 7, "max_marks": 10, "overall_score": 7.2})
            if action == "submit_viva_answer":
                return httpx.Response(200, json={"viva_passed": True, "viva_rating": "Good", "viva_score": 80})
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(gateway.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(gateway, "ALLOWED_AGENT_HOSTS", {"localhost"})
    return calls


def _make_org(client):
    created = client.post("/organizations/platform", headers=auth("platform"), json={
        "name": "Anna University", "kind": "college", "admin_email": "admin@example.test"})
    assert created.status_code == 201, created.text
    org = client.get("/organizations/me", headers=auth("admin")).json()["membership"]
    # The learner is on the student list, so the join code lets them straight in.
    from app import db
    from app.models import OrgRosterEntry

    session = db.get_session()
    session.add(OrgRosterEntry(organization_id=org["organization"]["id"], email="learner@example.test"))
    session.commit()
    session.close()
    return org["organization"]["id"], org["organization"]["join_code"]


def _assessment(client, org_id, **extra):
    body = {"title": "Placement drive round 1", "config": {
        "round_type": "technical", "role_name": "Data Analyst", "num_questions": 5, "level": "hard"},
        "proctoring": {"tab": True, "fullscreen": True, "copy_paste": True, "webcam": True, "face": False,
                       "max_warnings": 2}, **extra}
    created = client.post(f"/organizations/{org_id}/assessments", headers=auth("admin"), json=body)
    assert created.status_code == 201, created.text
    return created.json()


# --- practice sittings ------------------------------------------------------

def test_practice_needs_consent_and_reload_is_a_warning(api):
    refused = api.post("/proctoring/sessions", headers=auth(), json={"agent_name": "mock_interview_agent", "ref": "5"})
    assert refused.status_code == 400
    started = api.post("/proctoring/sessions", headers=auth(),
                       json={"agent_name": "mock_interview_agent", "ref": "5", "consent": True}).json()
    assert started["settings"]["webcam"] and started["integrity"] == 100 and started["warnings"] == 0
    again = api.post("/proctoring/sessions", headers=auth(),
                     json={"agent_name": "mock_interview_agent", "ref": "5", "consent": True}).json()
    assert again["id"] == started["id"] and again["warnings"] == 1 and again["integrity"] == 95
    # Another learner cannot see or write to it.
    assert api.get(f"/proctoring/sessions/{started['id']}", headers=auth("other")).status_code == 404


def test_too_many_warnings_end_the_test(api):
    sid = api.post("/proctoring/sessions", headers=auth(),
                   json={"agent_name": "capstone_project_agent", "ref": "sub1:1", "consent": True}).json()["id"]
    state = api.post(f"/proctoring/sessions/{sid}/events", headers=auth(), json={"events": [
        {"kind": "copy"}, {"kind": "focus_lost"}, {"kind": "fullscreen_exit"}, {"kind": "bogus"},
        {"kind": "session_resumed"}]}).json()
    assert state["warnings"] == 2 and state["integrity"] == 87 and not state["terminated"]
    state = api.post(f"/proctoring/sessions/{sid}/events", headers=auth(), json={"events": [
        {"kind": "focus_lost"}, {"kind": "focus_lost"}]}).json()
    assert state["terminated"] and state["warnings"] == 4
    # Nothing more is counted once it has ended.
    after = api.post(f"/proctoring/sessions/{sid}/events", headers=auth(), json={"events": [{"kind": "paste"}]}).json()
    assert after["integrity"] == state["integrity"]


def test_snapshots_are_checked_for_faces(api, database, monkeypatch):
    monkeypatch.setattr(service, "_vision_check", lambda raw: {"faces": 2, "phone": False, "note": "two people"})
    sid = api.post("/proctoring/sessions", headers=auth(),
                   json={"agent_name": "mock_interview_agent", "ref": "9", "consent": True}).json()["id"]
    assert api.post(f"/proctoring/sessions/{sid}/snapshots", headers=auth(), json={"image": "bm90IGEganBlZw=="}).status_code == 400
    assert api.post(f"/proctoring/sessions/{sid}/snapshots", headers=auth(),
                    json={"image": "data:image/jpeg;base64," + JPEG}).status_code == 200
    state = api.get(f"/proctoring/sessions/{sid}", headers=auth()).json()
    assert state["integrity"] == 90
    # A photo checked after the test ended still counts.
    with database() as session:
        snapshot_id = session.query(ProctorSnapshot).one().id
    api.post(f"/proctoring/sessions/{sid}/end", headers=auth())
    service.check_snapshot(snapshot_id)
    assert api.get(f"/proctoring/sessions/{sid}", headers=auth()).json()["integrity"] == 80
    with database() as session:
        assert session.query(ProctorSnapshot).one().faces == 2


def test_old_snapshots_are_deleted(api, database):
    sid = api.post("/proctoring/sessions", headers=auth(),
                   json={"agent_name": "mock_interview_agent", "ref": "3", "consent": True}).json()["id"]
    with database() as session:
        session.add(ProctorSnapshot(session_id=sid, image=b"\xff\xd8old",
                                    created_at=datetime.utcnow() - timedelta(days=service.SNAPSHOT_RETENTION_DAYS + 1)))
        session.add(ProctorSnapshot(session_id=sid, image=b"\xff\xd8new"))
        session.commit()
    assert service.purge_old_snapshots(force=True) == 1


# --- assessment links ---------------------------------------------------------

def test_assessment_link_runs_the_admins_interview(api, interview_agent, database):
    org_id, code = _make_org(api)
    created = _assessment(api, org_id)
    token = created["path"].rsplit("/", 1)[-1]
    assert created["proctoring"]["max_warnings"] == 2 and created["config"]["level_label"] == "Hard"

    # Only members (the default) may take it.
    preview = api.get(f"/assessments/{token}", headers=auth()).json()
    assert not preview["can_start"] and "member" in preview["reason"]
    api.post("/organizations/join", headers=auth(), json={"join_code": code})
    preview = api.get(f"/assessments/{token}", headers=auth()).json()
    assert preview["can_start"] and preview["organization"] == "Anna University"
    assert api.post(f"/assessments/{token}/start", headers=auth(), json={}).status_code == 400
    started = api.post(f"/assessments/{token}/start", headers=auth(), json={"consent": True}).json()
    assert started["settings"]["face"] is False

    # Whatever the browser asks for, the interview is the admin's.
    response = api.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(), json={
        "action": "start_interview", "payload": {"round_type": "hr", "num_questions": 15, "difficulty": "beginner",
                                                 "interview_mode": "course", "subject": "easy stuff"}})
    assert response.status_code == 200
    sent = interview_agent[-1]["payload"]
    assert sent["round_type"] == "technical" and sent["num_questions"] == 5 and sent["difficulty"] == "advanced"
    assert sent["interview_mode"] == "role" and sent["role_name"] == "Data Analyst" and "subject" not in sent

    # The score comes from the agent's own reply.
    api.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(), json={
        "action": "end_interview", "payload": {"interview_id": 77}})
    attempts = api.get(f"/organizations/{org_id}/assessments/{created['id']}/attempts", headers=auth("admin")).json()
    assert len(attempts) == 1 and attempts[0]["status"] == "completed"
    assert attempts[0]["result"]["score"] == 7 and attempts[0]["ref"] == "77"

    # One attempt only; a later interview is not changed.
    again = api.post(f"/assessments/{token}/start", headers=auth(), json={"consent": True})
    assert again.status_code == 409
    api.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(), json={
        "action": "start_interview", "payload": {"round_type": "hr", "num_questions": 15, "interview_mode": "course"}})
    assert interview_agent[-1]["payload"]["round_type"] == "hr"

    # The admin sees the timeline; another organization's admin does not.
    detail = api.get(f"/organizations/{org_id}/proctoring/{attempts[0]['session_id']}", headers=auth("admin"))
    assert detail.status_code == 200 and detail.json()["retention_days"] == 30
    assert api.get(f"/organizations/{org_id}/proctoring/{attempts[0]['session_id']}", headers=auth("other")).status_code == 403


def test_assessment_window_and_switching_off(api):
    org_id, _ = _make_org(api)
    later = (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"
    created = _assessment(api, org_id, opens_at=later, members_only=False)
    token = created["path"].rsplit("/", 1)[-1]
    assert api.get(f"/assessments/{token}", headers=auth()).json()["window"] == "not_open"
    opened = _assessment(api, org_id, members_only=False)
    token = opened["path"].rsplit("/", 1)[-1]
    assert api.get(f"/assessments/{token}", headers=auth("other")).json()["can_start"]
    api.patch(f"/organizations/{org_id}/assessments/{opened['id']}", headers=auth("admin"), json={"active": False})
    assert api.post(f"/assessments/{token}/start", headers=auth("other"), json={"consent": True}).status_code == 403
    assert api.get("/assessments/not-a-real-token", headers=auth()).status_code == 404
    # Members cannot create links.
    bad = api.post(f"/organizations/{org_id}/assessments", headers=auth("learner"), json={"title": "x" * 5, "config": {"role_name": "a"}})
    assert bad.status_code in (403, 404)


def test_viva_result_is_recorded(api, interview_agent, database):
    sid = api.post("/proctoring/sessions", headers=auth(),
                   json={"agent_name": "capstone_project_agent", "ref": "subX:1", "consent": True}).json()["id"]
    api.post("/gateway/agents/capstone_project_agent/invoke", headers=auth(), json={
        "action": "submit_viva_answer", "payload": {"submission_id": "subX", "question_id": 1, "answer": "a"}})
    with database() as session:
        ps = session.get(ProctorSession, sid)
        assert ps.status == "completed" and ps.result == {"label": "Good", "passed": True}


def test_member_practice_sessions_need_consent(api, database):
    org_id, code = _make_org(api)
    api.post("/organizations/join", headers=auth(), json={"join_code": code})
    api.post("/proctoring/sessions", headers=auth(), json={"agent_name": "mock_interview_agent", "ref": "1", "consent": True})
    members = api.get(f"/organizations/{org_id}/members", headers=auth("admin")).json()
    member_id = next(m["member_id"] for m in members if m.get("user_id") == "learner" or m.get("email") == "learner@example.test")
    rows = api.get(f"/organizations/{org_id}/members/{member_id}/proctoring", headers=auth("admin")).json()
    assert len(rows) == 1 and rows[0]["agent_name"] == "mock_interview_agent"


@pytest.mark.parametrize("module", ["app.organizations.service", "app.proctoring.service", "app.gateway.routes"])
def test_modules_import_in_any_order(module):
    """organizations -> readiness -> gateway -> proctoring is an import cycle:
    a script that imports any of them first must still work."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    result = subprocess.run([sys.executable, "-c", f"import {module}"], cwd=Path(__file__).resolve().parents[1],
                            env={**os.environ}, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]


def test_assessment_interviews_are_paid_by_the_creator_not_the_learner(api, interview_agent, database):
    from app.auth import service as auth_service
    from app.models import User

    org_id, code = _make_org(api)
    created = _assessment(api, org_id)
    token = created["path"].rsplit("/", 1)[-1]
    api.post("/organizations/join", headers=auth(), json={"join_code": code})
    session = database()
    session.query(User).filter_by(id="learner").update({"token_balance": 0})     # a learner with no coins can still attend
    session.commit()
    session.close()
    admin_before = auth_service.get_by_id("admin").token_balance
    api.post(f"/assessments/{token}/start", headers=auth(), json={"consent": True})
    started = api.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(), json={
        "action": "start_interview", "payload": {"round_type": "technical"}})
    assert started.status_code == 200
    api.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(), json={
        "action": "end_interview", "payload": {"interview_id": 77}})
    assert auth_service.get_by_id("learner").token_balance == 0
    assert auth_service.get_by_id("admin").token_balance < admin_before

    # Outside the assessment the learner pays for themselves (and has nothing left).
    own = api.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(), json={
        "action": "start_interview", "payload": {"round_type": "hr"}})
    assert own.status_code == 402


def test_an_assessment_needs_the_creators_coins(api, interview_agent, database):
    from app.models import User

    org_id, code = _make_org(api)
    created = _assessment(api, org_id)
    token = created["path"].rsplit("/", 1)[-1]
    api.post("/organizations/join", headers=auth(), json={"join_code": code})
    session = database()
    session.query(User).filter_by(id="admin").update({"token_balance": 0})
    session.commit()
    session.close()
    # No new assessments without coins...
    assert api.post(f"/organizations/{org_id}/assessments", headers=auth("admin"), json={
        "title": "Another", "kind": "mock_interview",
        "config": {"round_type": "hr", "num_questions": 5, "level": "medium"}}).status_code == 402
    # ...and an existing one cannot start an interview, with a message for the learner.
    api.post(f"/assessments/{token}/start", headers=auth(), json={"consent": True})
    refused = api.post("/gateway/agents/mock_interview_agent/invoke", headers=auth(), json={
        "action": "start_interview", "payload": {"round_type": "technical"}})
    assert refused.status_code == 402 and "trainer" in refused.json()["detail"]


def test_learners_see_their_organizations_assessments_and_staff_ones_only_for_their_students(api, database):
    from app.models import User

    org_id, code = _make_org(api)
    staff = api.post(f"/organizations/{org_id}/staff", headers=auth("admin"), json={"name": "Priya", "email": "priya@college.edu"}).json()
    session = database()
    staff_user = session.query(User).filter_by(email="priya@college.edu").one()
    staff_user.email_verified = True
    staff_user.token_balance = 1000
    staff_id = staff_user.id
    session.commit()
    session.close()
    assert staff["status"] == "created"
    staff_code = api.post(f"/organizations/{org_id}/codes", headers=auth(staff_id), json={"label": "CSE"}).json()["code"]
    api.post(f"/organizations/{org_id}/roster/upload", headers=auth(staff_id),
             files={"file": ("list.csv", "Name,Mobile,Email\nL,9876543210,learner@example.test\n".encode(), "text/csv")})
    assert api.get("/my-assessments", headers=auth()).json() == {"member": False, "organization": None, "assessments": []}
    api.post("/organizations/join", headers=auth(), json={"join_code": staff_code})          # Priya's student
    from app.models import OrgRosterEntry

    session = database()
    session.add(OrgRosterEntry(organization_id=org_id, email="other@example.test"))   # on the owner's list
    session.commit()
    session.close()
    assert api.post("/organizations/join", headers=auth("other"), json={"join_code": code}).json()["role"] == "member"
    owner_test = _assessment(api, org_id, title="Whole college test")
    staff_test = api.post(f"/organizations/{org_id}/assessments", headers=auth(staff_id), json={
        "title": "Priya's CSE test", "kind": "mock_interview",
        "config": {"round_type": "hr", "num_questions": 5, "level": "medium"}}).json()
    mine = api.get("/my-assessments", headers=auth()).json()
    assert mine["member"] is True and {a["title"] for a in mine["assessments"]} == {"Whole college test", "Priya's CSE test"}
    assert {a["status"] for a in mine["assessments"]} == {"open"}
    theirs = api.get("/my-assessments", headers=auth("other")).json()
    assert [a["title"] for a in theirs["assessments"]] == ["Whole college test"]
    # The link of a staff member's test does not let another staff member's student in.
    token = staff_test["path"].rsplit("/", 1)[-1]
    preview = api.get(f"/assessments/{token}", headers=auth("other")).json()
    assert not preview["can_start"] and "another staff member" in preview["reason"]
    assert api.get(f"/assessments/{token}", headers=auth()).json()["can_start"]
    assert owner_test["id"]


def test_the_organization_list_shows_its_own_students_only(api, database):
    org_id, code = _make_org(api)
    api.post("/organizations/join", headers=auth(), json={"join_code": code})
    for user in ("learner", "other"):
        api.post("/proctoring/sessions", headers=auth(user), json={"agent_name": "capstone_project_agent", "ref": f"{user}:1", "consent": True})
    rows = api.get(f"/organizations/{org_id}/proctoring", headers=auth("admin")).json()
    assert [row["user_id"] for row in rows] == ["learner"]
    assert rows[0]["agent_name"] == "capstone_project_agent"
    assert api.get(f"/organizations/{org_id}/proctoring", headers=auth("learner")).status_code in {403, 404}

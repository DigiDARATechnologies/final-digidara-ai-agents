"""The Conductor: what a learner means inside an agent's guided flow."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.a2a import routes as a2a_routes
from app.conductor import routes as conductor_routes
from app.conductor import service
from app.learner import service as learner_service
from app.models import User
from app.rate_limit import limiter

from test_phase2 import auth, send

OPTIONS = [
    {"value": "technical", "label": "Technical interview"},
    {"value": "hr", "label": "HR interview"},
]


@pytest.fixture
def api(database):
    with database() as session:
        session.add(User(id="learner", name="Learner", email="learner@example.test", email_verified=True, token_balance=1000))
        session.commit()
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(conductor_routes.router)
    app.include_router(a2a_routes.router)
    limiter.reset()
    with TestClient(app) as client:
        yield client


def decide(monkeypatch, decision, seen=None):
    def fake(system, user, temperature=0.3):
        if seen is not None:
            seen.append((system, json.loads(user)))
        return decision if isinstance(decision, str) else json.dumps(decision)
    monkeypatch.setattr(service, "call_text", fake)


def interpret(api, message, agent="mock_interview_agent", options=OPTIONS):
    return api.post("/conductor/interpret", headers=auth(), json={
        "agent_name": agent, "step": "choose_round", "options": options, "message": message,
    }).json()


def test_a_typed_choice_selects_the_offered_option(api, monkeypatch):
    seen = []
    decide(monkeypatch, {"intent": "select_option", "option_value": "HR"}, seen)
    learner_service.save_profile("learner", "Data Analyst", "", ["SQL"], "fresher")
    assert interpret(api, "the second one") == {"intent": "select_option", "option_value": "hr", "option_label": "HR interview"}
    system, data = seen[0]
    assert "- hr: HR interview" in system and "Mock Interview" in system
    assert data["learner"]["target_role"] == "Data Analyst" and data["message"] == "the second one"


def test_an_option_that_was_not_offered_falls_back_to_continue(api, monkeypatch):
    decide(monkeypatch, {"intent": "select_option", "option_value": "delete_everything"})
    assert interpret(api, "do it")["intent"] == "continue"


def test_switching_to_another_agent(api, monkeypatch):
    decide(monkeypatch, {"intent": "switch_agent", "agent_name": "codeforge_agent"})
    assert interpret(api, "actually I want to practise coding") == {
        "intent": "switch_agent", "agent_name": "codeforge_agent", "agent_label": "Coding Practice"}
    decide(monkeypatch, {"intent": "switch_agent", "agent_name": "mock_interview_agent"})
    assert interpret(api, "interview")["intent"] == "continue"
    decide(monkeypatch, {"intent": "switch_agent", "agent_name": "not_an_agent"})
    assert interpret(api, "x")["intent"] == "continue"


def test_restart_and_reply(api, monkeypatch):
    decide(monkeypatch, {"intent": "restart"})
    assert interpret(api, "change my role to data analyst") == {"intent": "restart"}
    decide(monkeypatch, {"intent": "reply", "reply": "  HR rounds ask about you and your teamwork.  Pick one below. "})
    assert interpret(api, "what is HR round?") == {"intent": "reply", "reply": "HR rounds ask about you and your teamwork. Pick one below."}


@pytest.mark.parametrize("raw", ["not json", "[1,2]", '{"intent": "launch_missiles"}'])
def test_anything_unexpected_continues(api, monkeypatch, raw):
    decide(monkeypatch, raw)
    assert interpret(api, "hello")["intent"] == "continue"


def test_a_provider_failure_continues(api, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("provider down")
    monkeypatch.setattr(service, "call_text", boom)
    assert interpret(api, "hello")["intent"] == "continue"


def test_unknown_agent_never_calls_the_model(api, monkeypatch):
    seen = []
    decide(monkeypatch, {"intent": "restart"}, seen)
    assert interpret(api, "hi", agent="general")["intent"] == "continue" and seen == []


def test_needs_a_login(api):
    assert api.post("/conductor/interpret", json={"agent_name": "mock_interview_agent", "message": "hi"}).status_code == 401


def test_conductor_is_an_a2a_agent(api, monkeypatch):
    decide(monkeypatch, {"intent": "restart"})
    card = api.get("/a2a/conductor/.well-known/agent-card.json").json()
    assert [s["id"] for s in card["skills"]] == ["interpret"]
    reply = api.post("/a2a/conductor", headers=auth(), json=send("interpret", {
        "agent_name": "mock_interview_agent", "step": "choose_round", "options": OPTIONS, "message": "start over"})).json()
    assert reply["result"]["artifacts"][0]["parts"][0]["data"] == {"intent": "restart"}

import pytest
from app.agent_state import service
from app.agent_state.routes import router as agent_state_router
from app.chat_history.routes import router as chat_history_router
from app.rate_limit import limiter
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.auth.security import create_access_token
from app.auth.service import create_user, delete_user, export_user_data
from app.chat_history import service as chat_history_service


@pytest.fixture
def client(database):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(agent_state_router)
    app.include_router(chat_history_router)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def users(database):
    a = create_user("User A", "a@example.com", None, "hash", "2026-01")
    b = create_user("User B", "b@example.com", None, "hash", "2026-01")
    return a.id, b.id


def auth(user_id):
    return {"authorization": "Bearer " + create_access_token(user_id)}


STATE = {"step": "awaiting_topic", "thread": "t-1", "scores": [1, 2, 3]}


def test_requires_login(client):
    assert client.get("/agent-state").status_code == 401
    assert client.put("/agent-state/capstone/c1", json={"state": STATE}).status_code == 401
    assert client.delete("/agent-state/capstone/c1").status_code == 401


def test_round_trip_one_row_per_chat(client, users):
    a, _ = users
    assert client.get("/agent-state", headers=auth(a)).json() == {"states": []}
    assert client.put("/agent-state/capstone/c1", headers=auth(a), json={"state": STATE}).status_code == 200
    assert client.put("/agent-state/capstone/c2", headers=auth(a), json={"state": {"step": "x"}}).status_code == 200
    states = client.get("/agent-state", headers=auth(a)).json()["states"]
    assert {(s["agentId"], s["chatId"]) for s in states} == {("capstone", "c1"), ("capstone", "c2")}
    assert next(s for s in states if s["chatId"] == "c1")["state"] == STATE


def test_saving_overwrites_only_that_chat(client, users):
    a, _ = users
    client.put("/agent-state/aptitude/c1", headers=auth(a), json={"state": {"n": 1}})
    client.put("/agent-state/aptitude/c2", headers=auth(a), json={"state": {"n": 2}})
    client.put("/agent-state/aptitude/c1", headers=auth(a), json={"state": {"n": 99}})
    by_chat = {s["chatId"]: s["state"] for s in client.get("/agent-state", headers=auth(a)).json()["states"]}
    assert by_chat == {"c1": {"n": 99}, "c2": {"n": 2}}


def test_users_are_isolated(client, users):
    a, b = users
    client.put("/agent-state/capstone/c1", headers=auth(a), json={"state": STATE})
    assert client.get("/agent-state", headers=auth(b)).json() == {"states": []}
    client.put("/agent-state/capstone/c1", headers=auth(b), json={"state": {"mine": True}})
    assert client.get("/agent-state", headers=auth(a)).json()["states"][0]["state"] == STATE
    client.delete("/agent-state/capstone/c1", headers=auth(b))
    assert len(client.get("/agent-state", headers=auth(a)).json()["states"]) == 1


def test_delete_removes_one_chat(client, users):
    a, _ = users
    client.put("/agent-state/capstone/c1", headers=auth(a), json={"state": STATE})
    client.put("/agent-state/capstone/c2", headers=auth(a), json={"state": STATE})
    assert client.delete("/agent-state/capstone/c1", headers=auth(a)).status_code == 204
    assert [s["chatId"] for s in client.get("/agent-state", headers=auth(a)).json()["states"]] == ["c2"]


def test_unknown_agent_oversize_and_bad_bodies_are_rejected(client, users):
    a, _ = users
    assert client.put("/agent-state/not_an_agent/c1", headers=auth(a), json={"state": STATE}).status_code == 422
    assert client.put("/agent-state/capstone/c1", headers=auth(a), json={"state": {"blob": "x" * (service.MAX_STATE_BYTES + 1)}}).status_code == 422
    assert client.put("/agent-state/capstone/c1", headers=auth(a), json={"state": "not an object"}).status_code == 422
    assert client.put("/agent-state/capstone/" + "c" * 129, headers=auth(a), json={"state": STATE}).status_code == 422


def test_per_agent_chat_limit(client, users, monkeypatch):
    a, _ = users
    monkeypatch.setattr(service, "MAX_CHATS_PER_AGENT", 2)
    assert client.put("/agent-state/capstone/c1", headers=auth(a), json={"state": STATE}).status_code == 200
    assert client.put("/agent-state/capstone/c2", headers=auth(a), json={"state": STATE}).status_code == 200
    assert client.put("/agent-state/capstone/c3", headers=auth(a), json={"state": STATE}).status_code == 422
    assert client.put("/agent-state/capstone/c1", headers=auth(a), json={"state": {"again": 1}}).status_code == 200  # updating is fine
    assert client.put("/agent-state/aptitude/c3", headers=auth(a), json={"state": STATE}).status_code == 200  # limit is per agent


def test_deleting_a_conversation_removes_its_state(client, users):
    a, _ = users
    chat = {"id": "c1", "agentId": "capstone", "title": "T", "messages": [], "updatedAt": 1_700_000_000_000}
    assert client.put("/chats/sync", headers=auth(a), json={"chats": [chat], "deleted_ids": []}).status_code == 200
    client.put("/agent-state/capstone/c1", headers=auth(a), json={"state": STATE})
    client.put("/agent-state/capstone/c2", headers=auth(a), json={"state": STATE})
    assert client.put("/chats/sync", headers=auth(a), json={"chats": [], "deleted_ids": ["c1"]}).status_code == 200
    assert [s["chatId"] for s in client.get("/agent-state", headers=auth(a)).json()["states"]] == ["c2"]


def test_export_includes_state_and_erasure_removes_it(client, users):
    a, b = users
    client.put("/agent-state/resume_builder/c1", headers=auth(a), json={"state": {"draft": "hello"}})
    client.put("/agent-state/resume_builder/c1", headers=auth(b), json={"state": {"draft": "other"}})
    exported = export_user_data(a)
    assert exported["agent_state"][0]["state"] == {"draft": "hello"}
    delete_user(a)
    assert service.get_all(a) == []
    assert len(service.get_all(b)) == 1  # someone else's state is untouched
    assert chat_history_service.get_history(a)[0] == []

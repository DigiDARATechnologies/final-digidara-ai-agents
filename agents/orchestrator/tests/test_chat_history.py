from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.auth.security import get_current_user_id
from app.auth.service import create_user
from app.chat_history.routes import router


def sample_chat(chat_id: str = "c_1") -> dict:
    return {
        "id": chat_id,
        "agentId": "general",
        "title": "Cross-device chat",
        "messages": [
            {
                "role": "agent",
                "text": "Hello",
                "time": "10:00 AM",
                "options": [{"label": "Continue", "value": "continue"}],
            }
        ],
        "updatedAt": 1_700_000_000_000,
        "pinned": True,
    }


@pytest.fixture
def history_client(database):
    user_a = create_user("User A", "a@example.com", None, "hash", "2026-01")
    user_b = create_user("User B", "b@example.com", None, "hash", "2026-01")
    current_user = {"id": user_a.id}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: current_user["id"]
    with TestClient(app) as client:
        yield client, current_user, user_a.id, user_b.id


def test_history_sync_round_trip_and_account_isolation(history_client):
    client, current_user, _user_a_id, user_b_id = history_client
    assert client.get("/chats").json() == {"chats": [], "initialized": False}

    chat = sample_chat()
    saved = client.put("/chats/sync", json={"chats": [chat], "deleted_ids": []})
    assert saved.status_code == 200
    assert saved.json() == {"chats": [chat], "initialized": True}

    current_user["id"] = user_b_id
    assert client.get("/chats").json() == {"chats": [], "initialized": False}


def test_clear_history_stays_initialized_and_stale_data_does_not_return(history_client):
    client, _current_user, _user_a_id, _user_b_id = history_client
    chat = sample_chat()
    assert client.put("/chats/sync", json={"chats": [chat], "deleted_ids": []}).status_code == 200
    assert client.put("/chats/sync", json={"chats": [], "deleted_ids": [chat["id"]]}).status_code == 200
    assert client.get("/chats").json() == {"chats": [], "initialized": True}

    stale = client.put("/chats/sync", json={"chats": [chat], "deleted_ids": []})
    assert stale.status_code == 200
    assert stale.json()["chats"] == []


def test_device_sync_merges_unseen_conversations_without_deleting_them(history_client):
    client, _current_user, _user_a_id, _user_b_id = history_client
    first_device_chat = sample_chat("c_device_a")
    second_device_chat = sample_chat("c_device_b")
    second_device_chat["updatedAt"] += 1

    assert client.put(
        "/chats/sync",
        json={"chats": [first_device_chat], "deleted_ids": []},
    ).status_code == 200
    synced = client.put(
        "/chats/sync",
        json={"chats": [second_device_chat], "deleted_ids": []},
    )

    assert synced.status_code == 200
    assert {chat["id"] for chat in synced.json()["chats"]} == {"c_device_a", "c_device_b"}


def test_a_duplicate_chat_keeps_its_newest_copy(history_client):
    client, _current_user, _user_a_id, _user_b_id = history_client
    older, newer = sample_chat(), sample_chat()
    newer["updatedAt"] += 5
    newer["title"] = "Newer title"
    saved = client.put("/chats/sync", json={"chats": [older, newer], "deleted_ids": []})
    assert saved.status_code == 200
    assert [c["title"] for c in saved.json()["chats"]] == ["Newer title"]


def test_one_malformed_message_does_not_block_the_whole_history(history_client):
    # A message without time, with a null or object text, or an unknown role
    # used to make every sync fail with 422; it is now repaired and kept.
    client, _current_user, _user_a_id, _user_b_id = history_client
    good = sample_chat("c_good")
    odd = sample_chat("c_odd")
    odd["messages"] = [{"role": "agent", "text": None, "options": [{"label": "Problem list", "value": "list"}]},
                       {"role": "system", "text": {"a": 1}, "time": "10:01 AM"},
                       {"role": "user", "text": "hi", "time": 5}, "not a message"]
    odd["title"] = "x" * 900
    saved = client.put("/chats/sync", json={"chats": [good, odd, {"id": ""}, "junk"], "deleted_ids": ["", None, "gone"]})
    assert saved.status_code == 200
    chats = {c["id"]: c for c in saved.json()["chats"]}
    assert set(chats) == {"c_good", "c_odd"}
    assert len(chats["c_odd"]["title"]) == 500
    assert [(m["role"], m["text"], m["time"]) for m in chats["c_odd"]["messages"]] == [
        ("agent", "", ""), ("agent", '{"a": 1}', "10:01 AM"), ("user", "hi", "")]
    assert chats["c_odd"]["messages"][0]["options"] == [{"label": "Problem list", "value": "list"}]


def test_more_than_five_hundred_chats_still_sync(history_client):
    client, _current_user, _user_a_id, _user_b_id = history_client
    chats = [sample_chat(f"c_{i}") for i in range(600)]
    saved = client.put("/chats/sync", json={"chats": chats, "deleted_ids": []})
    assert saved.status_code == 200
    assert len(saved.json()["chats"]) == 600


def test_history_endpoint_requires_authentication():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/chats").status_code == 401
        assert client.put("/chats/sync", json={"chats": [], "deleted_ids": []}).status_code == 401


def test_a_mysql_deadlock_during_sync_is_retried_transparently(history_client, monkeypatch):
    """The live failure: two overlapping syncs deadlocked MySQL (errno 1213) on the
    DELETE FROM conversation_messages step and the request crashed with a 500."""
    from unittest.mock import MagicMock

    from sqlalchemy.exc import OperationalError

    from app.chat_history import service

    client, _current_user, _user_a_id, _user_b_id = history_client
    real_get_session = service.get_session
    calls = {"n": 0}

    def flaky_get_session():
        session = real_get_session()
        calls["n"] += 1
        if calls["n"] == 1:

            def failing_commit():
                orig = MagicMock()
                orig.args = (1213, "Deadlock found when trying to get lock; try restarting transaction")
                raise OperationalError("DELETE FROM conversation_messages ...", {}, orig)

            session.commit = failing_commit
        return session

    monkeypatch.setattr(service, "get_session", flaky_get_session)
    response = client.put("/chats/sync", json={"chats": [sample_chat()], "deleted_ids": []})
    assert response.status_code == 200
    assert calls["n"] == 3                                  # 1 failed attempt + 1 retry that commits + get_history's own read
    assert [chat["id"] for chat in response.json()["chats"]] == ["c_1"]


def test_two_overlapping_syncs_creating_the_same_chat_do_not_500(history_client, monkeypatch):
    """Two tabs (or a save firing twice) both insert a brand-new chat; the slower
    one hits the duplicate key. It is retried and updates the row instead."""
    from sqlalchemy.exc import IntegrityError

    from app.chat_history import service

    client, _current_user, user_a_id, _user_b_id = history_client
    real_get_session = service.get_session
    calls = {"n": 0}

    def racing_get_session():
        session = real_get_session()
        calls["n"] += 1
        if calls["n"] == 1:

            def commit_after_the_other_sync():
                # The other request commits the same chat first.
                session.rollback()
                other = real_get_session()
                other.add(service.Conversation(id="c_1", user_id=user_a_id, agent_id="capstone-project", title="Other tab",
                                               pinned=False, updated_at_ms=1))
                other.commit()
                other.close()
                raise IntegrityError("INSERT INTO conversations ...", {}, Exception("Duplicate entry 'c_1'"))

            session.commit = commit_after_the_other_sync
        return session

    monkeypatch.setattr(service, "get_session", racing_get_session)
    response = client.put("/chats/sync", json={"chats": [sample_chat()], "deleted_ids": []})
    assert response.status_code == 200
    chats = response.json()["chats"]
    assert [chat["id"] for chat in chats] == ["c_1"] and chats[0]["title"] == sample_chat()["title"]


def test_a_non_deadlock_database_error_during_sync_is_not_retried(history_client, monkeypatch):
    from unittest.mock import MagicMock

    from sqlalchemy.exc import OperationalError

    from app.chat_history import service

    client, _current_user, _user_a_id, _user_b_id = history_client
    real_get_session = service.get_session

    def broken_get_session():
        session = real_get_session()

        def failing_commit():
            orig = MagicMock()
            orig.args = (1146, "Table 'orchestrator.conversations' doesn't exist")
            raise OperationalError("INSERT INTO conversations ...", {}, orig)

        session.commit = failing_commit
        return session

    monkeypatch.setattr(service, "get_session", broken_get_session)
    with pytest.raises(OperationalError):
        service.sync_history(_user_a_id, [sample_chat()], [])

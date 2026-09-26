"""The platform admin API: admin-only, and accurate about users, money, agents and chats."""
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin import routes as admin
from app.auth.security import create_access_token
from app.models import AgentChatState, AgentRegistry, Conversation, ConversationMessage, Payment, User

NOW = datetime.utcnow()


@pytest.fixture
def api(database, monkeypatch):
    monkeypatch.setattr(admin, "get_session", database)
    app = FastAPI()
    app.include_router(admin.router)
    with TestClient(app) as client:
        yield client


def bearer(user_id):
    return {"authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def seeded(database):
    with database() as s:
        s.add_all([
            User(id="boss", name="Boss", email="boss@x.io", is_admin=True, token_balance=10, created_at=NOW - timedelta(days=90)),
            User(id="asha", name="Asha Rao", email="asha@x.io", mobile="99999", token_balance=120_000, created_at=NOW - timedelta(days=3)),
            User(id="ravi", name="Ravi K", email="ravi@x.io", token_balance=0, google_id="g1", created_at=NOW - timedelta(days=40)),
        ])
        s.add_all([
            Payment(id="p1", user_id="asha", plan_id="basic", amount=49900, razorpay_order_id="o1", razorpay_payment_id="pay1", status="paid", created_at=NOW - timedelta(days=2), paid_at=NOW - timedelta(days=2)),
            Payment(id="p2", user_id="asha", plan_id="topup_100000", amount=10000, razorpay_order_id="o2", razorpay_payment_id="pay2", status="paid", created_at=NOW - timedelta(days=45), paid_at=NOW - timedelta(days=45)),
            Payment(id="p3", user_id="ravi", plan_id="standard", amount=99900, razorpay_order_id="o3", status="created", created_at=NOW - timedelta(days=1)),
        ])
        s.add_all([
            Conversation(id="c1", user_id="asha", agent_id="capstone-project", title="python", updated_at=NOW - timedelta(hours=1), updated_at_ms=1),
            Conversation(id="c2", user_id="asha", agent_id="leetcode", title="two sum", updated_at=NOW - timedelta(days=20), updated_at_ms=1),
            Conversation(id="c3", user_id="ravi", agent_id="capstone-project", title="gone", updated_at=NOW, updated_at_ms=1, deleted_at=NOW),
        ])
        s.flush()
        s.add_all([
            ConversationMessage(conversation_id="c1", user_id="asha", position=1, role="user", content="hello", display_time="10:00"),
            ConversationMessage(conversation_id="c1", user_id="asha", position=0, role="agent", content="hi there", display_time="09:59"),
            ConversationMessage(conversation_id="c2", user_id="asha", position=0, role="user", content="q", display_time="10:01"),
        ])
        s.add(AgentChatState(user_id="asha", agent_id="capstone", chat_id="c1", state={"step": "awaiting_submission"}))
        s.add_all([
            AgentRegistry(agent_name="capstone_project_agent", version="v1", endpoint="http://capstone:8000/api/invoke", description="Capstone",
                          input_schema={"properties": {"action": {"enum": ["health", "status"]}}}, output_schema={}, last_heartbeat=NOW),
            AgentRegistry(agent_name="old_agent", version="v1", endpoint="http://old/api", description="Old", input_schema={}, output_schema={},
                          last_heartbeat=NOW - timedelta(hours=3)),
        ])
        s.commit()


ENDPOINTS = ["/platform-admin/overview", "/platform-admin/users", "/platform-admin/users/asha", "/platform-admin/users/asha/conversations/c1",
             "/platform-admin/payments", "/platform-admin/agents"]


@pytest.mark.parametrize("url", ENDPOINTS)
def test_everything_needs_a_signed_in_administrator(api, seeded, url):
    assert api.get(url).status_code == 401
    assert api.get(url, headers=bearer("asha")).status_code == 403          # a normal user
    assert api.get(url, headers=bearer("nobody")).status_code == 403        # a token for a deleted account
    assert api.get(url, headers=bearer("boss")).status_code == 200


def test_overview_totals_money_users_tokens_and_agents(api, seeded):
    body = api.get("/platform-admin/overview", headers=bearer("boss")).json()
    assert body["users"] == {"total": 3, "new_7d": 1, "new_30d": 1, "admins": 1}
    revenue = body["revenue"]
    assert revenue["total"] == 599.0 and revenue["paid_count"] == 2 and revenue["paying_customers"] == 1
    assert revenue["last_30d"] == 499.0 and revenue["last_7d"] == 499.0          # the 45-day-old top-up is outside
    assert revenue["by_status"] == {"paid": 2, "created": 1}
    assert {e["label"]: e["amount"] for e in revenue["by_plan"]} == {"Basic plan": 499.0, "Token top-up (100,000 tokens)": 100.0}
    assert len(revenue["daily"]) == 30 and sum(d["amount"] for d in revenue["daily"]) == 499.0
    assert body["tokens"] == {"outstanding_balance": 120_010, "credited_by_payments": 600_000, "users_out_of_tokens": 1}
    assert body["activity"]["conversations"] == 2 and body["activity"]["messages"] == 3 and body["activity"]["active_users_7d"] == 1
    assert {a["agent_id"]: (a["chats"], a["messages"]) for a in body["activity"]["by_agent"]} == {"capstone-project": (1, 2), "leetcode": (1, 1)}
    assert body["agents"] == {"registered": 2, "healthy": 1}
    assert body["recent_payments"][0]["email"] == "ravi@x.io"


def test_users_search_sort_and_page(api, seeded):
    def get(**query):
        return api.get("/platform-admin/users", params=query, headers=bearer("boss")).json()

    everyone = get()
    assert everyone["total"] == 3 and [u["id"] for u in everyone["users"]] == ["asha", "ravi", "boss"]     # newest first
    asha = everyone["users"][0]
    assert asha["paid_total"] == 599.0 and asha["chats"] == 2 and asha["agents_used"] == 2 and asha["token_balance"] == 120_000
    assert [u["id"] for u in get(search="RAVI")["users"]] == ["ravi"]
    assert [u["id"] for u in get(search="99999")["users"]] == ["asha"]
    assert [u["id"] for u in get(sort="spent")["users"]][0] == "asha"
    assert [u["id"] for u in get(sort="balance")["users"]][0] == "ravi"
    page = get(limit=2, page=2)
    assert page["total"] == 3 and [u["id"] for u in page["users"]] == ["boss"]
    assert api.get("/platform-admin/users?limit=1000", headers=bearer("boss")).status_code == 422
    assert api.get("/platform-admin/users?sort=password", headers=bearer("boss")).status_code == 422


def test_user_detail_is_the_whole_story_of_one_user(api, seeded):
    body = api.get("/platform-admin/users/asha", headers=bearer("boss")).json()
    assert body["user"]["email"] == "asha@x.io" and "password" not in str(body).lower()
    assert body["totals"] == {"paid": 599.0, "payments": 2, "paid_payments": 2, "tokens_bought": 600_000, "conversations": 2, "messages": 3}
    assert body["payments"][0]["label"] == "Basic plan" and body["payments"][0]["tokens"] == 500_000
    assert [c["id"] for c in body["conversations"]] == ["c1", "c2"] and body["conversations"][0]["messages"] == 2
    progress = body["agent_progress"]
    assert [(p["agent_id"], p["chat_id"], p["step"]) for p in progress] == [("capstone", "c1", "awaiting_submission")]
    assert api.get("/platform-admin/users/nope", headers=bearer("boss")).status_code == 404


def test_a_conversation_is_read_in_order_and_the_access_is_logged(api, seeded, caplog):
    with caplog.at_level("INFO"):
        body = api.get("/platform-admin/users/asha/conversations/c1", headers=bearer("boss")).json()
    assert [m["content"] for m in body["messages"]] == ["hi there", "hello"] and body["agent_id"] == "capstone-project"
    assert "admin boss viewed conversation c1 of user asha" in caplog.text
    assert api.get("/platform-admin/users/ravi/conversations/c1", headers=bearer("boss")).status_code == 404     # not that user's


def test_payments_filter_search_and_summary(api, seeded):
    def get(**query):
        return api.get("/platform-admin/payments", params=query, headers=bearer("boss")).json()

    everything = get()
    assert everything["total"] == 3 and everything["payments"][0]["id"] == "p3"                                 # newest first
    assert everything["summary"] == {"paid": {"count": 2, "amount": 599.0}, "created": {"count": 1, "amount": 999.0}}
    assert [p["id"] for p in get(status="paid")["payments"]] == ["p1", "p2"]
    assert [p["id"] for p in get(search="ravi")["payments"]] == ["p3"]
    assert [p["id"] for p in get(search="pay2")["payments"]] == ["p2"]
    assert get(status="paid")["payments"][0]["email"] == "asha@x.io"


def test_agents_show_health_actions_and_usage(api, seeded):
    body = api.get("/platform-admin/agents", headers=bearer("boss")).json()
    by_name = {a["agent_name"]: a for a in body["agents"]}
    assert by_name["capstone_project_agent"]["online"] is True and by_name["capstone_project_agent"]["actions"] == ["health", "status"]
    assert by_name["old_agent"]["online"] is False and by_name["old_agent"]["heartbeat_age_seconds"] >= 3 * 3600 - 5
    assert {u["agent_id"] for u in body["chat_usage"]} == {"capstone-project", "leetcode"}

"""OpenAI credit against the tokens users hold: the figures, the email to
support, the signup check and the admin endpoints."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin import routes as admin
from app.auth.security import create_access_token
from app.billing import openai_pool
from app.models import OpenAICreditEntry, TokenUsageEvent, User

NOW = datetime.utcnow().replace(microsecond=0)
ONE_DOLLAR = openai_pool.tokens_for_usd(1.0)   # 3,809,523 at the default gpt-4o-mini price


@pytest.fixture
def sent(monkeypatch):
    mails = []
    monkeypatch.setattr("app.monitoring.service._send_email", lambda to, subject, body: mails.append((to, subject, body)) or True)
    return mails


@pytest.fixture
def users(database):
    with database() as s:
        s.add_all([
            User(id="boss", name="Boss", email="boss@x.io", is_admin=True, token_balance=0, created_at=NOW - timedelta(days=90)),
            User(id="old", name="Old Learner", email="old@x.io", token_balance=2_000_000, created_at=NOW - timedelta(days=30)),
            User(id="new", name="New Learner", email="new@x.io", token_balance=2_000_000, created_at=NOW - timedelta(days=1)),
            User(id="over", name="Overdrawn", email="over@x.io", token_balance=-500, created_at=NOW - timedelta(days=2)),
        ])
        s.commit()
    return database


def add_balance(database, usd, at=None):
    with database() as s:
        s.add(OpenAICreditEntry(balance_usd=usd, created_at=at or NOW - timedelta(hours=1)))
        s.commit()


def test_not_set_until_an_admin_enters_the_balance(users, sent):
    figures = openai_pool.check_and_alert()
    assert figures["status"] == openai_pool.NOT_SET
    assert figures["allocated_tokens"] == 4_000_000   # the overdrawn account owes nothing more
    assert figures["available_tokens"] is None
    assert sent == []


def test_enough_credit_covers_every_user(users, sent):
    add_balance(users, 2.0)
    figures = openai_pool.check_and_alert()
    assert figures["status"] == openai_pool.ENOUGH
    assert figures["available_tokens"] == openai_pool.tokens_for_usd(2.0)
    assert figures["spare_tokens"] == figures["available_tokens"] - 4_000_000
    assert figures["new_users_room"] == figures["spare_tokens"] // openai_pool.free_signup_tokens()
    assert sent == []


def test_estimated_spend_since_the_entry_is_taken_off(users, sent):
    add_balance(users, 2.0, at=NOW - timedelta(hours=2))
    with users() as s:
        s.add(TokenUsageEvent(user_id="old", tokens=3_000_000, created_at=NOW - timedelta(hours=3)))   # before: already in the balance
        s.add(TokenUsageEvent(user_id="old", tokens=ONE_DOLLAR, created_at=NOW - timedelta(hours=1)))
        s.commit()
    figures = openai_pool.check_and_alert()
    assert figures["spend_source"] == "estimate"
    assert figures["spent_usd"] == pytest.approx(1.0, abs=0.001)
    assert figures["status"] == openai_pool.SHORT


def test_short_emails_support_once_then_reminds(users, sent):
    add_balance(users, 0.5)
    figures = openai_pool.check_and_alert(now=NOW)
    assert figures["status"] == openai_pool.SHORT and figures["emailed"]
    assert figures["shortfall_tokens"] == 4_000_000 - openai_pool.tokens_for_usd(0.5)
    to, subject, body = sent[0]
    assert to == ["support@digidaratechnologies.com"]
    assert "not enough" in subject and "Short by" in body

    assert not openai_pool.check_and_alert(now=NOW + timedelta(hours=1))["emailed"]
    assert openai_pool.check_and_alert(now=NOW + timedelta(hours=13))["emailed"]
    assert len(sent) == 2


def test_new_users_while_short_are_counted_and_reset_after_a_top_up(users, sent):
    add_balance(users, 0.5)
    openai_pool.check_and_alert(now=NOW)
    openai_pool.check_and_alert(new_user=True, now=NOW + timedelta(minutes=5))
    openai_pool.check_and_alert(new_user=True, now=NOW + timedelta(hours=13))
    assert "New users who joined while short: 2" in sent[-1][2]

    add_balance(users, 10.0, at=NOW)
    assert openai_pool.check_and_alert(now=NOW + timedelta(hours=14))["status"] == openai_pool.ENOUGH
    with users() as s:
        assert openai_pool.alert_state(s)["new_users_while_short"] == 0
    # Falling short again is news: emailed straight away.
    add_balance(users, 0.1, at=NOW + timedelta(minutes=1))
    assert openai_pool.check_and_alert(now=NOW + timedelta(hours=14, minutes=10))["emailed"]


def test_exact_costs_come_from_openai_when_an_admin_key_is_set(users, sent, monkeypatch):
    add_balance(users, 5.0)
    seen = []

    def answer(request):
        seen.append(request)
        if "page" not in request.url.params:
            return httpx.Response(200, json={"data": [{"results": [{"amount": {"value": 1.25, "currency": "usd"}}]}],
                                             "has_more": True, "next_page": "p2"})
        return httpx.Response(200, json={"data": [{"results": [{"amount": {"value": 0.75}}]}], "has_more": False})

    real_client = httpx.Client
    monkeypatch.setattr(openai_pool.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(answer), **kw))
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "sk-admin-test")
    openai_pool._costs_cache.clear()
    figures = openai_pool.check_and_alert()
    assert figures["spend_source"] == "openai" and figures["exact_costs"]
    assert figures["spent_usd"] == pytest.approx(2.0)
    assert seen[0].headers["authorization"] == "Bearer sk-admin-test"
    entered = NOW - timedelta(hours=1)
    day_start = datetime(entered.year, entered.month, entered.day, tzinfo=timezone.utc)
    assert seen[0].url.params["start_time"] == str(int(day_start.timestamp()))


def test_openai_failure_falls_back_to_the_estimate(users, sent, monkeypatch):
    add_balance(users, 5.0)
    real_client = httpx.Client
    monkeypatch.setattr(openai_pool.httpx, "Client",
                        lambda **kw: real_client(transport=httpx.MockTransport(lambda r: httpx.Response(401)), **kw))
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "sk-admin-wrong")
    openai_pool._costs_cache.clear()
    assert openai_pool.check_and_alert()["spend_source"] == "estimate"


def test_a_new_account_starts_the_check(database, monkeypatch):
    calls = []
    monkeypatch.setattr(openai_pool, "check_in_background", lambda **kw: calls.append(kw))
    monkeypatch.setenv("OPENAI_POOL_CHECK_ON_SIGNUP", "1")
    with database() as s:
        s.add(User(id="u1", name="U", email="u@x.io"))
        s.commit()
        s.get(User, "u1").name = "Renamed"   # an update is not a new user
        s.commit()
    assert calls == [{"new_user": True}]
    monkeypatch.setenv("OPENAI_POOL_CHECK_ON_SIGNUP", "0")
    with database() as s:
        s.add(User(id="u2", name="U2", email="u2@x.io"))
        s.commit()
    assert len(calls) == 1


# --- admin endpoints ------------------------------------------------------

@pytest.fixture
def api(users, monkeypatch):
    monkeypatch.setattr(admin, "get_session", users)
    app = FastAPI()
    app.include_router(admin.router)
    with TestClient(app) as client:
        yield client


def bearer(user_id):
    return {"authorization": "Bearer " + create_access_token(user_id)}


def test_only_admins_see_openai_tokens(api):
    assert api.get("/platform-admin/openai-tokens", headers=bearer("old")).status_code == 403
    assert api.post("/platform-admin/openai-tokens/balance", json={"balance_usd": 9}, headers=bearer("old")).status_code == 403
    assert api.get("/platform-admin/openai-tokens/users", headers=bearer("old")).status_code == 403


def test_admin_enters_a_balance_and_support_hears_when_short(api, sent):
    body = api.get("/platform-admin/openai-tokens", headers=bearer("boss")).json()
    assert body["status"] == "not_set" and body["entries"] == []

    body = api.post("/platform-admin/openai-tokens/balance", json={"balance_usd": 0.75, "note": " topped  up "}, headers=bearer("boss")).json()
    assert body["status"] == "short" and body["emailed"]
    assert body["entries"][0]["balance_usd"] == 0.75 and body["entries"][0]["note"] == "topped up"
    assert body["last_alert_at"] and len(sent) == 1

    assert api.post("/platform-admin/openai-tokens/balance", json={"balance_usd": -1}, headers=bearer("boss")).status_code == 422


def test_existing_users_are_covered_before_new_ones(api, users):
    add_balance(users, 0.75)   # ~2.86M tokens: the older 2M fits, the newer 2M does not
    rows = {r["id"]: r for r in api.get("/platform-admin/openai-tokens/users", headers=bearer("boss")).json()["users"]}
    assert rows["old"]["covered"] is True and rows["new"]["covered"] is False
    assert rows["over"]["covered"] is True and rows["boss"]["covered"] is True   # nothing held, nothing to cover
    short = api.get("/platform-admin/openai-tokens/users", params={"only_short": True}, headers=bearer("boss")).json()
    assert [r["id"] for r in short["users"]] == ["new"]
    found = api.get("/platform-admin/openai-tokens/users", params={"search": "OLD L"}, headers=bearer("boss")).json()
    assert [r["id"] for r in found["users"]] == ["old"]

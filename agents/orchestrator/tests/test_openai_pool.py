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


# --- live figures from the OpenAI platform -------------------------------

_REAL_CLIENT = httpx.Client


def _mock_openai(monkeypatch, answer):
    real_client = _REAL_CLIENT
    monkeypatch.setattr(openai_pool.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(answer), **kw))
    openai_pool._live_cache.clear()


def test_live_needs_an_admin_key(database, monkeypatch):
    monkeypatch.delenv("OPENAI_ADMIN_KEY", raising=False)
    assert openai_pool.live_from_openai() == {"connected": False, "error": "no_key"}


def test_live_pulls_spend_and_tokens_from_openai(database, monkeypatch):
    now = datetime(2026, 11, 28, 9, 0)
    today = int(datetime(2026, 11, 28, tzinfo=timezone.utc).timestamp())
    last_month = int(datetime(2026, 10, 31, tzinfo=timezone.utc).timestamp())
    seen = []

    def answer(request):
        seen.append(request)
        if request.url.path.endswith("/costs"):
            return httpx.Response(200, json={"data": [
                {"start_time": last_month, "results": [{"amount": {"value": 2.0}, "line_item": "gpt-4o-mini, input"}]},
                {"start_time": today, "results": [{"amount": {"value": 1.5}, "line_item": "gpt-4o-mini, input"},
                                                  {"amount": {"value": 0.5}, "line_item": "tts"}]},
            ], "has_more": False})
        return httpx.Response(200, json={"data": [
            {"start_time": today, "results": [
                {"model": "gpt-4o-mini", "input_tokens": 1000, "output_tokens": 200, "num_model_requests": 3},
                {"model": "gpt-4.1-mini", "input_tokens": 50, "output_tokens": 5, "num_model_requests": 1},
            ]},
        ], "has_more": False})

    _mock_openai(monkeypatch, answer)
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "sk-admin-test")
    live = openai_pool.live_from_openai(now)
    assert live["connected"] and live["error"] is None
    assert live["today_usd"] == pytest.approx(2.0)
    assert live["month_usd"] == pytest.approx(2.0)      # October's $2 is not this month
    assert live["period_usd"] == pytest.approx(4.0)
    assert live["period_tokens"] == 1255 and live["period_requests"] == 4
    assert live["by_model"][0] == {"model": "gpt-4o-mini", "input_tokens": 1000, "output_tokens": 200, "requests": 3}
    assert live["by_line_item"][0] == {"line_item": "gpt-4o-mini, input", "usd": 3.5}
    assert live["daily"][0]["date"] == "2026-11-28" and len(live["daily"]) == openai_pool.LIVE_DAYS
    assert all(r.headers["authorization"] == "Bearer sk-admin-test" for r in seen)

    calls = len(seen)
    openai_pool.live_from_openai(now)                    # cached
    assert len(seen) == calls
    openai_pool.live_from_openai(now, refresh=True)
    assert len(seen) == calls * 2


def test_live_says_when_openai_rejects_the_key(database, monkeypatch):
    _mock_openai(monkeypatch, lambda r: httpx.Response(401))
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "sk-admin-wrong")
    assert openai_pool.live_from_openai() == {"connected": False, "error": "rejected"}
    _mock_openai(monkeypatch, lambda r: httpx.Response(500))
    assert openai_pool.live_from_openai() == {"connected": False, "error": "unavailable"}


def test_only_admins_see_live_figures(api, monkeypatch):
    monkeypatch.delenv("OPENAI_ADMIN_KEY", raising=False)
    assert api.get("/platform-admin/openai-tokens/live", headers=bearer("old")).status_code == 403
    assert api.get("/platform-admin/openai-tokens/live", headers=bearer("boss")).json()["error"] == "no_key"


# --- the admin key entered on the admin page ------------------------------

KEY = "sk-admin-" + "x" * 40 + "abcd"


def test_admin_saves_the_key_on_the_page_encrypted_and_never_shown(api, users, monkeypatch):
    from app.models import AppSecret

    monkeypatch.delenv("OPENAI_ADMIN_KEY", raising=False)
    seen = []
    _mock_openai(monkeypatch, lambda r: seen.append(r) or httpx.Response(200, json={"data": [], "has_more": False}))
    assert api.get("/platform-admin/openai-tokens/admin-key", headers=bearer("boss")).json()["set"] is False
    assert api.put("/platform-admin/openai-tokens/admin-key", json={"key": KEY}, headers=bearer("old")).status_code == 403

    body = api.put("/platform-admin/openai-tokens/admin-key", json={"key": f"  {KEY} "}, headers=bearer("boss")).json()
    assert body == {**body, "set": True, "source": "page", "hint": "sk-admin-…abcd", "updated_by": "boss"}
    assert KEY not in str(body)
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"   # checked with OpenAI before saving
    with users() as s:
        stored = s.get(AppSecret, openai_pool.ADMIN_KEY_SECRET).value
    assert KEY not in stored                                      # encrypted at rest
    assert openai_pool._admin_key() == KEY
    assert api.get("/platform-admin/openai-tokens", headers=bearer("boss")).json()["exact_costs"] is True

    # The page's key wins over the .env one; removing it falls back to .env.
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "sk-admin-from-env-9999")
    assert openai_pool._admin_key() == KEY
    body = api.delete("/platform-admin/openai-tokens/admin-key", headers=bearer("boss")).json()
    assert body["source"] == "env" and body["hint"] == "sk-admin-…9999"
    assert openai_pool._admin_key() == "sk-admin-from-env-9999"


def test_a_wrong_key_is_not_saved(api, monkeypatch):
    monkeypatch.delenv("OPENAI_ADMIN_KEY", raising=False)
    normal = "sk-proj-" + "y" * 40
    response = api.put("/platform-admin/openai-tokens/admin-key", json={"key": normal}, headers=bearer("boss"))
    assert response.status_code == 400 and "sk-admin-" in response.json()["detail"]

    _mock_openai(monkeypatch, lambda r: httpx.Response(401))
    response = api.put("/platform-admin/openai-tokens/admin-key", json={"key": KEY}, headers=bearer("boss"))
    assert response.status_code == 400 and "refused" in response.json()["detail"]
    _mock_openai(monkeypatch, lambda r: httpx.Response(503))
    assert api.put("/platform-admin/openai-tokens/admin-key", json={"key": KEY}, headers=bearer("boss")).status_code == 502
    assert api.get("/platform-admin/openai-tokens/admin-key", headers=bearer("boss")).json()["set"] is False


def test_a_key_saved_under_another_jwt_secret_counts_as_not_set(database, monkeypatch):
    from app import secret_store
    from app.auth import security

    secret_store.put(openai_pool.ADMIN_KEY_SECRET, KEY)
    monkeypatch.setattr(security, "JWT_SECRET", "a-different-secret-with-at-least-32-characters")
    monkeypatch.delenv("OPENAI_ADMIN_KEY", raising=False)
    assert secret_store.get(openai_pool.ADMIN_KEY_SECRET) is None
    assert openai_pool.admin_key_status()["set"] is False

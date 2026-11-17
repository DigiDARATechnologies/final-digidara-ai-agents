"""Settings: preferences, profile, sign-ins (sign out one device or every
other), two-step verification, usage over a date range and the reminder emails."""
import re
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.account import reminders
from app.account import routes as account_routes
from app.auth import email_verification
from app.auth import routes as auth_routes
from app.auth import service as auth_service
from app.auth.security import create_access_token, decode_access_token
from app.models import (Assessment, Organization, OrganizationMember, Payment, TokenUsageEvent, User,
                        UserPreference, UserSignIn)
from app.rate_limit import limiter

SENT: list = []


class FakeSMTP:
    def __init__(self, host, port, timeout=None, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        SENT.append(message)


@pytest.fixture
def smtp(monkeypatch):
    SENT.clear()
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "false")
    monkeypatch.setattr(email_verification.smtplib, "SMTP", FakeSMTP)
    return SENT


@pytest.fixture
def api(database):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_routes.router)
    app.include_router(account_routes.router)
    limiter.reset()
    with TestClient(app) as client:
        yield client


def bearer(token):
    return {"authorization": "Bearer " + token}


def signup(api, email="asha@example.com", password="asha-pass-123", agent="Mozilla/5.0 (Windows NT 10.0) Chrome/130.0"):
    response = api.post("/auth/signup", json={"name": "Asha Rao", "email": email, "mobile": "+919999999999",
                                              "password": password, "consent": True}, headers={"user-agent": agent})
    assert response.status_code == 201
    return response.json()


def login(api, email="asha@example.com", password="asha-pass-123", agent="Mozilla/5.0 (Linux; Android 14) Chrome/130.0"):
    return api.post("/auth/login", json={"email": email, "password": password}, headers={"user-agent": agent})


def last_code():
    text = SENT[-1].get_body(preferencelist=("plain",)).get_content()
    return re.search(r"\b(\d{6})\b", text).group(1)


# --- preferences ---------------------------------------------------------------

def test_preferences_start_at_defaults_and_keep_only_valid_values(api):
    token = signup(api)["access_token"]
    prefs = api.get("/account/preferences", headers=bearer(token)).json()
    assert prefs["notifications"]["in_app"] is True and prefs["notifications"]["weekly_progress"] is False
    assert prefs["usage"]["warn_percent"] == 80 and prefs["pinned_agents"] == []

    saved = api.put("/account/preferences", headers=bearer(token), json={
        "notifications": {"weekly_progress": True, "email": "yes"},
        "general": {"default_agent": "mock-interview", "time_zone": "Asia/Kolkata", "date_format": "ymd"},
        "usage": {"warn_percent": 33},
        "billing": {"billing_email": "Accounts@Example.com"},
        "pinned_agents": ["codeforge", "codeforge", "Bad Id!"],
        "unknown": 1,
    }).json()
    assert saved["notifications"]["weekly_progress"] is True and saved["notifications"]["email"] is True
    assert saved["general"] == {"default_agent": "mock-interview", "time_zone": "Asia/Kolkata", "date_format": "ymd"}
    assert saved["usage"]["warn_percent"] == 80
    assert saved["billing"]["billing_email"] == "accounts@example.com"
    assert saved["pinned_agents"] == ["codeforge"] and "unknown" not in saved

    # A later partial save keeps the rest.
    again = api.put("/account/preferences", headers=bearer(token), json={"usage": {"warn_percent": 90}}).json()
    assert again["usage"]["warn_percent"] == 90 and again["general"]["date_format"] == "ymd"


def test_profile_name_and_mobile_are_saved_on_the_account(api):
    token = signup(api)["access_token"]
    response = api.put("/account/profile", headers=bearer(token), json={"name": "  Asha   R  ", "mobile": "+91 98765-43210"})
    assert response.status_code == 200 and response.json() == {"name": "Asha R", "mobile": "+919876543210"}
    me = api.get("/auth/me", headers=bearer(token)).json()
    assert me["name"] == "Asha R" and me["mobile"] == "+919876543210"
    assert api.put("/account/profile", headers=bearer(token), json={"name": "Asha", "mobile": "12"}).status_code == 422
    assert api.put("/account/profile", headers=bearer(token), json={"name": "Asha", "mobile": ""}).json()["mobile"] is None


# --- sign-ins --------------------------------------------------------------------

def test_every_sign_in_is_listed_and_one_device_can_be_signed_out(api):
    laptop = signup(api)["access_token"]
    phone = login(api).json()["access_token"]
    rows = api.get("/account/sign-ins", headers=bearer(laptop)).json()["sign_ins"]
    assert [row["method"] for row in rows] == ["password", "signup"]
    assert rows[0]["device"] == "Chrome on Android" and rows[1]["device"] == "Chrome on Windows"
    assert rows[1]["current"] and all(row["active"] for row in rows)

    assert api.delete(f"/account/sign-ins/{rows[0]['id']}", headers=bearer(laptop)).status_code == 200
    assert api.get("/auth/me", headers=bearer(phone)).status_code == 401
    assert api.get("/auth/me", headers=bearer(laptop)).status_code == 200
    rows = api.get("/account/sign-ins", headers=bearer(laptop)).json()["sign_ins"]
    assert rows[0]["active"] is False and rows[0]["revoked_at"]


def test_another_account_cannot_sign_out_my_device(api):
    mine = signup(api)["access_token"]
    theirs = signup(api, email="ravi@example.com")["access_token"]
    my_row = api.get("/account/sign-ins", headers=bearer(mine)).json()["sign_ins"][0]
    assert api.delete(f"/account/sign-ins/{my_row['id']}", headers=bearer(theirs)).status_code == 404
    assert api.get("/auth/me", headers=bearer(mine)).status_code == 200


def test_sign_out_everywhere_else_keeps_this_device(api):
    laptop = signup(api)["access_token"]
    phone = login(api).json()["access_token"]
    response = api.post("/account/sign-ins/sign-out-others", headers=bearer(laptop))
    fresh = response.json()["access_token"]
    assert api.get("/auth/me", headers=bearer(phone)).status_code == 401
    assert api.get("/auth/me", headers=bearer(laptop)).status_code == 401
    assert api.get("/auth/me", headers=bearer(fresh)).status_code == 200
    rows = api.get("/account/sign-ins", headers=bearer(fresh)).json()["sign_ins"]
    assert [(row["method"], row["active"], row["current"]) for row in rows] == [("password", False, False), ("signup", True, True)]


def test_password_change_keeps_this_device_in_the_list(api):
    token = signup(api)["access_token"]
    login(api)
    fresh = api.put("/auth/password", headers=bearer(token),
                    json={"current_password": "asha-pass-123", "new_password": "new-pass-4567"}).json()["access_token"]
    rows = api.get("/account/sign-ins", headers=bearer(fresh)).json()["sign_ins"]
    assert [(row["method"], row["active"]) for row in rows] == [("password", False), ("signup", True)]


def test_tokens_from_before_sign_ins_still_work(api, database):
    signup(api)
    user = auth_service.get_by_email("asha@example.com")
    assert decode_access_token(create_access_token(user.id, 0)) == user.id


def test_other_signed_tokens_are_never_a_session(api):
    import jwt as pyjwt
    from app.auth.security import JWT_SECRET

    user_id = signup(api)["user"]["id"]
    for extra in ({"purpose": "two_step_login"}, {"typ": "certificate_link"}):
        token = pyjwt.encode({"sub": user_id, "exp": 9999999999, **extra}, JWT_SECRET, algorithm="HS256")
        assert api.get("/auth/me", headers=bearer(token)).status_code == 401


# --- two-step verification ---------------------------------------------------------

def turn_on_two_step(api, token):
    assert api.post("/account/two-step/start", headers=bearer(token), json={"password": "asha-pass-123"}).status_code == 200
    assert api.post("/account/two-step/enable", headers=bearer(token), json={"code": last_code()}).json() == {"enabled": True}


def test_two_step_needs_the_password_and_a_code_to_turn_on(api, smtp):
    token = signup(api)["access_token"]
    assert api.get("/account/two-step", headers=bearer(token)).json()["enabled"] is False
    assert api.post("/account/two-step/start", headers=bearer(token), json={"password": "wrong"}).status_code == 401
    assert api.post("/account/two-step/start", headers=bearer(token), json={"password": "asha-pass-123"}).status_code == 200
    assert api.post("/account/two-step/enable", headers=bearer(token), json={"code": "000000" if last_code() != "000000" else "111111"}).status_code == 400
    assert api.get("/account/two-step", headers=bearer(token)).json()["enabled"] is False
    assert api.post("/account/two-step/enable", headers=bearer(token), json={"code": last_code()}).status_code == 200
    assert api.get("/account/two-step", headers=bearer(token)).json()["enabled"] is True


def test_with_two_step_on_login_needs_the_emailed_code(api, smtp):
    token = signup(api)["access_token"]
    turn_on_two_step(api, token)
    first = login(api)
    body = first.json()
    assert first.status_code == 200 and body["two_step_required"] is True and "access_token" not in body
    assert body["email"] == "as**@example.com"
    # The challenge itself is not a session.
    assert api.get("/auth/me", headers=bearer(body["challenge"])).status_code == 401
    assert api.post("/auth/login/two-step", json={"challenge": body["challenge"], "code": "12"}).status_code == 400
    done = api.post("/auth/login/two-step", json={"challenge": body["challenge"], "code": last_code()})
    assert done.status_code == 200
    assert api.get("/auth/me", headers=bearer(done.json()["access_token"])).status_code == 200
    # A code works once.
    assert api.post("/auth/login/two-step", json={"challenge": body["challenge"], "code": last_code()}).status_code == 400
    methods = [row["method"] for row in api.get("/account/sign-ins", headers=bearer(token)).json()["sign_ins"]]
    assert methods[0] == "two_step"


def test_two_step_locks_after_five_wrong_codes(api, smtp):
    token = signup(api)["access_token"]
    turn_on_two_step(api, token)
    challenge = login(api).json()["challenge"]
    right = last_code()
    wrong = "000000" if right != "000000" else "111111"
    for _ in range(5):
        api.post("/auth/login/two-step", json={"challenge": challenge, "code": wrong})
    assert api.post("/auth/login/two-step", json={"challenge": challenge, "code": right}).status_code == 429


def test_turning_two_step_off_needs_the_password(api, smtp):
    token = signup(api)["access_token"]
    turn_on_two_step(api, token)
    assert api.post("/account/two-step/disable", headers=bearer(token), json={"password": "nope"}).status_code == 401
    assert api.post("/account/two-step/disable", headers=bearer(token), json={"password": "asha-pass-123"}).status_code == 200
    assert "access_token" in login(api).json()


# --- usage over a date range -------------------------------------------------------

def test_usage_between_two_days_by_agent_and_day(api, database):
    body = signup(api)
    token, user_id = body["access_token"], body["user"]["id"]
    session = database()
    try:
        for when, agent, tokens in ((datetime(2026, 11, 1, 10), "codeforge", 3000), (datetime(2026, 11, 2, 10), "codeforge", 6000),
                                    (datetime(2026, 11, 2, 11), "aptitude", 3000), (datetime(2026, 10, 30, 10), "aptitude", 9000)):
            session.add(TokenUsageEvent(user_id=user_id, agent_name=agent, action="run", tokens=tokens, created_at=when))
        session.commit()
    finally:
        session.close()
    data = api.get("/account/usage", headers=bearer(token), params={"start": "2026-11-01", "end": "2026-11-02"}).json()
    assert data["requests"] == 3 and data["tokens_used"] == 12000
    assert [row["agent_name"] for row in data["agents"]] == ["codeforge", "aptitude"]
    assert [(row["day"], row["requests"]) for row in data["days"]] == [("2026-11-01", 1), ("2026-11-02", 2)]
    assert len(data["events"]) == 3
    bad = api.get("/account/usage", headers=bearer(token), params={"start": "2026-11-02", "end": "2026-11-01"})
    assert bad.status_code == 422


# --- data download and erasure -------------------------------------------------------

def test_settings_are_in_the_data_download_and_erased_with_the_account(api, database, monkeypatch):
    from app import agent_data, job_data

    monkeypatch.setattr(agent_data, "delete_user_data", lambda *a: None)
    monkeypatch.setattr(job_data, "delete_user_data", lambda *a: None)
    body = signup(api)
    token, user_id = body["access_token"], body["user"]["id"]
    api.put("/account/preferences", headers=bearer(token), json={"pinned_agents": ["codeforge"]})
    exported = auth_service.export_user_data(user_id)["settings"]
    assert exported["preferences"]["pinned_agents"] == ["codeforge"] and len(exported["sign_ins"]) == 1
    assert api.request("DELETE", "/auth/me", headers=bearer(token), json={"password": "asha-pass-123"}).status_code == 204
    session = database()
    try:
        assert session.query(UserSignIn).filter_by(user_id=user_id).count() == 0
        assert session.get(UserPreference, user_id) is None
    finally:
        session.close()


# --- reminder emails ---------------------------------------------------------------

def _user(database, **fields):
    session = database()
    try:
        user = User(name="Meena K", email=fields.pop("email", "meena@example.com"), email_verified=True, **fields)
        session.add(user)
        session.commit()
        return user.id
    finally:
        session.close()


def _subjects():
    return [message["Subject"] for message in SENT]


def test_low_coin_email_once_a_month_for_active_learners(database, smtp):
    user_id = _user(database, token_balance=3000, tokens_per_point=3000)
    session = database()
    session.add(TokenUsageEvent(user_id=user_id, agent_name="codeforge", tokens=100, created_at=datetime.utcnow()))
    session.commit()
    session.close()
    reminders.send_due()
    reminders.send_due()
    assert _subjects() == ["You're running low on SkillDARA coins"]


def test_turning_a_reminder_off_stops_it(database, smtp):
    user_id = _user(database, token_balance=0, tokens_per_point=3000)
    session = database()
    session.add(TokenUsageEvent(user_id=user_id, agent_name="codeforge", tokens=100, created_at=datetime.utcnow()))
    session.add(UserPreference(user_id=user_id, prefs={"notifications": {"email": False}}, sent={}))
    session.commit()
    session.close()
    reminders.send_due()
    assert SENT == []


def test_weekly_progress_goes_out_on_monday_morning_once(database, smtp):
    user_id = _user(database)
    session = database()
    session.add(UserPreference(user_id=user_id, prefs={"notifications": {"weekly_progress": True}}, sent={}))
    monday = datetime(2026, 11, 16, 4, 0)  # 9:30 India time
    session.add(TokenUsageEvent(user_id=user_id, agent_name="mock_interview", tokens=3000, created_at=monday - timedelta(days=2)))
    session.commit()
    session.close()
    reminders.send_due(monday - timedelta(hours=1))  # 8:30 India time: too early
    assert SENT == []
    reminders.send_due(monday)
    reminders.send_due(monday + timedelta(hours=1))
    assert _subjects() == ["Your SkillDARA week"]
    assert "Mock Interview: 1 request" in SENT[0].get_content()


def test_renewal_reminder_goes_to_the_billing_email(database, smtp):
    user_id = _user(database)
    now = datetime.utcnow()
    session = database()
    session.add(Payment(user_id=user_id, plan_id="pro_monthly", amount=49900, currency="INR", status="paid",
                        razorpay_order_id="order_1", paid_at=now - timedelta(days=28), created_at=now - timedelta(days=28)))
    session.add(UserPreference(user_id=user_id, prefs={"billing": {"billing_email": "accounts@example.com"}}, sent={}))
    session.commit()
    session.close()
    reminders.send_due(now)
    reminders.send_due(now)
    assert len(SENT) == 1 and SENT[0]["To"] == "accounts@example.com" and "plan ends on" in SENT[0]["Subject"]


def test_assessment_reminder_for_members_who_have_not_started(database, smtp):
    member_id = _user(database)
    owner_id = _user(database, email="owner@example.com")
    now = datetime.utcnow()
    session = database()
    org = Organization(name="Test College", join_code="TESTCOLLEGE1")
    session.add(org)
    session.flush()
    session.add(OrganizationMember(organization_id=org.id, user_id=member_id, role="member"))
    session.add(OrganizationMember(organization_id=org.id, user_id=owner_id, role="owner"))
    session.add(Assessment(organization_id=org.id, title="Python round", token="tok-python-round-123",
                           closes_at=now + timedelta(hours=5)))
    session.add(Assessment(organization_id=org.id, title="Later round", token="tok-later-round-1234",
                           closes_at=now + timedelta(days=5)))
    session.commit()
    session.close()
    reminders.send_due(now)
    reminders.send_due(now)
    assert _subjects() == ["Reminder: Python round closes soon"]
    assert SENT[0]["To"] == "meena@example.com" and "/assessment/tok-python-round-123" in SENT[0].get_content()

"""Email verification by a 6-digit code, and password changes signing other
devices out."""
import re
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.auth import email_verification
from app.auth import routes as auth_routes
from app.auth import service as auth_service
from app.auth.verified import NOT_VERIFIED_DETAIL, ensure_verified
from app.models import User
from app.orchestrator.routes import router as chat_router
from app.rate_limit import limiter

SENT: list = []


class FakeSMTP:
    def __init__(self, host, port, timeout=None, **kwargs):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        assert (user, password) == ("sender@example.com", "app-password")

    def send_message(self, message):
        SENT.append(message)


@pytest.fixture
def smtp(monkeypatch):
    SENT.clear()
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
    monkeypatch.setattr(email_verification.smtplib, "SMTP", FakeSMTP)
    return SENT


@pytest.fixture
def api(database):
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(auth_routes.router)
    app.include_router(chat_router)
    limiter.reset()
    with TestClient(app) as client:
        yield client


def signup(api, email="asha@example.com", password="asha-pass-123"):
    response = api.post("/auth/signup", json={"name": "Asha Rao", "email": email, "mobile": "+919999999999", "password": password, "consent": True})
    assert response.status_code == 201
    return response.json()


def bearer(token):
    return {"authorization": "Bearer " + token}


def last_code():
    text = SENT[-1].get_body(preferencelist=("plain",)).get_content()
    return re.search(r"\b(\d{6})\b", text).group(1)


def test_signup_emails_a_code_and_the_account_must_verify_before_using_agents(api, smtp):
    body = signup(api)
    assert body["user"]["email_verified"] is False and body["user"]["verification_required"] is True
    assert len(smtp) == 1 and smtp[0]["To"] == "asha@example.com" and "verification code" in smtp[0]["Subject"]
    token = body["access_token"]
    # The general chat and voice refuse until verified (the gateway uses the same check).
    response = api.post("/chat/route", json={"message": "what agents do you have"}, headers=bearer(token))
    assert response.status_code == 403 and response.json()["detail"] == NOT_VERIFIED_DETAIL
    assert api.post("/chat/transcribe", json={"audio_base64": "AAAA"}, headers=bearer(token)).status_code == 403

    verified = api.post("/auth/email/verify", json={"code": last_code()}, headers=bearer(token))
    assert verified.status_code == 200
    assert verified.json()["email_verified"] is True and verified.json()["verification_required"] is False
    assert api.get("/auth/me", headers=bearer(token)).json()["verification_required"] is False


def test_only_a_hash_of_the_code_is_stored(api, smtp, database):
    body = signup(api)
    code = last_code()
    session = database()
    try:
        row = session.get(User, body["user"]["id"])
        assert row.email_code_hash and code not in row.email_code_hash and len(row.email_code_hash) == 64
    finally:
        session.close()


def test_wrong_codes_count_down_then_lock(api, smtp):
    token = signup(api)["access_token"]
    real = last_code()
    wrong = "000000" if real != "000000" else "111111"
    messages = [api.post("/auth/email/verify", json={"code": wrong}, headers=bearer(token)).json()["detail"] for _ in range(5)]
    assert messages[0] == "That code is not right. 4 tries left."
    assert messages[-1] == "Too many wrong codes. Please ask for a new one."
    # Even the right code is refused once locked.
    locked = api.post("/auth/email/verify", json={"code": real}, headers=bearer(token))
    assert locked.status_code == 429


def test_an_expired_code_is_refused(api, smtp, database):
    body = signup(api)
    code = last_code()
    with pytest.raises(email_verification.VerificationError) as error:
        email_verification.verify_code(body["user"]["id"], code, now=datetime.utcnow() + timedelta(minutes=11))
    assert error.value.status_code == 400 and "expired" in error.value.message


def test_resending_has_a_cooldown_and_a_new_code_replaces_the_old(api, smtp):
    body = signup(api)
    token, first = body["access_token"], last_code()
    assert api.post("/auth/email/send-code", headers=bearer(token)).status_code == 429       # within a minute
    email_verification.send_code(body["user"]["id"], now=datetime.utcnow() + timedelta(seconds=61))
    second = last_code()
    if first != second:
        assert api.post("/auth/email/verify", json={"code": first}, headers=bearer(token)).status_code == 400
    assert api.post("/auth/email/verify", json={"code": second}, headers=bearer(token)).status_code == 200


def test_an_email_failure_shows_no_server_details(api, smtp, monkeypatch):
    class BrokenSMTP(FakeSMTP):
        def login(self, user, password):
            raise email_verification.smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted sender@example.com")

    user_id = signup(api)["user"]["id"]
    monkeypatch.setattr(email_verification.smtplib, "SMTP", BrokenSMTP)
    with pytest.raises(email_verification.VerificationError) as error:
        email_verification.send_code(user_id, now=datetime.utcnow() + timedelta(seconds=61))
    assert error.value.status_code == 502
    assert "sender@example.com" not in error.value.message and "535" not in error.value.message


def test_without_smtp_nobody_is_locked_out(api, monkeypatch):
    for name in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("EMAIL_VERIFICATION_REQUIRED", raising=False)
    body = signup(api)
    assert body["user"]["email_verified"] is False and body["user"]["verification_required"] is False
    ensure_verified(auth_service.get_by_id(body["user"]["id"]))          # does not raise


def test_verification_can_be_forced_off_or_on(monkeypatch, smtp):
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "false")
    assert email_verification.verification_required() is False
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "true")
    assert email_verification.verification_required() is True


def test_google_and_already_verified_accounts_pass(smtp, database):
    session = database()
    session.add(User(id="g", name="G", email="g@gmail.com", google_id="sub", email_verified=True))
    session.commit()
    session.close()
    ensure_verified(auth_service.get_by_id("g"))
    with pytest.raises(HTTPException):
        ensure_verified(None)


def test_changing_the_password_signs_out_every_other_device(api):
    old_token = signup(api, password="first-pass-123")["access_token"]
    response = api.put("/auth/password", json={"current_password": "first-pass-123", "new_password": "second-pass-456"}, headers=bearer(old_token))
    assert response.status_code == 200
    new_token = response.json()["access_token"]
    assert api.get("/auth/me", headers=bearer(old_token)).status_code == 401
    assert api.get("/auth/me", headers=bearer(new_token)).status_code == 200

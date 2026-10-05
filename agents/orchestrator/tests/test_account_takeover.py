"""Signup doesn't verify email, so an account can be registered under an
address its creator doesn't own. Proving ownership later (Google sign-in, or
the operator's ADMIN_EMAIL) must evict whoever set that account up first."""
import time

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import google_oauth, routes as auth_routes, security, service as auth_service
from app.auth.security import create_access_token, hash_password
from app.models import User
from app.rate_limit import limiter

VICTIM = "victim@gmail.com"


@pytest.fixture
def api(database):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(auth_routes.router)
    limiter.reset()
    with TestClient(app) as client:
        yield client


@pytest.fixture
def google_says(monkeypatch):
    def _profile(sub="google-sub-1", email=VICTIM):
        monkeypatch.setattr(
            google_oauth, "exchange_code",
            lambda code, redirect_uri: google_oauth.GoogleProfile(sub=sub, email=email, email_verified=True, name="Real Owner"),
        )
    return _profile


def signup(api, email=VICTIM, password="attacker-pass-123"):
    response = api.post("/auth/signup", json={"name": "Squatter", "email": email, "password": password, "consent": True})
    assert response.status_code == 201
    return response.json()["access_token"]


def bearer(token):
    return {"authorization": "Bearer " + token}


def google_login(api):
    response = api.post("/auth/google", json={"code": "c", "redirect_uri": "https://x/auth/google/callback"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_google_sign_in_evicts_whoever_pre_registered_the_email(api, google_says):
    squatter_token = signup(api)
    assert api.get("/auth/me", headers=bearer(squatter_token)).status_code == 200

    google_says()
    owner_token = google_login(api)

    # The squatter's session and password both stop working...
    assert api.get("/auth/me", headers=bearer(squatter_token)).status_code == 401
    assert api.post("/auth/login", json={"email": VICTIM, "password": "attacker-pass-123"}).status_code == 401
    # ...and the real owner is in, on the same account.
    me = api.get("/auth/me", headers=bearer(owner_token))
    assert me.status_code == 200 and me.json()["email"] == VICTIM
    user = auth_service.get_by_email(VICTIM)
    assert user.email_verified and user.password_hash is None and user.google_id == "google-sub-1"


def test_owner_can_set_a_new_password_after_the_takeover_is_undone(api, google_says):
    signup(api)
    google_says()
    owner_token = google_login(api)
    response = api.put("/auth/password", json={"new_password": "owner-pass-456"}, headers=bearer(owner_token))
    assert response.status_code == 200
    assert api.post("/auth/login", json={"email": VICTIM, "password": "owner-pass-456"}).status_code == 200


def test_linking_google_to_an_already_verified_account_keeps_its_password_and_sessions(api, google_says, database):
    session = database()
    session.add(User(id="owner", name="Owner", email=VICTIM, password_hash=hash_password("owner-pass-456"), email_verified=True))
    session.commit()
    session.close()
    old_token = create_access_token("owner")

    google_says()
    google_login(api)

    assert api.get("/auth/me", headers=bearer(old_token)).status_code == 200
    assert api.post("/auth/login", json={"email": VICTIM, "password": "owner-pass-456"}).status_code == 200


def test_new_google_accounts_are_verified(api, google_says):
    google_says(email="fresh@gmail.com")
    response = api.post("/auth/google", json={"code": "c", "redirect_uri": "https://x/cb", "consent": True})
    assert response.status_code == 200
    assert auth_service.get_by_email("fresh@gmail.com").email_verified


def test_tokens_issued_before_session_versions_existed_still_work(api, database):
    session = database()
    session.add(User(id="legacy", name="Legacy", email="legacy@x.io", password_hash=hash_password("legacy-pass")))
    session.commit()
    session.close()
    now = int(time.time())
    legacy_token = jwt.encode({"sub": "legacy", "iat": now, "exp": now + 600}, security.JWT_SECRET, algorithm="HS256")
    assert api.get("/auth/me", headers=bearer(legacy_token)).status_code == 200


def test_admin_seed_takes_over_an_unverified_account_squatting_on_admin_email(api, monkeypatch):
    squatter_token = signup(api, email="ops@digidara.example", password="squatter-pass")
    monkeypatch.setenv("ADMIN_EMAIL", "ops@digidara.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "operator-pass-789")

    auth_service.seed_admin_from_env()

    admin = auth_service.get_by_email("ops@digidara.example")
    assert admin.is_admin and admin.email_verified
    assert api.get("/auth/me", headers=bearer(squatter_token)).status_code == 401
    assert api.post("/auth/login", json={"email": "ops@digidara.example", "password": "squatter-pass"}).status_code == 401
    assert api.post("/auth/login", json={"email": "ops@digidara.example", "password": "operator-pass-789"}).status_code == 200


def test_admin_seed_promotes_a_verified_account_without_touching_its_password(api, database, monkeypatch):
    session = database()
    session.add(User(id="ops", name="Ops", email="ops@digidara.example", password_hash=hash_password("own-pass-123"), email_verified=True))
    session.commit()
    session.close()
    monkeypatch.setenv("ADMIN_EMAIL", "ops@digidara.example")
    monkeypatch.setenv("ADMIN_PASSWORD", "operator-pass-789")

    auth_service.seed_admin_from_env()

    assert auth_service.get_by_email("ops@digidara.example").is_admin
    assert api.post("/auth/login", json={"email": "ops@digidara.example", "password": "own-pass-123"}).status_code == 200

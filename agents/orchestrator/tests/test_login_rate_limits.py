"""A college's students share one IP address: many of them must be able to
sign in within the same minute, while guessing any one account's password
stays limited to 5 tries a minute."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import routes as auth_routes
from app.rate_limit import limiter


@pytest.fixture
def api(database):
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(auth_routes.router)
    limiter.reset()
    with TestClient(app) as client:
        yield client
    limiter.reset()


def signup(api, email):
    return api.post("/auth/signup", json={"name": "Learner", "email": email, "password": "learner-pass-123", "consent": True})


def login(api, email, password="learner-pass-123"):
    return api.post("/auth/login", json={"email": email, "password": password})


def test_thirty_classmates_on_one_ip_can_all_sign_up_and_sign_in(api):
    emails = [f"student{i}@college.edu" for i in range(30)]
    assert [signup(api, email).status_code for email in emails] == [201] * 30
    assert [login(api, email).status_code for email in emails] == [200] * 30


def test_password_guessing_on_one_account_is_still_limited(api):
    assert signup(api, "target@college.edu").status_code == 201
    codes = [login(api, "target@college.edu", password=f"guess-{i}-wrong").status_code for i in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429
    # The limit is per account, not per address: a classmate is unaffected.
    assert signup(api, "classmate@college.edu").status_code == 201
    assert login(api, "classmate@college.edu").status_code == 200


def test_the_account_limit_ignores_email_case_and_spaces(api):
    assert signup(api, "case@college.edu").status_code == 201
    variants = ["case@college.edu", "CASE@college.edu", " Case@College.edu ", "case@COLLEGE.EDU", "Case@college.edu", "case@college.edu"]
    codes = [login(api, email, password="wrong-password-1").status_code for email in variants]
    assert codes[-1] == 429

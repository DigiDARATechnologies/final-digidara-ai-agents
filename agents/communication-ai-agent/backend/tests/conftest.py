import os
from sqlalchemy.engine import make_url

import pytest

from app import create_app
from app.extensions import db
from app.services import groq_common



def integration_url(fallback):
    value = os.environ.get("INTEGRATION_DATABASE_URL")
    if not value:
        return fallback
    url = make_url(value)
    if url.get_backend_name() != "mysql" or not (url.database or "").endswith("_test"):
        raise RuntimeError("Integration tests require a dedicated MySQL database ending in _test")
    return value

@pytest.fixture(autouse=True)
def clear_groq_rate_limit_state():
    groq_common._groq_rate_limit_until.clear()
    yield
    groq_common._groq_rate_limit_until.clear()


@pytest.fixture()
def app():
    test_app = create_app({
        "TESTING": True,
        "OPENAI_API_KEY": "",
        "AI_PROVIDER": "auto",
        "SQLALCHEMY_DATABASE_URI": integration_url("sqlite:///:memory:"),
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "JWT_SECRET_KEY": "test-jwt-secret-with-at-least-32-bytes",
        "WTF_CSRF_ENABLED": False,
    })

    with test_app.app_context():
        db.drop_all()
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    response = client.post("/api/auth/guest")
    assert response.status_code == 200
    token = response.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}

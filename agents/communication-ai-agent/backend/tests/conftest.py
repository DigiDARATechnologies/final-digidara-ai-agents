import pytest

from app import create_app
from app.extensions import db
from app.services import groq_common


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
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "JWT_SECRET_KEY": "test-jwt-secret-with-at-least-32-bytes",
        "WTF_CSRF_ENABLED": False,
    })

    with test_app.app_context():
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

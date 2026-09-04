import os
from pathlib import Path
from urllib.parse import urlparse
import pytest
from flask_migrate import upgrade
from backend.app import create_app
from backend.app.config import Config
from backend.app.extensions import db


TEST_DATABASE_URL=os.getenv("TEST_DATABASE_URL","")


class TestConfig(Config):
    APP_ENV="testing"
    DEBUG=False
    TESTING=True
    SECRET_KEY="test-secret"
    SQLALCHEMY_DATABASE_URI=TEST_DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping":True,"pool_recycle":280}
    JWT_SECRET="test-jwt-secret"
    JWT_ALGORITHM="HS256"
    JWT_AUDIENCE="aptitude-ai"
    JWT_ISSUER="aptidara"
    AUTH_TOKEN_TTL_SECONDS=3600
    SINGLE_USER_MODE=False
    ALLOW_DEMO_QUESTIONS=True
    GROQ_API_KEY=""
    GROQ_MODEL="test"
    GROQ_FALLBACK_MODELS=()
    GROQ_TIMEOUT_SECONDS=1
    GROQ_CIRCUIT_FAILURE_THRESHOLD=2
    GROQ_CIRCUIT_COOLDOWN_SECONDS=1
    FRONTEND_ORIGIN="http://localhost:5173"
    QUESTION_SECONDS=60
    TIMEOUT_GRACE_SECONDS=3
    ABANDON_AFTER_SECONDS=3600
    WORKER_POLL_SECONDS=.01
    MAX_JOB_ATTEMPTS=2
    WORKER_HEARTBEAT_SECONDS=2
    WORKER_STALE_SECONDS=10
    REQUIRE_APPROVED_QUESTION_BANK=False


def pytest_sessionstart(session):
    if not TEST_DATABASE_URL:
        return
    if not TEST_DATABASE_URL.startswith("mysql+pymysql://"):
        raise pytest.UsageError("TEST_DATABASE_URL must use mysql+pymysql://")
    database=urlparse(TEST_DATABASE_URL.replace("mysql+pymysql://","mysql://",1)).path.strip("/")
    if not database.endswith("_test"):
        raise pytest.UsageError("Refusing to run: MySQL test database name must end with _test")


@pytest.fixture(scope="session")
def app():
    if not TEST_DATABASE_URL:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated MySQL schema ending in _test")
    app=create_app(TestConfig)
    with app.app_context():
        upgrade(directory=str(Path(__file__).resolve().parents[1]/"migrations"))
    yield app


@pytest.fixture(autouse=True)
def clean_mysql(app):
    with app.app_context():
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.execute(db.text("SET FOREIGN_KEY_CHECKS=1"))
        db.session.commit()


@pytest.fixture()
def client(app):return app.test_client()


@pytest.fixture()
def auth_headers(client):
    response=client.post("/api/aptitude/auth/register",json={"name":"Test Learner","email":"learner@example.com","password":"SecurePass123","course":"Computer Science","department":"Engineering","year":"Year 1","institution":"Test Institute","batch":"2026"})
    assert response.status_code==201
    return {"Authorization":f"Bearer {response.get_json()['token']}"}

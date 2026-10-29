"""Isolated real SQL tables; no developer database or external agent calls."""
import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "orchestrator-test-secret-with-at-least-32-characters"
os.environ["AGENT_SHARED_SECRET"] = "registry-test-secret"
os.environ["ALLOWED_AGENT_HOSTS"] = "localhost"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import db
from app.auth import service as auth_service, service_auth
from app.agent_state import service as agent_state_service
from app.chat_history import service as chat_history_service
from app.registry import routes, service
from app.gateway import routes as gateway

@pytest.fixture
def database(monkeypatch, tmp_path):
    test_url = os.environ.get("INTEGRATION_DATABASE_URL")
    if test_url:
        from sqlalchemy.engine import make_url
        url = make_url(test_url)
        if url.get_backend_name() != "mysql" or not (url.database or "").endswith("_test"):
            raise RuntimeError("Integration tests require a dedicated MySQL database ending in _test")
        engine = create_engine(test_url)
    else:
        # A file, with a connection per use (like MySQL's pool in production):
        # the app runs database work in worker threads, several at a time
        # (readiness asks every agent at once), and one shared in-memory
        # connection cannot be used from several threads at the same time.
        engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False, "timeout": 30},
                               pool_size=10, max_overflow=20)
    db.Base.metadata.drop_all(engine)
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    for module in (db, service, auth_service, chat_history_service, agent_state_service):
        monkeypatch.setattr(module, "get_session", factory)
    service_auth._seen_request_ids.clear()
    yield factory
    db.Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def client(database):
    app = FastAPI()
    app.include_router(routes.router)
    app.include_router(gateway.router)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def learner(database):
    """A signed-up account whose email is verified, id "learner"."""
    from app.models import User
    session = database()
    try:
        session.add(User(id="learner", name="Learner", email="learner@example.com", email_verified=True))
        session.commit()
    finally:
        session.close()
    return "learner"

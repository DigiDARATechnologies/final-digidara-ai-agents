"""Isolated real SQL tables; no developer database or external agent calls."""
import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "orchestrator-test-secret-with-at-least-32-characters"
os.environ["AGENT_SHARED_SECRET"] = "registry-test-secret"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app import db
from app.auth import service as auth_service, service_auth
from app.registry import routes, service
from app.gateway import routes as gateway

@pytest.fixture
def database(monkeypatch):
    test_url = os.environ.get("INTEGRATION_DATABASE_URL")
    if test_url:
        from sqlalchemy.engine import make_url
        url = make_url(test_url)
        if url.get_backend_name() != "mysql" or not (url.database or "").endswith("_test"):
            raise RuntimeError("Integration tests require a dedicated MySQL database ending in _test")
        engine = create_engine(test_url)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db.Base.metadata.drop_all(engine)
    db.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    for module in (db, service, auth_service):
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

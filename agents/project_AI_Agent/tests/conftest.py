"""Real graph and SQL models with disposable SQLite and memory checkpoints."""
import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["OPENAI_API_KEY"] = "test-unused-key"

from unittest.mock import MagicMock, patch
from langgraph.checkpoint.memory import MemorySaver
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Production initializes its MySQL checkpointer at import. Substitute only
# that storage adapter; retain the real graph wiring and node functions.
checkpointer = MemorySaver()
checkpointer.setup = lambda: None
with patch("pymysql.connect", return_value=MagicMock()), patch("langgraph.checkpoint.mysql.pymysql.PyMySQLSaver", return_value=checkpointer):
    from app.api import routes
from app import config
from app.agentic import qa_agent
from app.db.database import Base
from app.db.models import Student, Course, CourseMedium, ProjectAssignment
from app.graph import nodes

@pytest.fixture
def database(monkeypatch, tmp_path):
    def unexpected_ai_call(*args, **kwargs):
        raise AssertionError("Test attempted an uncontrolled AI call")
    monkeypatch.setattr(nodes, "call_json", unexpected_ai_call)
    monkeypatch.setattr(nodes, "call_text", unexpected_ai_call)
    test_url = os.environ.get("INTEGRATION_DATABASE_URL")
    if test_url:
        from sqlalchemy.engine import make_url
        url = make_url(test_url)
        if url.get_backend_name() != "mysql" or not (url.database or "").endswith("_test"):
            raise RuntimeError("Integration tests require a dedicated MySQL database ending in _test")
        engine = create_engine(test_url)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(routes, "get_session", factory)
    monkeypatch.setattr(nodes, "get_session", factory)
    monkeypatch.setattr(qa_agent, "get_session", factory)
    monkeypatch.setattr(config, "UPLOAD_DIR", tmp_path)
    with factory() as session:
        session.add(Student(id="student", name="Learner", email="learner@example.test"))
        session.add(Course(id="course", name="Python", medium=CourseMedium.local))
        session.flush()
        session.add(ProjectAssignment(id="assignment", thread_id="thread", student_id="student", course_id="course", medium=CourseMedium.local))
        session.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture
def state(database):
    return {"assignment_id": "assignment", "student_name": "Learner", "course_id": "course", "course_name": "Python", "course_medium": "local", "chosen_topic": {"id": "one", "title": "Task tracker", "summary": "Track daily tasks"}, "requirements": {}, "submission_guide": {}}

@pytest.fixture
def client(database):
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        yield client

@pytest.fixture
def workflow(client, state, monkeypatch):
    monkeypatch.setattr(routes, "_get_state_values", lambda thread: state.copy())
    graph = MagicMock()
    monkeypatch.setattr(routes, "compiled_graph", graph)
    questions = [{"id": i, "question": f"Explain concept {i}", "expected_concepts": ["private rubric"]} for i in range(10)]
    monkeypatch.setattr(routes, "generate_viva_questions", lambda *args: questions)
    monkeypatch.setattr(routes, "_run_submission", lambda value: {"status": "graded", "passed": True, "final_score": 85, "feedback": "Good work"})
    return graph

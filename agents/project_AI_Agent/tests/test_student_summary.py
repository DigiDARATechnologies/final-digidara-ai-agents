"""Phase 2 readiness skill: get_student_summary."""
import pytest

from app.api import readiness
from app.db.models import AssignmentStatus, ProjectAssignment, Submission, SubmissionStatus

HEADERS = {"x-digidara-user-id": "gateway-user-1"}


@pytest.fixture
def summary_db(database, monkeypatch):
    monkeypatch.setattr(readiness, "get_session", database)
    return database


def _invoke(client, email="learner@example.test", headers=HEADERS):
    return client.post("/api/invoke", json={"action": "get_student_summary", "payload": {"email": email}}, headers=headers)


def test_requires_verified_identity(client, summary_db):
    assert _invoke(client, headers={}).status_code == 401


def test_chosen_but_not_submitted(client, summary_db):
    body = _invoke(client).json()
    assert body["score"] is None
    assert body["gaps"] == ["Submit your capstone project for grading"]
    assert body["metrics"]["projects"] == 1


def test_best_graded_score(client, summary_db):
    with summary_db() as session:
        assignment = session.get(ProjectAssignment, "assignment")
        assignment.topic_json = {"title": "Task tracker"}
        assignment.status = AssignmentStatus.graded
        for index, (score, status) in enumerate(((62, SubmissionStatus.graded), (81, SubmissionStatus.pending_viva), (99, SubmissionStatus.error))):
            session.add(Submission(id=f"s{index}", assignment_id="assignment", docx_path="r.docx", zip_path="s.zip",
                                   status=status, score_json={"final_score": score}))
        session.commit()
    body = _invoke(client).json()
    assert body["score"] == 81.0
    assert body["strengths"] == ["Graded: Task tracker"]
    assert body["metrics"]["graded"] == 2 and body["metrics"]["submissions"] == 3


def test_unknown_learner_is_empty(client, summary_db):
    assert _invoke(client, email="nobody@example.test").json()["score"] is None

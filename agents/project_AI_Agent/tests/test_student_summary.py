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
    assert body["score"] is None and body["resume"]["projects"] == []
    assert body["gaps"] == ["Submit your capstone project for grading"]
    assert body["metrics"]["projects"] == 1


def test_best_graded_score(client, summary_db):
    with summary_db() as session:
        assignment = session.get(ProjectAssignment, "assignment")
        assignment.topic_json = {"title": "Task tracker", "summary": "Tracks tasks with due dates.", "skills_applied": ["Flask", "SQL"]}
        assignment.status = AssignmentStatus.graded
        for index, (score, status) in enumerate(((62, SubmissionStatus.graded), (81, SubmissionStatus.pending_viva), (99, SubmissionStatus.error))):
            session.add(Submission(id=f"s{index}", assignment_id="assignment", docx_path="r.docx", zip_path="s.zip",
                                   status=status, score_json={"final_score": score}))
        session.commit()
    body = _invoke(client).json()
    assert body["score"] == 81.0
    assert body["strengths"] == ["Graded: Task tracker"]
    assert body["metrics"]["graded"] == 2 and body["metrics"]["submissions"] == 3
    # Graded code but no viva passed yet: half of Beginner, no level completed.
    assert body["level_scores"] == {"easy": 50.0, "medium": 0.0, "hard": 0.0, "professional": 0.0}
    assert body["metrics"]["projects_passed"] == 0
    # The submitted project, for the learner's resume.
    assert body["resume"]["projects"] == [
        {"title": "Task tracker", "description": "Tracks tasks with due dates.", "skills": ["Flask", "SQL"], "score": 81.0}]


def test_unknown_learner_is_empty(client, summary_db):
    assert _invoke(client, email="nobody@example.test").json()["score"] is None


def test_a_level_is_a_project_that_passed_both_the_code_grading_and_the_viva():
    def sub(assignment, status, score, viva, passed=True):
        return Submission(id=f"{assignment}-{score}", assignment_id=assignment, status=status, viva_passed=viva,
                          score_json={"final_score": score, "passed": passed})
    assert readiness.level_scores([]) == {"easy": 0.0, "medium": 0.0, "hard": 0.0, "professional": 0.0}
    # Two projects passed (two tries of the first count once); a third failed its code grading.
    submissions = [sub("a", SubmissionStatus.graded, 80, True), sub("a", SubmissionStatus.graded, 90, True),
                   sub("b", SubmissionStatus.graded, 95, True), sub("c", SubmissionStatus.needs_revision, 30, None, False)]
    assert readiness.level_scores(submissions) == {"easy": 100.0, "medium": 100.0, "hard": 0.0, "professional": 0.0}
    # A third project waiting for its viva is half of Hard.
    submissions.append(sub("d", SubmissionStatus.pending_viva, 70, None))
    assert readiness.level_scores(submissions)["hard"] == 50.0
    # A failed viva does not count.
    assert readiness.level_scores([sub("e", SubmissionStatus.graded, 88, False)])["easy"] == 50.0

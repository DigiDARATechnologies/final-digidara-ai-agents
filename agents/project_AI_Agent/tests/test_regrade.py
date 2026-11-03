"""Second chances for projects graded before the run fix."""
from datetime import datetime, timedelta, timezone

import pytest

from app.api import regrade
from app.db.models import ProjectAssignment, ProjectRegrade, Student, Submission, SubmissionStatus

BEFORE = regrade.RUN_FIX_AT - timedelta(days=1)
AFTER = regrade.RUN_FIX_AT + timedelta(days=1)
HEADERS = {"x-digidara-user-id": "gateway-user-1"}
ERROR = "ModuleNotFoundError: No module named 'storage'"


@pytest.fixture
def db(database, monkeypatch):
    monkeypatch.setattr(regrade, "get_session", database)
    return database


def _submission(db, sid, status=SubmissionStatus.graded, passed=True, score=70, viva=True, feedback=ERROR, at=BEFORE):
    with db() as session:
        session.add(Submission(id=sid, assignment_id="assignment", docx_path="r.docx", zip_path="s.zip", submitted_at=at, status=status,
                               viva_passed=viva, feedback_text=feedback,
                               score_json={"final_score": score, "passed": passed, "feedback": feedback}))
        session.commit()


def _email(db):
    with db() as session:
        assignment = session.get(ProjectAssignment, "assignment")
        return session.get(Student, assignment.student_id).email


def test_a_project_hit_by_the_bug_gets_three_chances(db):
    _submission(db, "s1")
    offers = regrade.offers(_email(db))
    assert len(offers) == 1 and offers[0]["chances_left"] == 3 and offers[0]["score"] == 70 and offers[0]["passed"] is True


def test_a_project_without_that_error_or_graded_after_the_fix_gets_none(db):
    _submission(db, "s1", feedback="Good work.")
    _submission(db, "s2", at=AFTER)
    assert regrade.offers(_email(db)) == []


def test_a_passed_project_reopens_until_its_chances_are_used(db):
    _submission(db, "s1")
    assert regrade.upload_gate("assignment", "graded") == "open"
    for _ in range(regrade.CHANCES):
        regrade.use_chance("assignment")
    assert regrade.upload_gate("assignment", "graded") == "closed"
    assert regrade.offers(_email(db)) == []
    regrade.use_chance("assignment")          # never below zero
    with db() as session:
        assert session.get(ProjectRegrade, "assignment").chances_left == 0


def test_a_student_who_passed_keeps_that_pass_after_failing_every_chance(db):
    _submission(db, "s1", score=70)
    assert regrade.upload_gate("assignment", "needs_revision") == "open"
    for _ in range(regrade.CHANCES):
        regrade.use_chance("assignment")
    assert regrade.upload_gate("assignment", "needs_revision") == "used_up"
    earlier = regrade.earlier_result("assignment")
    assert earlier["status"] == "graded" and earlier["passed"] is True and earlier["final_score"] == 70
    assert regrade.kept_submission_id("assignment") == "s1"


def test_a_student_who_had_not_passed_can_still_resubmit_after_the_chances(db):
    _submission(db, "s1", status=SubmissionStatus.needs_revision, passed=False, score=55, viva=None)
    assert regrade.upload_gate("assignment", "needs_revision") == "open"
    for _ in range(regrade.CHANCES):
        regrade.use_chance("assignment")
    assert regrade.upload_gate("assignment", "needs_revision") == "normal"
    assert regrade.earlier_result("assignment") is None and regrade.kept_submission_id("assignment") is None


def test_a_project_nobody_touched_follows_the_usual_rules(db):
    assert regrade.upload_gate("assignment", "graded") == "closed"
    assert regrade.upload_gate("assignment", "needs_revision") == "normal"


def test_offers_need_the_verified_user(client, db):
    body = {"action": "regrade_offers", "payload": {"email": _email(db)}}
    assert client.post("/api/invoke", json=body).status_code == 401
    assert client.post("/api/invoke", json=body, headers=HEADERS).json() == {"offers": []}

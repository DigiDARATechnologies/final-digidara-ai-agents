"""Second chances for projects graded before the run fix.

Until RUN_FIX_AT the grader ran a project's entry file from the top folder, so
src/main.py could not import the files beside it and correct projects lost marks
to a ModuleNotFoundError that was ours. Each such project gets CHANCES more
submissions, even past its deadline. A chance is used only by a submission that
is actually graded (a packaging rejection costs none).

A student who had passed keeps that pass: a chance can only add a better result,
and once the chances are used the earlier result is theirs again. A student who
had not passed could already resubmit without limit, and still can.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from app.db.database import get_session
from app.db.models import ProjectAssignment, ProjectRegrade, Student, Submission, SubmissionStatus

CHANCES = 3
RUN_FIX_AT = datetime.fromisoformat(os.environ.get("CAPSTONE_RUN_FIX_AT", "2026-11-03T00:00:00+00:00"))
_THE_ERROR = re.compile(r"ModuleNotFoundError|No module named", re.IGNORECASE)
_GRADED = (SubmissionStatus.graded, SubmissionStatus.needs_revision, SubmissionStatus.pending_viva)


def _utc(value: datetime | None) -> datetime | None:
    # SQLite does not keep tzinfo; everything stored here is UTC.
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _hit_by_the_bug(submission: Submission) -> bool:
    submitted = _utc(submission.submitted_at)
    if submitted is None or submitted >= RUN_FIX_AT or submission.status not in _GRADED:
        return False
    score = submission.score_json or {}
    return any(_THE_ERROR.search(str(text or "")) for text in (
        submission.review_markdown, submission.feedback_text, score.get("feedback"), score.get("score_reasoning")))


def _passed(submission: Submission) -> bool:
    return (submission.status == SubmissionStatus.graded and (submission.score_json or {}).get("passed") is True
            and submission.viva_passed is True)


def _score(submission: Submission) -> float | None:
    value = (submission.score_json or {}).get("final_score")
    return float(value) if isinstance(value, (int, float)) else None


def _grant(session, assignment: ProjectAssignment) -> ProjectRegrade | None:
    """The assignment's chances, granted the first time they are looked for."""
    row = session.query(ProjectRegrade).filter_by(assignment_id=assignment.id).one_or_none()
    if row is not None:
        return row
    submissions = (session.query(Submission).filter_by(assignment_id=assignment.id)
                   .order_by(Submission.submitted_at).all())
    hit = [submission for submission in submissions if _hit_by_the_bug(submission)]
    if not hit:
        return None
    passed = [submission for submission in submissions if _passed(submission)]
    kept = passed[-1] if passed else hit[-1]
    row = ProjectRegrade(assignment_id=assignment.id, student_id=assignment.student_id, submission_id=kept.id,
                         original_passed=bool(passed), original_score=_score(kept), chances_left=CHANCES)
    session.add(row)
    return row


def offers(email: str) -> list[dict]:
    """This student's projects with chances left, for the notification bell."""
    session = get_session()
    try:
        result = []
        for student in session.query(Student).filter_by(email=email).all():
            for assignment in session.query(ProjectAssignment).filter_by(student_id=student.id).all():
                row = _grant(session, assignment)
                if row is None or row.chances_left <= 0:
                    continue
                topic = assignment.topic_json or {}
                result.append({
                    "thread_id": assignment.thread_id,
                    "title": str(topic.get("title") or topic.get("name") or "Your capstone project")[:120],
                    "chosen_topic": assignment.topic_json,
                    "requirements": assignment.requirements_json,
                    "deadline_at": _utc(assignment.deadline_at).isoformat() if assignment.deadline_at else None,
                    "score": row.original_score,
                    "passed": row.original_passed,
                    "chances_left": row.chances_left,
                    "reason": row.reason,
                })
        session.commit()
        return result
    finally:
        session.close()


def upload_gate(assignment_id: str, status: str | None) -> str:
    """May this assignment take a submission? "normal": the usual rules apply.
    "open": it has chances left, so a graded project reopens and the deadline
    does not apply. "closed": it is graded with no chances. "used_up": a project
    that had passed used every chance without passing again."""
    session = get_session()
    try:
        assignment = session.get(ProjectAssignment, assignment_id)
        row = _grant(session, assignment) if assignment is not None else None
        session.commit()
        if row is not None and row.chances_left > 0:
            return "open"
        if status == "graded":
            return "closed"
        if row is not None and row.original_passed and status == "needs_revision":
            return "used_up"
        return "normal"
    finally:
        session.close()


def use_chance(assignment_id: str) -> None:
    session = get_session()
    try:
        row = session.query(ProjectRegrade).filter_by(assignment_id=assignment_id).one_or_none()
        if row is not None and row.chances_left > 0:
            row.chances_left -= 1
            session.commit()
    finally:
        session.close()


def earlier_result(assignment_id: str) -> dict | None:
    """The pass a student keeps, as the project's state."""
    session = get_session()
    try:
        row = session.query(ProjectRegrade).filter_by(assignment_id=assignment_id).one_or_none()
        submission = session.get(Submission, row.submission_id) if row is not None and row.original_passed else None
        if submission is None:
            return None
        score = submission.score_json or {}
        return {"status": "graded", "final_score": row.original_score, "passed": True, "revision_notes": None,
                "feedback": score.get("feedback"), "score_reasoning": score.get("score_reasoning"),
                "code_quality_score": score.get("code_quality_score")}
    finally:
        session.close()


def kept_submission_id(assignment_id: str | None) -> str | None:
    """The submission whose certificate and report a student keeps, if any."""
    if not assignment_id:
        return None
    session = get_session()
    try:
        row = session.query(ProjectRegrade).filter_by(assignment_id=assignment_id).one_or_none()
        return row.submission_id if row is not None and row.original_passed else None
    finally:
        session.close()

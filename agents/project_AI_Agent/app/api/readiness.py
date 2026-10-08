"""Phase 2 readiness skill: the learner's capstone project progress.

Score: the best graded project score (0-100) across the learner's
submissions. A project that is chosen but not yet graded has no score; the
summary says what is left to do instead.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func

from app.db.database import get_session
from app.db.models import AssignmentStatus, ProjectAssignment, Student, Submission, SubmissionStatus

GRADED = {SubmissionStatus.graded, SubmissionStatus.pending_viva}


def _title(assignment: ProjectAssignment) -> str:
    topic = assignment.topic_json or {}
    return str(topic.get("title") or topic.get("name") or "Capstone project")[:120]


def build_student_summary(assignments: list[ProjectAssignment], submissions: list[Submission]) -> dict[str, Any]:
    empty: dict[str, Any] = {"schema": "digidara.student_summary.v1", "score": None, "activity_count": 0,
                             "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {}}
    if not assignments:
        return empty
    by_assignment = {a.id: a for a in assignments}
    graded = [s for s in submissions if s.status in GRADED and isinstance((s.score_json or {}).get("final_score"), (int, float))]
    best = max(graded, key=lambda s: float(s.score_json["final_score"]), default=None)
    times: list[datetime] = [t for t in [a.created_at for a in assignments] + [s.submitted_at for s in submissions] if t]
    gaps: list[str] = []
    if best is None:
        if any(a.status == AssignmentStatus.needs_revision for a in assignments):
            gaps.append("Revise and resubmit your capstone project")
        elif submissions:
            gaps.append("Your capstone submission is still being graded")
        else:
            gaps.append("Submit your capstone project for grading")
    elif best.viva_passed is False:
        gaps.append("Pass the project viva (oral defense)")
    strengths = [f"Graded: {_title(by_assignment[best.assignment_id])}"] if best and best.assignment_id in by_assignment else []
    return {
        "schema": "digidara.student_summary.v1",
        "score": round(float(best.score_json["final_score"]), 1) if best else None,
        "activity_count": len(assignments) + len(submissions),
        "last_activity_at": max(times).isoformat() if times else None,
        "strengths": strengths,
        "gaps": gaps,
        "metrics": {
            "projects": len(assignments),
            "submissions": len(submissions),
            "graded": len(graded),
            "viva_passed": bool(best and best.viva_passed),
        },
    }


def student_summary(email: str) -> dict[str, Any]:
    session = get_session()
    try:
        students = session.query(Student).filter(func.lower(Student.email) == email).all() if email else []
        ids = [s.id for s in students]
        assignments = session.query(ProjectAssignment).filter(ProjectAssignment.student_id.in_(ids)).all() if ids else []
        assignment_ids = [a.id for a in assignments]
        submissions = (session.query(Submission).filter(Submission.assignment_id.in_(assignment_ids)).all()
                       if assignment_ids else [])
        return build_student_summary(assignments, submissions)
    finally:
        session.close()

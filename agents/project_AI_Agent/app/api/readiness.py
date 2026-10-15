"""Phase 2 readiness skill: the learner's capstone project progress.

Score: the best graded project score (0-100) across the learner's
submissions. A project that is chosen but not yet graded has no score; the
summary says what is left to do instead.

Levels: projects do not have a difficulty, so a level is a passed project --
one that passed BOTH the code grading and the viva. The first passed project
completes Beginner, the second Medium, the third Hard, the fourth
Professional. A project whose code passed but whose viva is not passed yet
is half of the next level.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func

from app.db.database import get_session
from app.db.models import AssignmentStatus, ProjectAssignment, Student, Submission, SubmissionStatus
from app.api.role_periods import clean_periods, in_periods

GRADED = {SubmissionStatus.graded, SubmissionStatus.pending_viva}
LEVEL_KEYS = ("easy", "medium", "hard", "professional")


def _code_passed(submission: Submission) -> bool:
    score = submission.score_json or {}
    return (submission.status in GRADED and isinstance(score.get("final_score"), (int, float))
            and score.get("passed") is not False)


def level_scores(submissions: list[Submission]) -> dict[str, float]:
    """Progress (0-100) at each level, counted in passed projects."""
    passed = {s.assignment_id for s in submissions if _code_passed(s) and s.viva_passed is True}
    waiting = {s.assignment_id for s in submissions if _code_passed(s)} - passed
    done = len(passed)
    return {key: 100.0 if done > index else 50.0 if done == index and waiting else 0.0
            for index, key in enumerate(LEVEL_KEYS)}


def _title(assignment: ProjectAssignment) -> str:
    topic = assignment.topic_json or {}
    return str(topic.get("title") or topic.get("name") or "Capstone project")[:120]


def _resume_projects(assignments: list[ProjectAssignment], submissions: list[Submission]) -> list[dict[str, Any]]:
    """Projects the learner built and submitted, for their resume: title,
    what it does and the skills it used (from the topic they chose)."""
    best: dict[int, float | None] = {}
    for s in submissions:
        score = (s.score_json or {}).get("final_score") if s.status in GRADED else None
        current = best.get(s.assignment_id)
        best[s.assignment_id] = score if isinstance(score, (int, float)) and (current is None or score > current) else current
    projects = []
    for a in assignments:
        if a.id not in best:
            continue
        topic = a.topic_json or {}
        skills = [str(x)[:40] for x in (topic.get("skills_applied") or []) if str(x).strip()][:8]
        projects.append({
            "title": _title(a),
            "description": str(topic.get("summary") or "")[:400],
            "skills": skills,
            "score": round(float(best[a.id]), 1) if best[a.id] is not None else None,
        })
    return projects[:4]


def _project_status(submissions: list[Submission]) -> str:
    """Where one project stands, from its submissions."""
    if any(_code_passed(s) and s.viva_passed is True for s in submissions):
        return "passed (code and viva)"
    if any(_code_passed(s) for s in submissions):
        return "code passed, viva not passed yet"
    if any(s.status == SubmissionStatus.needs_revision for s in submissions):
        return "needs revision"
    if all(s.status == SubmissionStatus.error for s in submissions):
        return "grading failed, resubmit"
    return "submitted, being graded"


def recent_projects(assignments: list[ProjectAssignment], submissions: list[Submission]) -> list[dict[str, Any]]:
    """Each project the learner submitted, newest first: its title, when it was
    last submitted, where it stands and its best score -- so they can ask Boss
    "which projects did I submit?"."""
    by_assignment: dict[str, list[Submission]] = {}
    for submission in submissions:
        by_assignment.setdefault(submission.assignment_id, []).append(submission)
    rows = []
    for assignment in assignments:
        tries = by_assignment.get(assignment.id)
        if not tries:
            continue
        last = max((s.submitted_at for s in tries if s.submitted_at), default=None)
        scores = [float(s.score_json["final_score"]) for s in tries if _code_passed(s)]
        row: dict[str, Any] = {"date": last.isoformat() if last else "", "title": _title(assignment),
                               "status": _project_status(tries), "submissions": len(tries)}
        if scores:
            row["score"] = round(max(scores), 1)
        rows.append(row)
    rows.sort(key=lambda row: row["date"], reverse=True)
    return rows[:10]


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
            "projects_passed": len({s.assignment_id for s in submissions if _code_passed(s) and s.viva_passed is True}),
        },
        "level_scores": level_scores(submissions),
        "recent": recent_projects(assignments, submissions),
        "resume": {"projects": _resume_projects(assignments, submissions)},
    }


def student_summary(email: str, periods: Any = None) -> dict[str, Any]:
    """periods: the orchestrator's role periods; only projects started inside them count."""
    windows = clean_periods(periods)
    session = get_session()
    try:
        students = session.query(Student).filter(func.lower(Student.email) == email).all() if email else []
        ids = [s.id for s in students]
        assignments = session.query(ProjectAssignment).filter(ProjectAssignment.student_id.in_(ids)).all() if ids else []
        assignments = [a for a in assignments if in_periods(a.created_at, windows)]
        assignment_ids = [a.id for a in assignments]
        submissions = (session.query(Submission).filter(Submission.assignment_id.in_(assignment_ids)).all()
                       if assignment_ids else [])
        return build_student_summary(assignments, submissions)
    finally:
        session.close()

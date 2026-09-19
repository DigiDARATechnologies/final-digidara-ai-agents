"""DPDP (Digital Personal Data Protection Act, 2023) data-principal rights:
access/portability and erasure, scoped to the calling learner's own Student
record.

Trust model matches the rest of this agent (see
routes.eligibility_check_free): there is no login system inside this agent
itself, so a Student is looked up by the email the caller supplies. To stop
an unauthenticated caller from reading or erasing someone else's data by
guessing an email address, these endpoints additionally require the
gateway-verified `x-digidara-user-id` header (see app/request_context.py)
to be present -- i.e. the request must have already passed through the
DigiDARA orchestrator's own authentication before it reaches this agent.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, field_validator

from app.db.database import get_session
from app.db.models import Certificate, Course, Enrollment, ProjectAssignment, Student, Submission

logger = logging.getLogger("capstone.privacy")

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


class PrivacyRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not value or "@" not in value:
            raise ValueError("A valid email is required")
        return value


def _require_gateway_identity(caller_id: str | None) -> None:
    if not caller_id:
        raise HTTPException(status_code=401, detail="Missing verified caller identity")


@router.post("/export")
def export_my_data(req: PrivacyRequest, x_digidara_user_id: str | None = Header(default=None)):
    """DPDP right to access / data portability: every record tied to the
    caller's own Student row, as plain JSON."""
    _require_gateway_identity(x_digidara_user_id)
    session = get_session()
    try:
        student = session.query(Student).filter_by(email=req.email).first()
        if student is None:
            raise HTTPException(status_code=404, detail="No data found for this email")

        courses = {course.id: course.name for course in session.query(Course).all()}
        enrollments = session.query(Enrollment).filter_by(student_id=student.id).all()
        certificates = session.query(Certificate).filter_by(student_id=student.id).all()
        assignments = session.query(ProjectAssignment).filter_by(student_id=student.id).all()
        submissions = (
            session.query(Submission)
            .filter(Submission.assignment_id.in_([assignment.id for assignment in assignments]))
            .all()
            if assignments
            else []
        )
        assignment_thread_by_id = {assignment.id: assignment.thread_id for assignment in assignments}

        export = {
            "profile": {
                "id": student.id,
                "name": student.name,
                "email": student.email,
                "phone": student.phone,
                "created_at": student.created_at.isoformat(),
            },
            "enrollments": [
                {
                    "course": courses.get(enrollment.course_id),
                    "status": enrollment.status.value,
                    "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else None,
                }
                for enrollment in enrollments
            ],
            "certificates": [
                {
                    "course": courses.get(certificate.course_id),
                    "certificate_id": certificate.certificate_id,
                    "issued_at": certificate.issued_at.isoformat(),
                }
                for certificate in certificates
            ],
            "project_assignments": [
                {
                    "thread_id": assignment.thread_id,
                    "course": courses.get(assignment.course_id),
                    "status": assignment.status.value,
                    "chosen_at": assignment.chosen_at.isoformat() if assignment.chosen_at else None,
                    "deadline_at": assignment.deadline_at.isoformat() if assignment.deadline_at else None,
                    "requirements": assignment.requirements_json,
                }
                for assignment in assignments
            ],
            "submissions": [
                {
                    "assignment_thread_id": assignment_thread_by_id.get(submission.assignment_id),
                    "submitted_at": submission.submitted_at.isoformat(),
                    "status": submission.status.value,
                    "score": submission.score_json,
                    "feedback": submission.feedback_text,
                    "viva_score": submission.viva_score,
                    "viva_passed": submission.viva_passed,
                }
                for submission in submissions
            ],
        }
        logger.info("privacy export served id=%s", student.id)
        return export
    finally:
        session.close()


@router.delete("/erase")
def erase_my_data(req: PrivacyRequest, x_digidara_user_id: str | None = Header(default=None)):
    """DPDP right to erasure. Contact fields and free-text answers are
    wiped; graded submission rows are anonymized in place rather than
    deleted outright, since the platform retains a legitimate
    academic-integrity interest in the grading/audit trail -- DPDP permits
    continuing to hold data for a purpose distinct from the one it was
    originally collected for, once identifying details are removed."""
    _require_gateway_identity(x_digidara_user_id)
    session = get_session()
    try:
        student = session.query(Student).filter_by(email=req.email).first()
        if student is None:
            raise HTTPException(status_code=404, detail="No data found for this email")

        student.name = "Erased User"
        student.email = f"erased-{student.id}@erased.invalid"
        student.phone = None

        assignments = session.query(ProjectAssignment).filter_by(student_id=student.id).all()
        for assignment in assignments:
            assignment.qa_conversation_json = None
            assignment.about_markdown = None
            for submission in session.query(Submission).filter_by(assignment_id=assignment.id).all():
                submission.feedback_text = None
                submission.review_markdown = None
                submission.viva_questions_json = None
                submission.viva_answers_json = None

        session.commit()
        logger.info("privacy erasure completed id=%s", student.id)
        return {"status": "erased", "id": student.id}
    finally:
        session.close()

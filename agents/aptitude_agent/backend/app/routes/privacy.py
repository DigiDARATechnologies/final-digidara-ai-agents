"""DPDP (Digital Personal Data Protection Act) data-principal rights:
consent recording, data export, and erasure for the authenticated learner.

Identity here is never taken from a request body -- ``require_student``
resolves ``g.student`` from the verified JWT (or the single-user session),
so every endpoint below only ever acts on the caller's own record.
"""
from datetime import datetime, timezone

from flask import Blueprint, g, request

from ..extensions import db
from ..models import AptitudeAnswer, AptitudeTest, LearnerLastTopics, LearnerMixedTestConfig
from ..services.audit_service import record_event
from ..utils.authentication import require_student
from ..utils.errors import APIError

bp = Blueprint("privacy", __name__, url_prefix="/api/aptitude")

CURRENT_CONSENT_VERSION = "1.0"


@bp.post("/me/consent")
@require_student
def record_consent():
    body = request.get_json(silent=True) or {}
    version = str(body.get("version") or CURRENT_CONSENT_VERSION).strip()[:20]
    if not body.get("granted", True):
        raise APIError("Consent must be granted to continue using this service", 400, "consent_required")
    g.student.data_consent_at = datetime.now(timezone.utc)
    g.student.data_consent_version = version
    record_event("consent_recorded", g.student.id, metadata={"version": version})
    db.session.commit()
    return {"consented": True, "version": version, "consented_at": g.student.data_consent_at.isoformat()}


@bp.get("/me/export")
@require_student
def export_my_data():
    """DPDP right to access / data portability: every record tied to the
    caller's own account, as plain JSON."""
    student = g.student
    tests = AptitudeTest.query.filter_by(student_id=student.id).all()
    answers = AptitudeAnswer.query.filter_by(student_id=student.id).all()
    mixed_config = LearnerMixedTestConfig.query.filter_by(learner_id=student.id).all()
    last_topics = LearnerLastTopics.query.filter_by(learner_id=student.id).all()

    export = {
        "profile": {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "phone": student.phone,
            "course": student.course,
            "department": student.department,
            "year": student.year,
            "institution": student.institution,
            "batch": student.batch,
            "created_at": student.created_at.isoformat(),
            "data_consent_version": student.data_consent_version,
            "data_consent_at": student.data_consent_at.isoformat() if student.data_consent_at else None,
        },
        "tests": [
            {
                "id": test.id,
                "status": test.status,
                "started_at": test.started_at.isoformat() if test.started_at else None,
                "completed_at": test.completed_at.isoformat() if test.completed_at else None,
                "score": test.score,
                "percentage": float(test.percentage) if test.percentage is not None else None,
                "test_mode": test.test_mode,
            }
            for test in tests
        ],
        "answers": [
            {
                "test_id": answer.test_id,
                "selected_answer": answer.selected_answer,
                "is_correct": answer.is_correct,
                "confidence_rating": answer.confidence_rating,
                "reasoning_text": answer.reasoning_text,
                "mistake_explanation": answer.mistake_explanation,
                "answered_at": answer.answered_at.isoformat() if answer.answered_at else None,
            }
            for answer in answers
        ],
        "mixed_test_config": [
            {"category": config.category_name, "question_count": config.question_count}
            for config in mixed_config
        ],
        "last_topics": [
            {"category_id": topic.category_id, "level": topic.level, "topics_used": topic.topics_used}
            for topic in last_topics
        ],
    }
    record_event("data_export_requested", student.id)
    db.session.commit()
    return export


@bp.delete("/me")
@require_student
def erase_my_account():
    """DPDP right to erasure. Contact details, profile media, and free-text
    answer content are wiped and every issued session token is invalidated.
    Aggregate performance rows (score/accuracy counters, with no free text)
    are kept for platform analytics since they no longer identify anyone
    once the profile itself is anonymized."""
    student = g.student

    anonymized_email = f"erased-{student.id}@erased.invalid"
    student.name = "Erased User"
    student.email = anonymized_email
    student.phone = None
    student.course = None
    student.department = None
    student.year = None
    student.institution = None
    student.batch = None
    student.profile_photo = None
    student.profile_photo_mime = None
    student.password_hash = None
    student.token_version = (student.token_version or 0) + 1

    AptitudeAnswer.query.filter_by(student_id=student.id).update(
        {"reasoning_text": None, "mistake_explanation": None, "reasoning_feedback": None},
        synchronize_session=False,
    )
    LearnerMixedTestConfig.query.filter_by(learner_id=student.id).delete(synchronize_session=False)
    LearnerLastTopics.query.filter_by(learner_id=student.id).delete(synchronize_session=False)

    record_event("account_erased", student.id)
    db.session.commit()
    return {"status": "erased", "id": student.id}

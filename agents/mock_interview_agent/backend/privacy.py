"""DPDP export and erasure for one learner, keyed by their platform email.

Called only from routes/invoke.py after the gateway-verified identity header
is present; the email comes from the orchestrator's own account record.
"""
from __future__ import annotations

import logging

import db
from services.media_storage import delete_managed_audio, delete_managed_avatar

logger = logging.getLogger("mock_interview.privacy")


def _student(email: str):
    row, _ = db.query("SELECT * FROM students WHERE email = %s", (email,), fetchone=True)
    return row


def export_student(email: str) -> dict:
    student = _student(email)
    if student is None:
        return {"profile": None}
    interviews, _ = db.query(
        "SELECT * FROM interviews WHERE student_id = %s ORDER BY id", (student["id"],), fetch=True
    )
    for interview in interviews:
        details, _ = db.query(
            "SELECT question_order, question, answer, verdict, verdict_reason, ideal_answer, "
            "timed_out, time_taken_sec, answer_audio_path, created_at, answered_at "
            "FROM interview_details WHERE interview_id = %s ORDER BY question_order",
            (interview["id"],), fetch=True,
        )
        interview["questions"] = details
    usage, _ = db.query(
        "SELECT usage_date, answered_count FROM daily_usage WHERE student_id = %s ORDER BY usage_date",
        (student["id"],), fetch=True,
    )
    return {"profile": student, "interviews": interviews, "daily_usage": usage}


def erase_student(email: str) -> dict:
    """Wipe contact details, free-text answers, recordings and the avatar.

    Interview rows keep their numeric scores, which no longer identify anyone
    once the profile itself is anonymized.
    """
    student = _student(email)
    if student is None:
        return {"status": "no_data"}
    student_id = student["id"]

    audio_rows, _ = db.query(
        "SELECT d.answer_audio_path FROM interview_details d "
        "JOIN interviews i ON i.id = d.interview_id "
        "WHERE i.student_id = %s AND d.answer_audio_path IS NOT NULL",
        (student_id,), fetch=True,
    )
    for row in audio_rows:
        delete_managed_audio(row["answer_audio_path"])
    delete_managed_avatar(student.get("avatar_url"))

    db.query(
        "UPDATE interview_details d JOIN interviews i ON i.id = d.interview_id "
        "SET d.answer = NULL, d.answer_audio_path = NULL, d.processing_error = NULL "
        "WHERE i.student_id = %s",
        (student_id,),
    )
    db.query(
        "UPDATE interviews SET strengths = NULL, weaknesses = NULL, feedback = NULL WHERE student_id = %s",
        (student_id,),
    )
    db.query("DELETE FROM user_question_history WHERE user_id = %s", (student_id,))
    db.query(
        "UPDATE students SET name = 'Erased User', email = %s, phone = NULL, course_enrolled = NULL, "
        "target_role = NULL, bio = NULL, avatar_url = NULL WHERE id = %s",
        (f"erased-{student_id}@erased.invalid", student_id),
    )
    logger.info("privacy erasure completed id=%s", student_id)
    return {"status": "erased", "id": student_id}

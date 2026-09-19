"""Non-blocking live-question search for already-created interviews."""

import logging
from concurrent.futures import ThreadPoolExecutor

import db
from ai.question_generation import fetch_live_real_questions

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="live-question-search")


def upgrade_unserved_questions_with_real(interview_id, real_questions):
    """Replace only future, unserved main-question slots in one transaction."""
    if not real_questions:
        return {"upgraded": 0, "skipped": 0, "reason": "no_real_questions"}

    conn = db.get_conn()
    cursor = conn.cursor(dictionary=True)
    try:
        conn.start_transaction()
        cursor.execute(
            "SELECT status FROM interviews WHERE id = %s FOR UPDATE",
            (interview_id,),
        )
        interview = cursor.fetchone()
        if not interview or interview["status"] != "in_progress":
            conn.rollback()
            return {"upgraded": 0, "skipped": len(real_questions), "reason": "interview_not_active"}

        # The earliest unanswered question is currently visible to the student,
        # so only rows after it are eligible for replacement.
        cursor.execute(
            """SELECT id, question_order
               FROM interview_details
               WHERE interview_id = %s AND is_followup = FALSE
                 AND answer IS NULL AND verdict IS NULL AND timed_out = FALSE
               ORDER BY question_order, id
               FOR UPDATE""",
            (interview_id,),
        )
        pending = cursor.fetchall()
        future_slots = pending[1:]
        replacements = min(len(future_slots), len(real_questions))
        for slot, real in zip(future_slots, real_questions):
            cursor.execute(
                """UPDATE interview_details
                   SET question = %s, question_source = 'real',
                       topic_area = %s
                   WHERE id = %s""",
                (
                    real["question"],
                    real.get("topic_area") or "frequently asked interview question",
                    slot["id"],
                ),
            )
        conn.commit()
        return {
            "upgraded": replacements,
            "skipped": len(real_questions) - replacements,
            "reason": "completed",
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def _search_and_upgrade(interview_id, role, difficulty, round_type, count, role_skills, already_asked_hashes):
    try:
        real_questions = fetch_live_real_questions(
            role, difficulty, round_type, count,
            already_asked_hashes=already_asked_hashes,
            role_skills=role_skills,
        )
        result = upgrade_unserved_questions_with_real(interview_id, real_questions)
        logger.info(
            "Background live-question search completed for interview %s: upgraded=%s skipped=%s reason=%s",
            interview_id, result["upgraded"], result["skipped"], result["reason"],
            extra={"event": "background_live_question_search_completed"},
        )
        return result
    except Exception:
        logger.exception(
            "Background live-question search failed for interview %s; retaining AI plan",
            interview_id,
            extra={"event": "background_live_question_search_failed"},
        )
        return {"upgraded": 0, "skipped": 0, "reason": "search_error"}


def schedule_live_question_search(interview_id, role, difficulty, round_type, count, role_skills, already_asked_hashes):
    """Submit work and return immediately; never block the Flask request."""
    return _executor.submit(
        _search_and_upgrade,
        interview_id, role, difficulty, round_type, count, role_skills,
        set(already_asked_hashes or ()),
    )

"""Audio transcription and answer-submission routes."""

import logging
import json
from io import BytesIO
from uuid import uuid4

from flask import Blueprint, jsonify, request

import db
import groq_client
from http_context import log, set_log_context
from policies import counts_toward_daily_limit
from runtime_state import submission_locks
from services.interview_state import (
    daily_answered_count,
    merge_question_context,
    merge_topic_area_context,
    quota_payload,
    format_question_for_display,
    recent_questions_for_student,
    recent_topic_areas_for_student,
    usage_date as get_usage_date,
)
from services.media_storage import delete_managed_audio
from services.ai_usage import track_ai_usage
from services.role_interviews import role_subject_prompt, subject_for_question
from services.question_history import (
    get_recent_asked_history,
    question_hash,
    record_served_questions,
)
from settings import (
    ALLOWED_AUDIO_TYPES,
    AUDIO_UPLOAD_DIR,
    AUDIO_URL_PREFIX,
    DAILY_ANSWER_LIMIT,
    DAILY_LIMIT_ENABLED,
    DAILY_LIMIT_MESSAGE,
    MAX_AUDIO_UPLOAD_BYTES,
)
from validation import ValidationError, boolean, bounded_int, positive_int, text


answers_bp = Blueprint("answers", __name__)


@answers_bp.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    audio_type = (audio_file.mimetype or "").split(";", 1)[0].lower()
    if audio_type not in ALLOWED_AUDIO_TYPES:
        return jsonify({"error": "Use a WebM, OGG, M4A, MP3, or WAV recording."}), 400
    audio_bytes = audio_file.stream.read(MAX_AUDIO_UPLOAD_BYTES + 1)
    if not audio_bytes:
        return jsonify({"error": "The uploaded recording is empty."}), 400
    if len(audio_bytes) > MAX_AUDIO_UPLOAD_BYTES:
        return jsonify({"error": "The uploaded recording is too large."}), 413

    round_type = "technical"
    subject = None
    question = None
    raw_interview_id = request.form.get("interview_id")
    audio_path = None
    student_id = None
    question_id = None
    interview_id = None
    if raw_interview_id:
        interview_id = positive_int(raw_interview_id, "interview_id")
        question_order = positive_int(
            request.form.get("question_order"), "question_order"
        )
        set_log_context(interview_id=interview_id)
        detail, _ = db.query(
            """SELECT d.id, d.answer_audio_path, d.question,
                      i.round_type, i.subject, i.student_id
               FROM interview_details d
               JOIN interviews i ON i.id = d.interview_id
               WHERE d.interview_id = %s AND d.question_order = %s
               ORDER BY d.id DESC
               LIMIT 1""",
            (interview_id, question_order),
            fetchone=True,
        )
        if not detail:
            return jsonify({"error": "Interview question not found."}), 404
        round_type = detail["round_type"]
        subject = detail.get("subject")
        question = detail.get("question")
        # Some legacy/database test fixtures do not project student_id; the
        # transcription usage record may safely omit it in that case.
        student_id = detail.get("student_id")
        question_id = detail["id"]
        extension = ALLOWED_AUDIO_TYPES[audio_type]
        filename = (
            f"{interview_id}-{question_order}-{uuid4().hex}{extension}"
        )
        AUDIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        destination = AUDIO_UPLOAD_DIR / filename
        destination.write_bytes(audio_bytes)
        audio_path = f"{AUDIO_URL_PREFIX}{filename}"
        try:
            db.query(
                """UPDATE interview_details
                   SET answer_audio_path = %s
                   WHERE id = %s""",
                (audio_path, detail["id"]),
            )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        delete_managed_audio(detail.get("answer_audio_path"))
    try:
        with track_ai_usage(
            student_id=student_id,
            interview_id=interview_id,
            question_id=question_id,
            request_type="audio_transcription",
        ):
            transcript_text = groq_client.transcribe_audio(
                BytesIO(audio_bytes),
                audio_file.filename,
                round_type,
                subject=subject,
                question=question,
            )
    except Exception:
        log(
            logging.ERROR,
            "audio_transcription_failed",
            "Audio transcription failed",
            exc_info=True,
        )
        return jsonify({"error": "Transcription service is temporarily unavailable."}), 502

    return jsonify({
        "transcript": transcript_text,
        "audio_path": audio_path,
    })



@answers_bp.route("/submit_answer", methods=["POST"])
def submit_answer():
    data = request.get_json(silent=True) or {}
    interview_id = positive_int(data.get("interview_id"), "interview_id")
    question_order = positive_int(data.get("question_order"), "question_order")
    set_log_context(interview_id=interview_id)
    data.update({
        "interview_id": interview_id,
        "question_order": question_order,
        "answer": text(data.get("answer"), "answer", max_length=20000),
        "time_taken_sec": bounded_int(
            data.get("time_taken_sec", 0), "time_taken_sec", 0, 600
        ),
        "timed_out": boolean(data.get("timed_out", False), "timed_out"),
    })
    if not data["answer"] and not data["timed_out"]:
        raise ValidationError("answer is required unless the question timed out.")
    log(
        logging.INFO,
        "answer_submission_received",
        "Answer submission received",
        question_order=question_order,
    )
    with submission_locks.acquire((interview_id, question_order)):
        response = _submit_answer(data)
    log(
        logging.INFO,
        "answer_submission_completed",
        "Answer submission completed",
        question_order=question_order,
    )
    return response


def _submit_answer(data):
    interview_id = data["interview_id"]
    question_order = data["question_order"]
    answer = data.get("answer") or ""
    time_taken_sec = data.get("time_taken_sec", 0)
    timed_out = bool(data.get("timed_out")) and not answer.strip()
    current, _ = db.query(
        """SELECT *
           FROM interview_details
           WHERE interview_id = %s AND question_order = %s
           ORDER BY id DESC
           LIMIT 1""",
        (interview_id, question_order), fetchone=True,
    )
    if not current:
        return jsonify({"error": "Question not found for this interview."}), 404

    interview_row, _ = db.query(
        "SELECT * FROM interviews WHERE id = %s", (interview_id,), fetchone=True
    )
    if not interview_row or interview_row["status"] != "in_progress":
        total_questions = int(interview_row["num_questions"]) if interview_row else 5
        return jsonify({
            "interview_id": interview_id,
            "done": True,
            "verdict": current.get("verdict"),
            "verdict_reason": current.get("verdict_reason"),
            "zero_marked": bool(current.get("timed_out")),
            "answered_question_verdict": {
                "question_order": current["question_order"],
                "verdict": current.get("verdict"),
                "reason": current.get("verdict_reason"),
            },
            "total_questions": total_questions,
        })

    question_limit = int(interview_row["num_questions"])
    set_log_context(student_id=interview_row["student_id"])

    # Ignore any follow-up row left in an older in-progress interview.
    next_existing, _ = db.query(
        """SELECT question_order, question, question_source, topic_area, is_followup
           FROM interview_details
           WHERE interview_id = %s AND question_order > %s AND is_followup = FALSE
           ORDER BY question_order, id
           LIMIT 1""",
        (interview_id, question_order), fetchone=True,
    )

    rows, _ = db.query(
        "SELECT * FROM interview_details WHERE interview_id = %s ORDER BY question_order, id",
        (interview_id,), fetch=True,
    )
    asked_so_far = [r["question"] for r in rows]
    topic_areas_so_far = [
        row.get("topic_area")
        for row in reversed(rows)
        if not row["is_followup"] and row.get("topic_area")
    ]

    # Planned main questions exist from session start; count only completed
    # ones so a preloaded 10-question plan does not end after question one.
    real_question_count = sum(
        1 for r in rows
        if not r["is_followup"] and (
            r.get("verdict") is not None or bool(r.get("timed_out"))
            or r.get("answer") is not None
        )
    )
    evaluation_complete = False
    batch_answer_saved = False

    if (
        current.get("verdict") is not None
        or bool(current.get("timed_out"))
    ):
        answered_count = daily_answered_count(interview_row["student_id"])
        verdict_payload = {
            "verdict": current.get("verdict"),
            "verdict_reason": current.get("verdict_reason"),
            "zero_marked": bool(current.get("timed_out")),
            "answered_question_verdict": {
                "question_order": current["question_order"],
                "verdict": current.get("verdict"),
                "reason": current.get("verdict_reason"),
            },
            "total_questions": question_limit,
            **quota_payload(answered_count),
        }
        if (
            real_question_count >= question_limit
            or verdict_payload["daily_limit_reached"]
        ):
            return jsonify({
                "interview_id": interview_id,
                "done": True,
                "message": (
                    DAILY_LIMIT_MESSAGE
                    if verdict_payload["daily_limit_reached"]
                    else None
                ),
                **verdict_payload,
            })
        if next_existing:
            return jsonify({
                "interview_id": interview_id,
                "question_order": next_existing["question_order"],
                **format_question_for_display(next_existing),
                "topic_area": next_existing.get("topic_area"),
                "is_followup": bool(next_existing["is_followup"]),
                "done": False,
                **verdict_payload,
            })
        # The answer was evaluated but the next-question response may have
        # failed before it was persisted. Continue from the evaluated state.
        answer = current.get("answer") or answer
        verdict = current.get("verdict")
        verdict_reason = current.get("verdict_reason")
        ideal_answer = current.get("ideal_answer")
        timed_out = bool(current.get("timed_out"))
        evaluation_complete = True

    usage_day = get_usage_date()
    answer_evaluation = None
    if evaluation_complete:
        answered_count = daily_answered_count(
            interview_row["student_id"], usage_day
        )
    elif current.get("answer") is not None:
        # A previous request saved and counted the answer but failed during
        # AI evaluation. Resume without saving or counting it again.
        answer = current["answer"]
        answered_count = daily_answered_count(
            interview_row["student_id"], usage_day
        )
    elif answer.strip():
        usage_result = db.save_answer_with_optional_daily_usage(
            current["id"],
            interview_row["student_id"],
            usage_day,
            answer,
            time_taken_sec,
            DAILY_ANSWER_LIMIT,
            count_toward_daily_limit=counts_toward_daily_limit(
                enabled=DAILY_LIMIT_ENABLED,
                is_followup=bool(current["is_followup"]),
                has_answer=bool(answer.strip()),
            ),
        )
        if usage_result["limit_reached"]:
            quota = quota_payload(usage_result["answered_count"])
            return jsonify({
                "interview_id": interview_id,
                "done": True,
                "error": DAILY_LIMIT_MESSAGE,
                "message": DAILY_LIMIT_MESSAGE,
                **quota,
            })
        if not usage_result["saved"]:
            # Another request saved it first. Resume processing that persisted
            # answer without consuming quota twice.
            current, _ = db.query(
                "SELECT * FROM interview_details WHERE id = %s",
                (current["id"],),
                fetchone=True,
            )
            answer = current.get("answer") or answer
            answered_count = daily_answered_count(
                interview_row["student_id"], usage_day
            )
        else:
            answered_count = usage_result["answered_count"]
    else:
        # Empty timeout submissions are not answered questions and consume no
        # daily quota. The verdict update below marks the row as timed out.
        db.query(
            """UPDATE interview_details
               SET time_taken_sec = %s
               WHERE id = %s AND answer IS NULL AND verdict IS NULL""",
            (time_taken_sec, current["id"]),
        )
        answered_count = daily_answered_count(
            interview_row["student_id"], usage_day
        )

    current["answer"] = answer if answer.strip() else None
    current["time_taken_sec"] = time_taken_sec

    # Batch-evaluation mode stores the answer and advances immediately. The
    # single evaluator call is made by /api/end_interview after all answers.
    if not evaluation_complete and not timed_out:
        db.query(
            """UPDATE interview_details
               SET answered_at = NOW(), processing_status = 'answered',
                   processing_error = NULL
               WHERE id = %s""",
            (current["id"],),
        )
        verdict = None
        verdict_reason = None
        ideal_answer = None
        evaluation_complete = True
        real_question_count += 1
        batch_answer_saved = True

    if evaluation_complete:
        pass
    elif timed_out:
        verdict = "wrong"
        verdict_reason = "No answer was given within the time limit."
        try:
            with track_ai_usage(
                student_id=interview_row["student_id"],
                interview_id=interview_id,
                question_id=current["id"],
                request_type="ideal_answer_generation",
            ):
                ideal_answer = groq_client.generate_ideal_answer(
                    current["question"],
                    interview_row["difficulty"],
                    interview_row["round_type"],
                )
        except Exception:
            # The timeout verdict must remain deterministic even if OpenAI is
            # temporarily unavailable for the optional learning aid.
            log(
                logging.WARNING,
                "timeout_ideal_answer_generation_failed",
                "Optional ideal answer generation failed after timeout",
                question_order=question_order,
                exc_info=True,
            )
            ideal_answer = None
        db.query(
            """UPDATE interview_details
               SET verdict = %s, verdict_reason = %s, timed_out = TRUE,
                   ideal_answer = %s, answered_at = NOW(),
                   processing_status = 'evaluated', processing_error = NULL
               WHERE id = %s""",
            (verdict, verdict_reason, ideal_answer, current["id"]),
        )
        current["timed_out"] = True
    else:
        db.query(
            """UPDATE interview_details
               SET processing_status = 'evaluating', processing_error = NULL
               WHERE id = %s""",
            (current["id"],),
        )
        try:
            with track_ai_usage(
                student_id=interview_row["student_id"],
                interview_id=interview_id,
                question_id=current["id"],
                request_type="answer_evaluation",
            ):
                answer_evaluation = groq_client.evaluate_answer(
                    current["question"],
                    answer,
                    interview_row["difficulty"],
                    interview_row["round_type"],
                )
        except Exception as exc:
            log(
                logging.ERROR,
                "answer_evaluation_failed",
                "Answer evaluation failed",
                question_order=question_order,
                exc_info=True,
            )
            db.query(
                """UPDATE interview_details
                   SET processing_status = 'failed', processing_error = %s
                   WHERE id = %s""",
                (str(exc)[:500], current["id"]),
            )
            return jsonify({
                "error": "AI evaluation is temporarily unavailable. Retry to continue.",
                "retryable": True,
                "interview_id": interview_id,
                "question_order": question_order,
            }), 503
        verdict = answer_evaluation["verdict"]
        verdict_reason = answer_evaluation["reason"]
        ideal_answer = answer_evaluation.get("ideal_answer")
        db.query(
            """UPDATE interview_details
               SET verdict = %s, verdict_reason = %s, ideal_answer = %s,
                   processing_status = 'evaluated', processing_error = NULL
               WHERE id = %s""",
            (verdict, verdict_reason, ideal_answer, current["id"]),
        )

    # Include the question just evaluated when deciding whether the planned
    # session has reached its configured main-question limit.
    if not current["is_followup"] and current.get("verdict") is None and not batch_answer_saved:
        real_question_count += 1

    verdict_payload = {
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "zero_marked": timed_out,
        "answered_question_verdict": {
            "question_order": current["question_order"],
            "verdict": verdict,
            "reason": verdict_reason,
        },
        "total_questions": question_limit,
        **quota_payload(answered_count),
    }
    # Re-read before issuing anything else because another active interview
    # for the same student may have consumed the last quota unit meanwhile.
    verdict_payload.update(quota_payload(
        daily_answered_count(interview_row["student_id"], usage_day)
    ))

    # The configured main-question limit always wins.
    if (
        real_question_count >= question_limit
        or verdict_payload["daily_limit_reached"]
    ):
        return jsonify({
            "interview_id": interview_id,
            "done": True,
            "message": (
                DAILY_LIMIT_MESSAGE
                if verdict_payload["daily_limit_reached"]
                else None
            ),
            **verdict_payload,
        })

    if next_existing:
        return jsonify({
            "interview_id": interview_id,
            "question_order": next_existing["question_order"],
            **format_question_for_display(next_existing),
            "topic_area": next_existing.get("topic_area"),
            "is_followup": bool(next_existing["is_followup"]),
            "done": False,
            **verdict_payload,
        })

    return _issue_next_question(
        interview_id,
        interview_row,
        question_order,
        asked_so_far,
        topic_areas_so_far,
        extra=verdict_payload,
    )


def _issue_next_question(
    interview_id,
    interview_row,
    question_order,
    asked_so_far,
    topic_areas_so_far,
    extra=None,
):
    answered_count = daily_answered_count(interview_row["student_id"])
    quota = quota_payload(answered_count)
    if quota["daily_limit_reached"]:
        payload = {
            "interview_id": interview_id,
            "done": True,
            "message": DAILY_LIMIT_MESSAGE,
            **quota,
        }
        if extra:
            payload.update(extra)
            payload.update(quota)
        return jsonify(payload)

    role_subjects = None
    if interview_row.get("interview_mode") in {"role", "weak_topic_practice"}:
        try:
            stored_subjects = interview_row.get("resolved_subjects")
            role_subjects = (
                stored_subjects
                if isinstance(stored_subjects, list)
                else json.loads(stored_subjects or "[]")
            )
        except (TypeError, ValueError):
            role_subjects = []
        if not role_subjects:
            return jsonify({"error": "Role interview subjects are unavailable. Please start a new session."}), 409
    history_subject = interview_row.get("role_name") if role_subjects else interview_row["subject"]
    history_scope = history_subject or "hr"
    role_skills = (
        groq_client.infer_role_skills(history_scope, interview_row["difficulty"])
        if interview_row["round_type"] == "technical" and history_scope
        else None
    )
    already_asked_hashes, history_question_texts = get_recent_asked_history(
        interview_row["student_id"], interview_row["round_type"], history_scope,
        interview_row["difficulty"],
    )
    historical_questions = recent_questions_for_student(
        interview_row["student_id"],
        interview_row["round_type"],
        history_subject,
        interview_row["difficulty"],
    )
    question_context = merge_question_context(
        asked_so_far,
        historical_questions,
        history_question_texts,
    )
    historical_topic_areas = recent_topic_areas_for_student(
        interview_row["student_id"],
        interview_row["round_type"],
        history_subject,
    )
    topic_area_context = merge_topic_area_context(
        topic_areas_so_far,
        historical_topic_areas,
    )

    try:
        with track_ai_usage(
            student_id=interview_row["student_id"],
            interview_id=interview_id,
            request_type="next_question_generation",
        ) as usage_scope:
            main_count, _ = db.query(
                """SELECT COUNT(*) AS count FROM interview_details
                   WHERE interview_id = %s AND is_followup = FALSE""",
                (interview_id,), fetchone=True,
            )
            main_count = main_count or {"count": 0}
            main_question_index = int(main_count["count"] or 0)
            next_subject = subject_for_question(role_subjects, main_question_index) if role_subjects else interview_row["subject"]
            for attempt in range(3):
                generated_question = groq_client.generate_question(
                    interview_row["round_type"], next_subject,
                    interview_row["difficulty"], question_context,
                    topic_area_context,
                    role_context=role_subject_prompt(interview_row["role_name"], next_subject) if role_subjects else None,
                    role_skills=role_skills,
                )
                if question_hash(generated_question["question"]) not in already_asked_hashes:
                    break
                log(logging.WARNING, "historical_question_collision", "Generated next question matched recent completed history", attempt=attempt + 1)
                question_context.append(generated_question["question"])
        next_question = generated_question["question"]
        next_topic_area = generated_question["topic_area"]
    except Exception as exc:
        log(
            logging.ERROR,
            "next_question_generation_failed",
            "Next question generation failed",
            question_order=question_order,
            exc_info=True,
        )
        db.query(
            """UPDATE interview_details
               SET processing_status = 'failed', processing_error = %s
               WHERE interview_id = %s AND question_order = %s""",
            (str(exc)[:500], interview_id, question_order),
        )
        return jsonify({
            "error": "The next question could not be prepared. Retry to continue.",
            "retryable": True,
            "interview_id": interview_id,
            "question_order": question_order,
        }), 503
    # The LLM call takes time; verify again before persisting or showing the
    # question in case another session used the final quota unit meanwhile.
    answered_count = daily_answered_count(interview_row["student_id"])
    quota = quota_payload(answered_count)
    if quota["daily_limit_reached"]:
        payload = {
            "interview_id": interview_id,
            "done": True,
            "message": DAILY_LIMIT_MESSAGE,
            **quota,
        }
        if extra:
            payload.update(extra)
            payload.update(quota)
        return jsonify(payload)

    _, next_question_id = db.query(
        """INSERT INTO interview_details
             (interview_id, question_order, question, question_source, topic_area, subject_tag, is_followup)
           VALUES (%s, %s, %s, %s, %s, %s, FALSE)""",
        (
            interview_id,
            question_order + 1,
            next_question,
            "ai_generated",
            next_topic_area,
            next_subject if role_subjects else interview_row["subject"],
        ),
    )
    usage_scope.attach(interview_id, next_question_id)
    record_served_questions(
        interview_row["student_id"], interview_row["round_type"], history_scope,
        interview_row["difficulty"], interview_id,
        [{"question": next_question, "source": "ai_generated"}],
    )
    db.query(
        """UPDATE interview_details
           SET processing_status = 'next_ready', processing_error = NULL
           WHERE interview_id = %s AND question_order = %s""",
        (interview_id, question_order),
    )
    payload = {
        "interview_id": interview_id,
        "question_order": question_order + 1,
        **format_question_for_display({
            "question": next_question,
            "source": "ai_generated",
        }),
        "topic_area": next_topic_area,
        "is_followup": False,
        "done": False,
        **quota,
    }
    if extra:
        payload.update(extra)
        payload.update(quota)
    return jsonify(payload)

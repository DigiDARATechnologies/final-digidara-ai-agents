"""Interview lifecycle and usage routes."""

import logging
import json
import io
import os
import re
import time
from uuid import UUID

from flask import Blueprint, jsonify, request, send_file

import db
import groq_client
import scoring
from http_context import log, set_log_context
from policies import completion_progress, exit_transition
from runtime_state import dashboard_cache
from services.interview_state import (
    active_interview_payload,
    daily_answered_count,
    merge_question_context,
    merge_topic_area_context,
    quota_payload,
    recent_questions_for_student,
    recent_topic_areas_for_student,
    format_question_for_display,
)
from services.focus_tracking import finalize_open_focus_events, focus_summary
from services.ai_usage import track_ai_usage
from services.role_interviews import (
    normalize_weak_topic_areas,
    role_subject_prompt,
    subject_breakdown,
    subject_for_question,
)
from services.question_history import (
    get_recent_asked_history,
    question_hash,
    record_served_questions,
)
from services.background_question_search import schedule_live_question_search
from services.report_pdf import generate_interview_report_pdf
from settings import (
    ALLOWED_QUESTION_COUNTS,
    DAILY_LIMIT_ENABLED,
    DAILY_LIMIT_MESSAGE,
    MAX_SUBJECT_LENGTH,
)
from validation import ValidationError, bounded_int, positive_int, text


interviews_bp = Blueprint("interviews", __name__)
logger = logging.getLogger(__name__)


def _batch_evaluations_or_error(interview_row, interview_id, pending_rows):
    """Run and validate the single batch evaluator without leaking 500s."""
    try:
        with track_ai_usage(
            student_id=interview_row["student_id"],
            interview_id=interview_id,
            request_type="answer_evaluation_batch",
        ):
            evaluations = groq_client.evaluate_answers_batch(
                interview_row["round_type"], interview_row["subject"], interview_row["difficulty"],
                [{"question_id": row["id"], "question": row["question"], "answer": row.get("answer") or ""} for row in pending_rows],
            )
        by_id = {int(item.get("question_id", -1)): item for item in evaluations}
        expected = {int(row["id"]) for row in pending_rows}
        if len(evaluations) != len(pending_rows) or set(by_id) != expected:
            raise ValueError("Batch evaluation did not return exactly one result for each question.")
        return evaluations, None
    except Exception as exc:
        logger.exception("Batch interview evaluation failed for interview %s", interview_id)
        return None, str(exc)


def _live_web_search_enabled():
    """Return whether optional source-backed question search is enabled."""
    return os.environ.get("ENABLE_LIVE_WEB_SEARCH", "false").strip().casefold() in {
        "1", "true", "yes", "on"
    }


def _generate_unique_question(generate, already_asked_hashes, asked_context):
    """Retry an exact historical hash collision twice without failing a session."""
    for attempt in range(3):
        generated = generate(asked_context)
        if question_hash(generated["question"]) not in already_asked_hashes:
            return generated
        log(logging.WARNING, "historical_question_collision", "Generated question matched recent completed history", attempt=attempt + 1)
        asked_context.append(generated["question"])
    log(logging.WARNING, "historical_question_collision_allowed", "Allowed a repeated question after two regeneration attempts")
    return generated


@interviews_bp.route("/start_interview", methods=["POST"])
def start_interview():
    request_started_at = time.perf_counter()
    timing = {
        "role_subjects_resolved_seconds": 0.0,
        "skill_inference_seconds": 0.0,
        "question_generation_seconds": 0.0,
        "db_write_seconds": 0.0,
        "background_schedule_seconds": 0.0,
    }
    data = request.get_json(silent=True) or {}
    student_id = positive_int(data.get("student_id"), "student_id")
    set_log_context(student_id=student_id)
    round_type = text(
        data.get("round_type"), "round_type", required=True, max_length=20
    ).lower()
    if round_type not in {"technical", "hr"}:
        raise ValidationError("round_type must be technical or hr.")
    interview_mode = text(
        data.get("interview_mode", "course"), "interview_mode", required=True,
        max_length=32,
    ).lower()
    if interview_mode not in {"course", "custom_topic", "role", "weak_topic_practice"}:
        raise ValidationError("interview_mode is invalid.")

    raw_subject = data.get("subject")
    subject = raw_subject.strip() if isinstance(raw_subject, str) else None
    difficulty = text(
        data.get("difficulty"), "difficulty", required=True, max_length=20
    ).lower()
    if difficulty not in {"beginner", "intermediate", "advanced"}:
        raise ValidationError(
            "difficulty must be beginner, intermediate, or advanced."
        )

    role_name = text(data.get("role_name"), "role_name", max_length=150)
    resolved_subjects = data.get("resolved_subjects")
    if interview_mode in {"role", "weak_topic_practice"}:
        if round_type != "technical" or not role_name:
            raise ValidationError("Role interviews require a technical role name.")
        if resolved_subjects is not None:
            if not isinstance(resolved_subjects, list) or not all(isinstance(item, str) for item in resolved_subjects):
                raise ValidationError("resolved_subjects must be a list of subjects.")
            resolved_subjects = [item.strip().lower() for item in resolved_subjects if item.strip()]
        else:
            try:
                role_resolution_started_at = time.perf_counter()
                with track_ai_usage(student_id=student_id, request_type="role_decomposition"):
                    resolved_subjects = groq_client.resolve_role_subjects(role_name)
                timing["role_subjects_resolved_seconds"] = round(
                    time.perf_counter() - role_resolution_started_at, 4
                )
                log(
                    logging.INFO,
                    "role_subjects_resolved",
                    "Resolved role subjects for interview start",
                    elapsed_seconds=timing["role_subjects_resolved_seconds"],
                    role=role_name,
                )
            except Exception:
                log(logging.ERROR, "role_decomposition_failed", "Role decomposition failed", exc_info=True)
                return jsonify({"error": "The role could not be mapped to interview subjects. Please try again."}), 503
        if interview_mode == "weak_topic_practice":
            resolved_subjects = normalize_weak_topic_areas(resolved_subjects)
            log(
                logging.INFO,
                "weak_topic_retest_scope_resolved",
                "Resolved weak-topic retest to exact skill areas",
                role=role_name,
                skill_areas=resolved_subjects,
            )
        if not 1 <= len(resolved_subjects) <= 10:
            raise ValidationError("Role interviews need between 1 and 10 skill areas.")
        subject = resolved_subjects[0]
    elif round_type == "technical" and not subject:
        raise ValidationError("Select a preset subject or enter a custom topic.")
    if subject and len(subject) > MAX_SUBJECT_LENGTH:
        raise ValidationError(
            f"Subject must be {MAX_SUBJECT_LENGTH} characters or fewer."
        )
    if round_type == "hr":
        subject = None
        role_name = None
        resolved_subjects = None

    num_questions = bounded_int(
        data.get("num_questions", 5), "num_questions", 1, 10
    )
    if num_questions not in ALLOWED_QUESTION_COUNTS:
        raise ValidationError("num_questions must be either 5 or 10.")

    student, _ = db.query(
        "SELECT id FROM students WHERE id = %s", (student_id,), fetchone=True
    )
    if not student:
        return jsonify({"error": "Student not found."}), 404

    answered_count = daily_answered_count(student_id)
    quota = quota_payload(answered_count)

    existing = active_interview_payload(student_id)
    if existing and existing["active"]:
        set_log_context(interview_id=existing["interview_id"])
        return jsonify({
            **existing,
            "resumed_existing": True,
            "message": "Resuming your interview already in progress.",
            "requested_questions": existing["total_questions"],
            "quota_adjusted": False,
            **quota,
        })
    if quota["daily_limit_reached"]:
        return jsonify({
            "error": DAILY_LIMIT_MESSAGE,
            "message": DAILY_LIMIT_MESSAGE,
            **quota,
        }), 429

    requested_questions = num_questions
    if DAILY_LIMIT_ENABLED:
        num_questions = min(requested_questions, quota["daily_remaining"])

    history_subject = role_name if interview_mode in {"role", "weak_topic_practice"} else subject
    history_scope = history_subject or "hr"
    already_asked_hashes, history_question_texts = get_recent_asked_history(
        student_id, round_type, history_scope, difficulty
    )
    previous_questions = recent_questions_for_student(
        student_id, round_type, history_subject, difficulty
    )
    question_context = merge_question_context(previous_questions, history_question_texts)
    previous_topic_areas = recent_topic_areas_for_student(
        student_id, round_type, history_subject
    )
    topic_area_context = merge_topic_area_context(previous_topic_areas)

    # Role sessions receive a session-start plan: source-backed FAQ questions
    # where live search can verify them, plus existing live AI questions.
    question_plan = None
    try:
        with track_ai_usage(
            student_id=student_id, request_type="initial_question_generation"
        ) as usage_scope:
            role_skill_scope = role_name or subject
            # A weak-topic retest is deliberately restricted to the exact
            # topic_area values flagged in the completed interview.  Do not
            # re-infer the full role skill list, which would dilute the retest.
            skill_inference_started_at = time.perf_counter()
            if interview_mode == "weak_topic_practice":
                role_skills = list(resolved_subjects)
            elif round_type == "technical" and role_skill_scope:
                role_skills = groq_client.infer_role_skills(role_skill_scope, difficulty)
            else:
                role_skills = None
            timing["skill_inference_seconds"] = round(
                time.perf_counter() - skill_inference_started_at, 4
            )
            log(
                logging.INFO,
                "role_skill_inference_completed",
                "Completed role-skill inference for interview start",
                elapsed_seconds=timing["skill_inference_seconds"],
                role=role_skill_scope,
            )
            if role_skills:
                log(
                    logging.INFO,
                    "role_skills_resolved",
                    "Resolved role skills before question-plan generation",
                    role=role_skill_scope,
                    skills=role_skills,
                )
            question_subject = subject_for_question(resolved_subjects, 0) if resolved_subjects else subject
            if interview_mode in {"role", "weak_topic_practice"}:
                def generate_ai_question(asked, skill_area):
                    generated = groq_client.generate_question(
                        round_type, role_name, difficulty, list(asked),
                        topic_area_context,
                        role_context=role_subject_prompt(role_name, skill_area),
                        role_skills=role_skills,
                        skill_area=skill_area,
                    )
                    # Persist the exact assigned skill so analytics and any
                    # later weak-area retest stay tied to this question's
                    # real competency rather than a broad stack label.
                    return {**generated, "subject_tag": skill_area or subject_for_question(resolved_subjects, 0)}

                question_generation_started_at = time.perf_counter()
                question_plan = groq_client.build_interview_questions(
                    role_name, difficulty, round_type, num_questions, generate_ai_question,
                    already_asked_hashes, role_skills, question_context,
                )
                timing["question_generation_seconds"] = round(
                    time.perf_counter() - question_generation_started_at, 4
                )
                for index, planned_question in enumerate(question_plan):
                    planned_question.setdefault("topic_area", "frequently asked interview question")
                    planned_question.setdefault(
                        "subject_tag", role_skills[index % len(role_skills)] if role_skills else subject_for_question(resolved_subjects, index)
                    )
                generated_question = question_plan[0]
                question_subject = generated_question.get("subject_tag") or question_subject
            else:
                generated_question = _generate_unique_question(
                    lambda context: groq_client.generate_question(
                        round_type, question_subject, difficulty,
                        asked_so_far=context, recent_topic_areas=topic_area_context,
                        role_context=role_subject_prompt(role_name, question_subject) if resolved_subjects else None,
                        role_skills=role_skills,
                    ), already_asked_hashes, list(question_context)
                )
        question = generated_question["question"]
        topic_area = generated_question.get("topic_area")
    except Exception:
        log(
            logging.ERROR,
            "initial_question_generation_failed",
            "Initial question generation failed",
            exc_info=True,
        )
        return jsonify({
            "error": "The AI interviewer is temporarily unavailable. Please try again."
        }), 503

    try:
        db_write_started_at = time.perf_counter()
        creation = db.create_or_resume_interview(
            student_id,
            round_type,
            subject,
            difficulty,
            num_questions,
            question,
            topic_area,
            interview_mode=interview_mode,
            role_name=role_name,
            resolved_subjects=resolved_subjects,
            first_subject_tag=question_subject if resolved_subjects else subject,
            question_plan=question_plan,
        )
        timing["db_write_seconds"] = round(time.perf_counter() - db_write_started_at, 4)
        log(
            logging.INFO,
            "initial_interview_db_write_completed",
            "Persisted initial interview plan",
            elapsed_seconds=timing["db_write_seconds"],
        )
    except Exception:
        log(
            logging.ERROR,
            "interview_creation_failed",
            "Atomic interview creation failed; transaction rolled back",
            exc_info=True,
        )
        return jsonify({
            "error": (
                "The interview could not be created. No partial session was "
                "saved. Please try again."
            )
        }), 500

    if not creation["student_exists"]:
        return jsonify({"error": "Student not found."}), 404
    if not creation["created"]:
        return jsonify({
            "active": True,
            "interview_id": creation["interview_id"],
            "question_order": creation["question_order"],
            **format_question_for_display(creation),
            "topic_area": creation.get("topic_area"),
            "is_followup": creation["is_followup"],
            "difficulty": creation["difficulty"],
            "round_type": creation["round_type"],
            "total_questions": creation["total_questions"],
            "real_question_index": creation["real_question_index"],
            "requested_questions": creation["total_questions"],
            "quota_adjusted": False,
            "resumed_existing": True,
            "message": "Resuming your interview already in progress.",
            **quota,
        })

    interview_id = creation["interview_id"]
    record_served_questions(
        student_id, round_type, history_scope, difficulty, interview_id,
        question_plan or [{**generated_question, "source": generated_question.get("source", "ai_generated")}],
    )
    if interview_mode == "role" and _live_web_search_enabled():
        background_schedule_started_at = time.perf_counter()
        schedule_live_question_search(
            interview_id,
            role_name,
            difficulty,
            round_type,
            min(5, num_questions // 2),
            role_skills,
            already_asked_hashes,
        )
        timing["background_schedule_seconds"] = round(
            time.perf_counter() - background_schedule_started_at, 4
        )
        log(
            logging.INFO,
            "background_live_question_search_scheduled",
            "Scheduled non-blocking live-question search after AI interview plan creation",
            interview_id=interview_id,
            role=role_name,
            elapsed_seconds=timing["background_schedule_seconds"],
        )
    elif interview_mode == "role":
        log(
            logging.INFO,
            "background_live_question_search_disabled",
            "Live web search is disabled; retaining the all-AI-generated question plan",
            interview_id=interview_id,
            role=role_name,
            enabled=False,
        )
    usage_scope.attach(interview_id, creation.get("first_detail_id"))
    set_log_context(interview_id=interview_id)
    if creation.get("orphaned_interview_id"):
        log(
            logging.WARNING,
            "questionless_interview_replaced",
            "Replaced a questionless active interview transactionally",
            old_interview_id=creation["orphaned_interview_id"],
        )

    total_seconds = round(time.perf_counter() - request_started_at, 4)
    known_seconds = sum(timing.values())
    log(
        logging.INFO,
        "start_interview_timing_summary",
        "Completed start-interview request timing breakdown",
        total_seconds=total_seconds,
        skill_inference_seconds=timing["skill_inference_seconds"],
        question_generation_seconds=timing["question_generation_seconds"],
        db_write_seconds=timing["db_write_seconds"],
        background_schedule_seconds=timing["background_schedule_seconds"],
        role_subjects_resolved_seconds=timing["role_subjects_resolved_seconds"],
        other_seconds=round(max(0.0, total_seconds - known_seconds), 4),
    )

    return jsonify({
        "interview_id": interview_id,
        "question_order": 1,
        **format_question_for_display(generated_question),
        "topic_area": topic_area,
        "total_questions": num_questions,
        "requested_questions": requested_questions,
        "quota_adjusted": num_questions < requested_questions,
        **quota,
        "difficulty": difficulty,
        "round_type": round_type,
        "interview_mode": interview_mode,
        "role_name": role_name,
        "resolved_subjects": resolved_subjects,
    })


@interviews_bp.route("/daily_usage/<int:student_id>", methods=["GET"])
def daily_usage(student_id):
    answered_count = daily_answered_count(student_id)
    return jsonify(quota_payload(answered_count))



@interviews_bp.route("/end_interview", methods=["POST"])
def end_interview():
    data = request.get_json(silent=True) or {}
    interview_id = positive_int(data.get("interview_id"), "interview_id")
    set_log_context(interview_id=interview_id)

    interview_row, _ = db.query(
        "SELECT * FROM interviews WHERE id = %s", (interview_id,), fetchone=True
    )
    if not interview_row:
        return jsonify({"error": "Interview not found."}), 404
    set_log_context(student_id=interview_row["student_id"])

    rows, _ = db.query(
        """SELECT question_order, id, question, answer, time_taken_sec, is_followup,
                  answer_audio_path, verdict, verdict_reason, ideal_answer, subject_tag,
                  timed_out
           FROM interview_details
           WHERE interview_id = %s
           ORDER BY question_order, id""",
        (interview_id,), fetch=True,
    )
    # Batch-evaluate all submitted answers once, then persist each result by
    # the database question id before building the final scorecard.
    if interview_row["status"] == "in_progress" and any(
        not row.get("is_followup") and row.get("answer") is not None and row.get("verdict") is None
        for row in rows
    ):
        # New interviews contain only main questions. Keep this filter for
        # historical interviews that already have follow-up rows.
        pending_rows = [row for row in rows if not row.get("is_followup")]
        evaluations, evaluation_error = _batch_evaluations_or_error(interview_row, interview_id, pending_rows)
        if evaluation_error:
            return jsonify({
                "error": "Interview evaluation is temporarily unavailable. Please retry shortly or contact support.",
                "retryable": True,
                "interview_id": interview_id,
            }), 503
        by_id = {int(item["question_id"]): item for item in evaluations}
        for row in pending_rows:
            item = by_id[int(row["id"])]
            db.query("UPDATE interview_details SET verdict=%s, verdict_reason=%s, ideal_answer=%s, processing_status='evaluated' WHERE id=%s", (item["verdict"], item.get("reason"), item.get("ideal_answer"), row["id"]))
        rows, _ = db.query("SELECT id, question_order, question, answer, time_taken_sec, is_followup, answer_audio_path, verdict, verdict_reason, ideal_answer, subject_tag, timed_out FROM interview_details WHERE interview_id=%s ORDER BY question_order, id", (interview_id,), fetch=True)
    scorecard, total_marks, max_marks = scoring.build_scorecard(rows)
    role_breakdown = subject_breakdown(rows) if interview_row.get("interview_mode") in {"role", "weak_topic_practice"} else None

    if interview_row["status"] == "completed":
        # Also emit the budget line when a client retries end_interview after
        # the session was already finalized (the normal completion path has
        # emitted it immediately after its commit).
        try:
            usage_rows, _ = db.query(
                """SELECT request_type, COALESCE(SUM(total_tokens), 0) AS total_tokens
                   FROM ai_usage_records WHERE interview_id = %s GROUP BY request_type""",
                (interview_id,), fetch=True,
            )
            usage_iter = usage_rows if isinstance(usage_rows, list) else []
            usage_by_type = {r["request_type"]: int(r["total_tokens"] or 0) for r in usage_iter}
            generation_tokens = sum(usage_by_type.get(k, 0) for k in ("initial_question_generation", "next_question_generation", "followup_generation"))
            evaluation_tokens = usage_by_type.get("answer_evaluation", 0) + usage_by_type.get("answer_evaluation_batch", 0)
            scorecard_tokens = usage_by_type.get("final_interview_evaluation", 0)
            transcription_tokens = usage_by_type.get("audio_transcription", 0)
            total_tokens = sum(usage_by_type.values())
            log(
                logging.INFO,
                "interview_token_usage_summary",
                f"Interview {interview_id} total tokens: {total_tokens} (generation: {generation_tokens}, evaluation: {evaluation_tokens}, scorecard: {scorecard_tokens}, transcription: {transcription_tokens})",
                total_tokens=total_tokens,
                generation_tokens=generation_tokens,
                evaluation_tokens=evaluation_tokens,
                scorecard_tokens=scorecard_tokens,
                transcription_tokens=transcription_tokens,
                web_search_tokens=usage_by_type.get("web_search", 0),
            )
        except Exception:
            log(
                logging.WARNING,
                "interview_token_usage_summary_failed",
                "Could not calculate the post-completion token usage summary",
                exc_info=True,
            )
        integrity = focus_summary(interview_id)
        return jsonify({
            "round_type": interview_row["round_type"],
            "interview_id": interview_id,
            "overall_score": interview_row["overall_score"],
            "technical_accuracy": interview_row["technical_accuracy"],
            "communication_clarity": interview_row["communication_clarity"],
            "confidence": interview_row["confidence"],
            "strengths": interview_row["strengths"],
            "weaknesses": interview_row["weaknesses"],
            "feedback": interview_row["feedback"],
            "question_results": rows,
            "scorecard": scorecard,
            "total_marks": total_marks,
            "max_marks": max_marks,
            "interview_mode": interview_row.get("interview_mode", "course"),
            "role_name": interview_row.get("role_name"),
            "subject_breakdown": role_breakdown,
            **integrity,
        })
    if interview_row["status"] != "in_progress":
        return jsonify({"error": "Only an active interview can be completed."}), 409

    progress = completion_progress(rows, interview_row["num_questions"])
    if not progress["complete"]:
        return jsonify({
            "error": (
                "This interview is not ready to complete. Answer all main "
                "questions or exit the interview instead."
            ),
            **progress,
        }), 409

    qa_pairs = [
        {
            "question": row["question"],
            "answer": row["answer"],
            "time_taken_sec": row["time_taken_sec"],
            "verdict": row["verdict"],
            "timed_out": bool(row["timed_out"]),
        }
        for row in rows
    ]
    try:
        with track_ai_usage(
            student_id=interview_row["student_id"],
            interview_id=interview_id,
            request_type="final_interview_evaluation",
        ):
            result = groq_client.evaluate_interview(
                interview_row["round_type"], interview_row["subject"],
                interview_row["difficulty"], qa_pairs,
            )
    except Exception:
        log(
            logging.ERROR,
            "final_interview_evaluation_failed",
            "Final interview evaluation failed",
            exc_info=True,
        )
        return jsonify({
            "error": "Final evaluation is temporarily unavailable. Please retry.",
            "retryable": True,
        }), 503

    avg_time = int(sum(r["time_taken_sec"] or 0 for r in rows) / max(len(rows), 1))

    if role_breakdown:
        result["strengths"] = json.dumps([
            f"Strong: {subject}" for subject in role_breakdown["strong_subjects"]
        ] or ["Continue building confidence across the role subjects."])
        result["weaknesses"] = json.dumps([
            f"Weak: {subject}" for subject in role_breakdown["weak_subjects"]
        ] or ["No weak role subjects were identified in this session."])

    integrity = finalize_open_focus_events(interview_id)

    db.query(
        """UPDATE interviews SET
             status='completed', ended_at = NOW(),
             overall_score=%s, technical_accuracy=%s, communication_clarity=%s,
             confidence=%s, avg_time_taken_sec=%s,
             strengths=%s, weaknesses=%s, feedback=%s
           WHERE id = %s""",
        (
            result["overall_score"], result["technical_accuracy"],
            result["communication_clarity"], result["confidence"], avg_time,
            result["strengths"], result["weaknesses"], result["feedback"],
            interview_id,
        ),
    )
    dashboard_cache.invalidate(interview_row["student_id"])

    # Emit a one-line token budget summary immediately after the completion
    # write.  Usage rows may be absent for calls that failed before a provider
    # response was received, so this diagnostic must never block the report.
    try:
        usage_rows, _ = db.query(
            """SELECT request_type, COALESCE(SUM(total_tokens), 0) AS total_tokens
               FROM ai_usage_records
               WHERE interview_id = %s
               GROUP BY request_type""",
            (interview_id,), fetch=True,
        )
        usage_by_type = {
            row["request_type"]: int(row["total_tokens"] or 0)
            for row in (usage_rows or [])
        }
        generation_tokens = sum(
            usage_by_type.get(kind, 0)
            for kind in (
                "initial_question_generation",
                "next_question_generation",
                "followup_generation",
            )
        )
        evaluation_tokens = usage_by_type.get("answer_evaluation", 0) + usage_by_type.get("answer_evaluation_batch", 0)
        scorecard_tokens = usage_by_type.get("final_interview_evaluation", 0)
        transcription_tokens = usage_by_type.get("audio_transcription", 0)
        total_tokens = sum(usage_by_type.values())
        log(
            logging.INFO,
            "interview_token_usage_summary",
            (
                f"Interview {interview_id} total tokens: {total_tokens} "
                f"(generation: {generation_tokens}, evaluation: {evaluation_tokens}, "
                f"scorecard: {scorecard_tokens}, transcription: {transcription_tokens})"
            ),
            total_tokens=total_tokens,
            generation_tokens=generation_tokens,
            evaluation_tokens=evaluation_tokens,
            scorecard_tokens=scorecard_tokens,
            transcription_tokens=transcription_tokens,
            web_search_tokens=usage_by_type.get("web_search", 0),
        )
    except Exception:
        log(
            logging.WARNING,
            "interview_token_usage_summary_failed",
            "Could not calculate the post-completion token usage summary",
            exc_info=True,
        )

    result["question_results"] = rows
    result["interview_id"] = interview_id
    result["round_type"] = interview_row["round_type"]
    result["interview_mode"] = interview_row.get("interview_mode", "course")
    result["role_name"] = interview_row.get("role_name")
    result["subject_breakdown"] = role_breakdown
    result["scorecard"] = scorecard
    result["total_marks"] = total_marks
    result["max_marks"] = max_marks
    result.update(integrity)
    return jsonify(result)


@interviews_bp.route("/interviews/<int:interview_id>/report-pdf", methods=["GET"])
def interview_report_pdf(interview_id):
    """Render a completed interview report as a downloadable PDF."""
    interview, _ = db.query(
        """SELECT i.*, s.name AS student_name
           FROM interviews i JOIN students s ON s.id = i.student_id
           WHERE i.id = %s""",
        (interview_id,), fetchone=True,
    )
    if not interview:
        return jsonify({"error": "Interview not found."}), 404
    if interview.get("status") != "completed" or interview.get("overall_score") is None:
        return jsonify({"error": "A PDF report is available only after interview completion."}), 400
    rows, _ = db.query(
        """SELECT question_order, question, answer, verdict, verdict_reason, ideal_answer,
                  is_followup FROM interview_details WHERE interview_id = %s
           ORDER BY question_order, id""",
        (interview_id,), fetch=True,
    )
    scorecard, total_marks, max_marks = scoring.build_scorecard(rows)
    pdf = generate_interview_report_pdf(interview, scorecard, total_marks, max_marks)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{interview.get('student_name')}_{interview.get('role_name') or interview.get('subject')}").strip("_") or "interview"
    return send_file(io.BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=f"Interview_Report_{safe}_{interview_id}.pdf")


@interviews_bp.route("/exit_interview", methods=["POST"])
def exit_interview():
    data = request.get_json(silent=True) or {}
    interview_id = positive_int(data.get("interview_id"), "interview_id")
    set_log_context(interview_id=interview_id)
    question_order = (
        positive_int(data["question_order"], "question_order")
        if data.get("question_order") is not None
        else None
    )
    answer = text(data.get("answer"), "answer", max_length=20000)
    time_taken_sec = bounded_int(
        data.get("time_taken_sec", 0), "time_taken_sec", 0, 600
    )

    interview, _ = db.query(
        "SELECT id, status FROM interviews WHERE id = %s",
        (interview_id,),
        fetchone=True,
    )
    if not interview:
        return jsonify({"error": "Interview not found."}), 404

    transition = exit_transition(interview["status"])
    if transition == "already_exited":
        return jsonify({
            "interview_id": interview_id,
            "status": "exited",
            "already_exited": True,
            "message": "This interview was already exited.",
        })
    if transition == "not_exit_eligible":
        return jsonify({
            "error": "A completed interview cannot be exited.",
            "interview_id": interview_id,
            "status": interview["status"],
        }), 409

    if question_order and answer:
        db.query(
            """UPDATE interview_details
               SET answer = %s, time_taken_sec = %s
               WHERE interview_id = %s AND question_order = %s AND answer IS NULL""",
            (answer, time_taken_sec, interview_id, question_order),
        )

    rows, _ = db.query(
        "SELECT COUNT(*) AS completed_count FROM interview_details WHERE interview_id = %s AND answer IS NOT NULL",
        (interview_id,), fetchone=True,
    )

    finalize_open_focus_events(interview_id)

    affected = db.execute_update(
        """UPDATE interviews
           SET status='exited', ended_at = NOW()
           WHERE id = %s AND status='in_progress'""",
        (interview_id,),
    )

    if affected != 1:
        latest, _ = db.query(
            "SELECT status FROM interviews WHERE id = %s",
            (interview_id,),
            fetchone=True,
        )
        return jsonify({
            "error": "The interview state changed before it could be exited.",
            "interview_id": interview_id,
            "status": latest["status"] if latest else "not_found",
        }), 409

    return jsonify({
        "interview_id": interview_id,
        "status": "exited",
        "completed_question_count": rows["completed_count"],
    })


@interviews_bp.route("/active_interview/<int:student_id>", methods=["GET"])
def active_interview(student_id):
    payload = active_interview_payload(student_id)
    if not payload:
        return jsonify({"active": False})
    if not payload["active"]:
        return jsonify({
            "active": False,
            "error": "The active interview has no recoverable question.",
        }), 409
    return jsonify(payload)


@interviews_bp.route(
    "/interviews/<int:interview_id>/focus-events", methods=["POST"]
)
def record_focus_event(interview_id):
    """Open or close one idempotent, server-timed focus-loss episode."""
    data = request.get_json(silent=True) or {}
    event_uuid = text(
        data.get("event_uuid"), "event_uuid", required=True, max_length=36
    ).lower()
    try:
        event_uuid = str(UUID(event_uuid))
    except (ValueError, AttributeError):
        raise ValidationError("event_uuid must be a valid UUID.")

    action = text(
        data.get("action"), "action", required=True, max_length=20
    ).lower()
    if action not in {"left", "returned"}:
        raise ValidationError("action must be left or returned.")
    set_log_context(interview_id=interview_id)

    if action == "left":
        source = text(
            data.get("source"), "source", required=True, max_length=20
        ).lower()
        if source not in {"visibility", "window_blur"}:
            raise ValidationError(
                "source must be visibility or window_blur."
            )
        db.query(
            """INSERT IGNORE INTO interview_focus_events
                 (event_uuid, interview_id, event_source, left_at)
               SELECT %s, id, %s, NOW(6)
               FROM interviews
               WHERE id = %s AND status = 'in_progress'""",
            (event_uuid, source, interview_id),
        )
    else:
        db.query(
            """UPDATE interview_focus_events e
               JOIN interviews i ON i.id = e.interview_id
               SET e.returned_at = NOW(6),
                   e.away_seconds = GREATEST(
                     0, TIMESTAMPDIFF(SECOND, e.left_at, NOW(6))
                   )
               WHERE e.event_uuid = %s AND e.interview_id = %s
                 AND e.returned_at IS NULL
                 AND i.status = 'in_progress'""",
            (event_uuid, interview_id),
        )

    event, _ = db.query(
        """SELECT e.id, e.returned_at, e.away_seconds, i.status
           FROM interview_focus_events e
           JOIN interviews i ON i.id = e.interview_id
           WHERE e.event_uuid = %s AND e.interview_id = %s""",
        (event_uuid, interview_id),
        fetchone=True,
    )
    if not event:
        interview, _ = db.query(
            "SELECT status FROM interviews WHERE id = %s",
            (interview_id,),
            fetchone=True,
        )
        if not interview:
            return jsonify({"error": "Interview not found."}), 404
        return jsonify({
            "error": "Focus events can only be recorded for an active interview."
        }), 409

    return jsonify({
        "interview_id": interview_id,
        "event_uuid": event_uuid,
        "event_open": event["returned_at"] is None,
        "away_seconds": event["away_seconds"],
        **focus_summary(interview_id),
    })

"""Paginated interview history and transcript routes."""

from flask import Blueprint, jsonify, request

import db
import scoring
from pagination import pagination_metadata
from policies import integrity_flagged
from services.focus_tracking import focus_summary
from validation import bounded_int


history_bp = Blueprint("history", __name__)


@history_bp.route("/history/<int:student_id>", methods=["GET"])
def history(student_id):
    page = bounded_int(request.args.get("page", 1), "page", 1, 100000)
    limit = bounded_int(request.args.get("limit", 10), "limit", 1, 50)
    offset = (page - 1) * limit
    total_row, _ = db.query(
        """SELECT COUNT(*) AS total_items
           FROM interviews
           WHERE student_id = %s AND status = 'completed'""",
        (student_id,),
        fetchone=True,
    )
    interviews, _ = db.query(
        """WITH paged_interviews AS (
             SELECT i.id,
                    s.name AS student_name,
                    s.id AS student_id,
                    i.role_name,
                    COALESCE(NULLIF(i.role_name, ''), s.target_role) AS job_role,
                    i.subject,
                    i.round_type,
                    i.difficulty,
                    i.started_at,
                    i.ended_at,
                    i.overall_score,
                    i.status
             FROM interviews i
             JOIN students s ON s.id = i.student_id
             WHERE i.student_id = %s
               AND i.status = 'completed'
             ORDER BY i.started_at DESC, i.id DESC
             LIMIT %s OFFSET %s
           ),
           detail_totals AS (
             SELECT d.interview_id, COUNT(d.id) AS total_questions
             FROM interview_details d
             JOIN paged_interviews p ON p.id = d.interview_id
             GROUP BY d.interview_id
           ),
           focus_totals AS (
             SELECT f.interview_id,
                    COUNT(*) AS focus_loss_count,
                    COALESCE(SUM(f.away_seconds), 0)
                      AS focus_loss_total_seconds
             FROM interview_focus_events f
             JOIN paged_interviews p ON p.id = f.interview_id
             GROUP BY f.interview_id
           )
           SELECT p.id,
                  p.student_name,
                  p.student_id,
                  p.job_role,
                  p.role_name,
                  p.subject,
                  p.round_type,
                  p.difficulty,
                  p.started_at,
                  p.ended_at,
                  CASE
                    WHEN p.ended_at IS NULL THEN NULL
                    ELSE TIMESTAMPDIFF(SECOND, p.started_at, p.ended_at)
                  END AS duration_seconds,
                  COALESCE(d.total_questions, 0) AS total_questions,
                  p.overall_score,
                  COALESCE(f.focus_loss_count, 0) AS focus_loss_count,
                  COALESCE(f.focus_loss_total_seconds, 0)
                    AS focus_loss_total_seconds,
                  p.status
             FROM paged_interviews p
             LEFT JOIN detail_totals d ON d.interview_id = p.id
             LEFT JOIN focus_totals f ON f.interview_id = p.id
            ORDER BY p.started_at DESC, p.id DESC""",
        (student_id, limit, offset), fetch=True,
    )
    total_items = int(total_row["total_items"] if total_row else 0)
    for interview in interviews:
        interview["focus_loss_count"] = int(
            interview.get("focus_loss_count") or 0
        )
        interview["focus_loss_total_seconds"] = int(
            interview.get("focus_loss_total_seconds") or 0
        )
        interview["integrity_flagged"] = integrity_flagged(
            interview["focus_loss_count"],
            interview["focus_loss_total_seconds"],
        )
    return jsonify({
        "items": interviews,
        "pagination": pagination_metadata(total_items, page, limit),
    })


@history_bp.route("/history/detail/<int:interview_id>", methods=["GET"])
def history_detail(interview_id):
    interview_row, _ = db.query(
        "SELECT * FROM interviews WHERE id = %s", (interview_id,), fetchone=True
    )
    if not interview_row:
        return jsonify({"error": "Interview not found."}), 404
    details, _ = db.query(
        """SELECT id, interview_id, question_order, question, is_followup,
                  answer, time_taken_sec, answer_audio_path, verdict,
                  verdict_reason, ideal_answer, timed_out, created_at
           FROM interview_details
           WHERE interview_id = %s
           ORDER BY question_order, id""",
        (interview_id,), fetch=True,
    )
    scorecard, total_marks, max_marks = scoring.build_scorecard(details)
    integrity = focus_summary(interview_id)
    return jsonify({
        "interview": interview_row,
        "qa": details,
        "scorecard": scorecard,
        "total_marks": total_marks,
        "max_marks": max_marks,
        **integrity,
    })

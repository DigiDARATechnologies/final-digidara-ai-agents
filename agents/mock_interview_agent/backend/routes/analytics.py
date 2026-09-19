"""Student-scoped AI usage and cost analytics routes."""

from datetime import date, timedelta

from flask import Blueprint, jsonify, request

import db
from pagination import pagination_metadata
from validation import ValidationError, bounded_int, positive_int


analytics_bp = Blueprint("analytics", __name__)


def _filters():
    student_id = positive_int(request.args.get("student_id"), "student_id")
    today = date.today()
    default_start = today - timedelta(days=29)
    raw_start = request.args.get("start_date")
    raw_end = request.args.get("end_date")
    try:
        start_date = date.fromisoformat(raw_start) if raw_start else default_start
        end_date = date.fromisoformat(raw_end) if raw_end else today
    except ValueError as exc:
        raise ValidationError("Dates must use YYYY-MM-DD format.") from exc
    if start_date > end_date:
        raise ValidationError("start_date cannot be after end_date.")
    if (end_date - start_date).days > 366:
        raise ValidationError("Date range cannot exceed 366 days.")
    interview_id = request.args.get("interview_id")
    return student_id, start_date, end_date, (
        positive_int(interview_id, "interview_id") if interview_id else None
    )


def _page():
    return (
        bounded_int(request.args.get("page", 1), "page", 1, 100000),
        bounded_int(request.args.get("limit", 20), "limit", 1, 100),
    )


def _usage_where(interview_id):
    if interview_id:
        return " AND u.interview_id = %s", (interview_id,)
    return "", ()


def _json_rows(rows):
    for row in rows:
        for key, value in list(row.items()):
            if hasattr(value, "isoformat"):
                row[key] = value.isoformat()
            elif key.endswith("cost") or key == "estimated_cost":
                row[key] = float(value or 0)
    return rows


def _fill_daily_date_range(rows, start_date, end_date):
    rows = _json_rows(rows)
    rows_by_date = {row["date"]: row for row in rows}
    filled = []
    current_date = start_date
    while current_date <= end_date:
        date_key = current_date.isoformat()
        if date_key in rows_by_date:
            filled.append(rows_by_date[date_key])
        else:
            filled.append({
                "date": date_key,
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": 0,
            })
        current_date += timedelta(days=1)
    return filled


@analytics_bp.route("/analytics/summary", methods=["GET"])
def summary():
    student_id, start_date, end_date, interview_id = _filters()
    extra_where, extra_params = _usage_where(interview_id)
    row, _ = db.query(
        f"""SELECT
              COUNT(u.id) AS total_requests,
              COALESCE(SUM(u.prompt_tokens), 0) AS prompt_tokens,
              COALESCE(SUM(u.completion_tokens), 0) AS completion_tokens,
              COALESCE(SUM(u.total_tokens), 0) AS total_tokens,
              COALESCE(SUM(u.estimated_cost), 0) AS estimated_cost,
              COUNT(DISTINCT u.interview_id) AS interviews_with_usage,
              (SELECT COUNT(*) FROM interviews i
               WHERE i.student_id = %s
                 AND DATE(COALESCE(i.ended_at, i.started_at)) BETWEEN %s AND %s)
                AS total_interviews
           FROM ai_usage_records u
           WHERE u.student_id = %s
             AND DATE(u.created_at) BETWEEN %s AND %s{extra_where}""",
        (student_id, start_date, end_date, student_id, start_date, end_date, *extra_params),
        fetchone=True,
    )
    today, _ = db.query(
        """SELECT COUNT(*) AS requests, COALESCE(SUM(total_tokens), 0) AS tokens,
                  COALESCE(SUM(estimated_cost), 0) AS estimated_cost,
                  COUNT(DISTINCT interview_id) AS interviews
           FROM ai_usage_records WHERE student_id = %s AND DATE(created_at) = CURDATE()""",
        (student_id,), fetchone=True,
    )
    return jsonify({"range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}, "summary": _json_rows([row or {}])[0], "today": _json_rows([today or {}])[0]})


@analytics_bp.route("/analytics/daily", methods=["GET"])
@analytics_bp.route("/analytics/cost", methods=["GET"])
def daily():
    student_id, start_date, end_date, interview_id = _filters()
    extra_where, extra_params = _usage_where(interview_id)
    rows, _ = db.query(
        f"""SELECT DATE(u.created_at) AS date, COUNT(*) AS requests,
                  COALESCE(SUM(u.prompt_tokens), 0) AS prompt_tokens,
                  COALESCE(SUM(u.completion_tokens), 0) AS completion_tokens,
                  COALESCE(SUM(u.total_tokens), 0) AS total_tokens,
                  COALESCE(SUM(u.estimated_cost), 0) AS estimated_cost
           FROM ai_usage_records u
           WHERE u.student_id = %s AND DATE(u.created_at) BETWEEN %s AND %s{extra_where}
           GROUP BY DATE(u.created_at) ORDER BY date""",
        (student_id, start_date, end_date, *extra_params), fetch=True,
    )
    return jsonify({
        "items": _fill_daily_date_range(rows, start_date, end_date),
        "range": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
    })


@analytics_bp.route("/analytics/monthly", methods=["GET"])
def monthly():
    student_id, start_date, end_date, interview_id = _filters()
    extra_where, extra_params = _usage_where(interview_id)
    rows, _ = db.query(
        f"""SELECT DATE_FORMAT(u.created_at, '%Y-%m') AS month,
                  COUNT(*) AS requests, COUNT(DISTINCT u.interview_id) AS interviews,
                  COALESCE(SUM(u.total_tokens), 0) AS total_tokens,
                  COALESCE(SUM(u.estimated_cost), 0) AS estimated_cost,
                  COALESCE(ROUND(SUM(u.total_tokens) / NULLIF(COUNT(DISTINCT u.interview_id), 0)), 0) AS average_tokens_per_interview
           FROM ai_usage_records u
           WHERE u.student_id = %s AND DATE(u.created_at) BETWEEN %s AND %s{extra_where}
           GROUP BY DATE_FORMAT(u.created_at, '%Y-%m') ORDER BY month""",
        (student_id, start_date, end_date, *extra_params), fetch=True,
    )
    return jsonify({"items": _json_rows(rows)})


@analytics_bp.route("/analytics/token-breakdown", methods=["GET"])
def token_breakdown():
    student_id, start_date, end_date, interview_id = _filters()
    extra_where, extra_params = _usage_where(interview_id)
    row, _ = db.query(
        f"""SELECT COALESCE(SUM(u.prompt_tokens), 0) AS prompt_tokens,
                  COALESCE(SUM(u.completion_tokens), 0) AS completion_tokens,
                  COALESCE(SUM(u.total_tokens), 0) AS total_tokens
           FROM ai_usage_records u WHERE u.student_id = %s
             AND DATE(u.created_at) BETWEEN %s AND %s{extra_where}""",
        (student_id, start_date, end_date, *extra_params), fetchone=True,
    )
    return jsonify(_json_rows([row or {}])[0])


def _paginated(sql, count_sql, params, page, limit):
    total, _ = db.query(count_sql, params, fetchone=True)
    rows, _ = db.query(sql + " LIMIT %s OFFSET %s", (*params, limit, (page - 1) * limit), fetch=True)
    return jsonify({"items": _json_rows(rows), "pagination": pagination_metadata(total["total_items"], page, limit)})


@analytics_bp.route("/analytics/interviews", methods=["GET"])
def interviews():
    student_id, start_date, end_date, _ = _filters()
    page, limit = _page()
    params = (student_id, start_date, end_date)
    base = """ FROM interviews i
               LEFT JOIN interview_details d ON d.interview_id = i.id
               LEFT JOIN (
                 SELECT interview_id, SUM(total_tokens) AS total_tokens,
                        SUM(estimated_cost) AS estimated_cost
                 FROM ai_usage_records GROUP BY interview_id
               ) u ON u.interview_id = i.id
               WHERE i.student_id = %s AND DATE(COALESCE(i.ended_at, i.started_at)) BETWEEN %s AND %s """
    sql = """SELECT i.id AS interview_id, i.round_type, i.subject, i.difficulty,
                    i.started_at, i.ended_at, i.avg_time_taken_sec AS duration_seconds,
                    COUNT(DISTINCT d.id) AS questions, COALESCE(MAX(u.total_tokens), 0) AS total_tokens,
                    COALESCE(MAX(u.estimated_cost), 0) AS estimated_cost """ + base + " GROUP BY i.id ORDER BY COALESCE(i.ended_at, i.started_at) DESC, i.id DESC"
    count_sql = "SELECT COUNT(*) AS total_items FROM interviews i WHERE i.student_id = %s AND DATE(COALESCE(i.ended_at, i.started_at)) BETWEEN %s AND %s"
    return _paginated(sql, count_sql, params, page, limit)


@analytics_bp.route("/analytics/questions", methods=["GET"])
def questions():
    student_id, start_date, end_date, interview_id = _filters()
    page, limit = _page()
    extra_where = " AND d.interview_id = %s" if interview_id else ""
    extra_params = (interview_id,) if interview_id else ()
    params = (student_id, start_date, end_date, *extra_params)
    base = f""" FROM interview_details d
               JOIN interviews i ON i.id = d.interview_id
               LEFT JOIN ai_usage_records u ON u.question_id = d.id
               WHERE i.student_id = %s AND DATE(COALESCE(d.answered_at, d.created_at)) BETWEEN %s AND %s{extra_where} """
    sql = """SELECT d.id AS question_id, d.interview_id, d.question_order, d.question,
                    COALESCE(SUM(u.prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(u.completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(u.total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(u.estimated_cost), 0) AS estimated_cost """ + base + " GROUP BY d.id ORDER BY d.created_at DESC, d.id DESC"
    count_sql = "SELECT COUNT(*) AS total_items FROM interview_details d JOIN interviews i ON i.id = d.interview_id WHERE i.student_id = %s AND DATE(COALESCE(d.answered_at, d.created_at)) BETWEEN %s AND %s" + extra_where
    return _paginated(sql, count_sql, params, page, limit)


@analytics_bp.route("/analytics/recent", methods=["GET"])
def recent():
    student_id, start_date, end_date, interview_id = _filters()
    page, limit = _page()
    extra_where, extra_params = _usage_where(interview_id)
    params = (student_id, start_date, end_date, *extra_params)
    base = f""" FROM ai_usage_records u
               LEFT JOIN interview_details d ON d.id = u.question_id
               WHERE u.student_id = %s AND DATE(u.created_at) BETWEEN %s AND %s{extra_where} """
    sql = """SELECT u.id, u.created_at, u.request_type, u.provider, u.model_name,
                    u.total_tokens, u.estimated_cost, u.response_time_ms, u.interview_id,
                    d.question_order, d.question """ + base + " ORDER BY u.created_at DESC, u.id DESC"
    count_sql = "SELECT COUNT(*) AS total_items " + base
    return _paginated(sql, count_sql, params, page, limit)

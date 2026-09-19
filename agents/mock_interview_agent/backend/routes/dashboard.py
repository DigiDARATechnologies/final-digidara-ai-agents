"""Dashboard aggregate route."""

import json

from flask import Blueprint, jsonify

import db
from dashboard_logic import (
    build_dashboard_payload,
    build_improvement_payload,
    build_recommendation_from_subject_averages,
)
from runtime_state import dashboard_cache


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard/<int:student_id>", methods=["GET"])
def dashboard(student_id):
    cached_payload, cache_generation = dashboard_cache.get_with_generation(
        student_id
    )
    if cached_payload is not None:
        return jsonify(cached_payload)

    summary, _ = db.query(
        """WITH completed AS (
             SELECT round_type, subject, overall_score, technical_accuracy,
                    communication_clarity, started_at, ended_at
             FROM interviews
             WHERE student_id = %s AND status = 'completed'
           ),
           subject_averages AS (
             SELECT i.round_type,
                    COALESCE(NULLIF(d.topic_area, ''), NULLIF(d.subject_tag, ''),
                             i.subject, 'HR') AS subject_label,
                    AVG(CASE d.verdict
                        WHEN 'correct' THEN 10
                        WHEN 'partial' THEN 5
                        WHEN 'wrong' THEN 0
                        ELSE NULL
                    END) AS average_score
             FROM interviews i
             JOIN interview_details d ON d.interview_id = i.id
             WHERE i.student_id = %s
               AND i.status = 'completed'
               AND d.is_followup = FALSE
               AND d.verdict IN ('correct', 'partial', 'wrong')
             GROUP BY i.round_type,
                      COALESCE(NULLIF(d.topic_area, ''), NULLIF(d.subject_tag, ''),
                               i.subject, 'HR')
           )
           SELECT COUNT(*) AS total_interviews,
                  COUNT(overall_score) AS scored_interview_count,
                  ROUND(AVG(overall_score), 1) AS average_score,
                  ROUND(MAX(overall_score), 1) AS highest_score,
                  ROUND(AVG(technical_accuracy), 1) AS technical_performance,
                  ROUND(AVG(communication_clarity), 1)
                    AS communication_performance,
                  SUM(COALESCE(ended_at, started_at) >= NOW() - INTERVAL 7 DAY)
                    AS weekly_practice_count,
                  SUM(started_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
                    AND started_at < DATE_FORMAT(
                      CURDATE() + INTERVAL 1 MONTH, '%Y-%m-01'
                    )) AS interviews_this_month,
                  (SELECT JSON_ARRAYAGG(JSON_OBJECT(
                     'round_type', round_type,
                     'subject', subject_label,
                     'average_score', average_score
                   )) FROM subject_averages) AS subject_averages
           FROM completed""",
        (student_id, student_id),
        fetchone=True,
    )
    improvement, _ = db.query(
        """WITH ranked_scores AS (
             SELECT overall_score,
                    ROW_NUMBER() OVER (
                      ORDER BY COALESCE(ended_at, started_at) DESC, id DESC
                    ) AS score_rank,
                    COUNT(*) OVER () AS scored_count
             FROM interviews
             WHERE student_id = %s
               AND status = 'completed'
               AND overall_score IS NOT NULL
           ),
           score_buckets AS (
             SELECT overall_score, score_rank, scored_count,
                    LEAST(5, GREATEST(1, FLOOR(scored_count / 2)))
                      AS recent_count
             FROM ranked_scores
           )
           SELECT COUNT(*) AS scored_count,
                  COALESCE(MAX(recent_count), 0) AS recent_count,
                   AVG(
                     CASE WHEN score_rank <= recent_count
                          THEN overall_score END
                   ) AS recent_average,
                   AVG(
                     CASE WHEN score_rank > recent_count
                          THEN overall_score END
                   ) AS earlier_average
           FROM score_buckets""",
        (student_id,),
        fetchone=True,
    )
    interviews, _ = db.query(
        """SELECT id, round_type, subject, difficulty, overall_score,
                  technical_accuracy, communication_clarity, confidence,
                  started_at, ended_at,
                  COALESCE(ended_at, started_at) AS completion_at
           FROM interviews
           WHERE student_id = %s AND status = 'completed'
           ORDER BY COALESCE(ended_at, started_at) DESC, id DESC
           LIMIT 10""",
        (student_id,),
        fetch=True,
    )
    payload = build_dashboard_payload(interviews)
    raw_subject_averages = summary.get("subject_averages") if summary else None
    if isinstance(raw_subject_averages, str):
        subject_averages = json.loads(raw_subject_averages)
    else:
        subject_averages = raw_subject_averages or []
    technical_subject_averages = {
        item["subject"]: float(item["average_score"])
        for item in subject_averages
        if item.get("round_type") == "technical"
        and item.get("average_score") is not None
    }
    weak_subjects = [
        item["subject"]
        for item in subject_averages
        if item.get("average_score") is not None
        and float(item["average_score"]) < 6
    ]
    technical_performance = (
        float(summary["technical_performance"])
        if summary and summary["technical_performance"] is not None
        else None
    )
    communication_performance = (
        float(summary["communication_performance"])
        if summary and summary["communication_performance"] is not None
        else None
    )
    recent = interviews[0] if interviews else None
    payload.update({
        "total_interviews": int(summary["total_interviews"] or 0),
        "average_score": (
            float(summary["average_score"])
            if summary and summary["average_score"] is not None
            else None
        ),
        "highest_score": (
            float(summary["highest_score"])
            if summary and summary["highest_score"] is not None
            else None
        ),
        "best_score": (
            float(summary["highest_score"])
            if summary and summary["highest_score"] is not None
            else None
        ),
        "recent_interview_score": (
            float(recent["overall_score"])
            if recent and recent["overall_score"] is not None
            else None
        ),
        "technical_performance": technical_performance,
        "communication_performance": communication_performance,
        "weekly_practice_count": int(summary["weekly_practice_count"] or 0),
        "interviews_this_month": int(summary["interviews_this_month"] or 0),
        "weak_subjects": weak_subjects,
        "recommended_next_interview": (
            build_recommendation_from_subject_averages(
                technical_subject_averages,
                technical_performance,
                communication_performance,
                recent.get("round_type") if recent else None,
            )
            if summary and int(summary["total_interviews"] or 0) > 0
            else None
        ),
        "improvement": build_improvement_payload(
            improvement.get("scored_count") if improvement else 0,
            improvement.get("recent_count") if improvement else 0,
            improvement.get("recent_average") if improvement else None,
            improvement.get("earlier_average") if improvement else None,
        ),
    })
    if recent:
        payload["recent_interview"] = {
            "id": recent["id"],
            "round_type": recent["round_type"],
            "subject": recent["subject"] or "HR",
            "difficulty": recent["difficulty"],
            "score": payload["recent_interview_score"],
            "date": recent["completion_at"].strftime("%Y-%m-%d"),
        }
    else:
        payload["recent_interview"] = None
    dashboard_cache.set_if_generation(
        student_id,
        payload,
        cache_generation,
    )
    return jsonify(payload)


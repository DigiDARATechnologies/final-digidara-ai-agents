"""Pure dashboard aggregation rules built from completed interview rows."""


RECENT_HISTORY_LIMIT = 5
TREND_LIMIT = 10
IMPROVEMENT_WINDOW = 5


def _number(value):
    return float(value) if value is not None else None


def _average(values):
    mean = _mean(values)
    return round(mean, 1) if mean is not None else None


def _mean(values):
    """Return an unrounded mean for calculations where precision matters."""
    numbers = [value for value in values if value is not None]
    return sum(numbers) / len(numbers) if numbers else None


def _date_text(value):
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def build_improvement_payload(
    scored_count,
    recent_count,
    recent_average,
    earlier_average,
):
    scored_count = int(scored_count or 0)
    recent_count = int(recent_count or 0)
    recent_average = _number(recent_average)
    earlier_average = _number(earlier_average)

    if scored_count < 2:
        return {
            "percentage": None,
            "status": "not_enough_data",
            "label": "Not enough data yet",
            "recent_count": scored_count,
        }

    if earlier_average in {None, 0}:
        return {
            "percentage": None,
            "status": "no_baseline",
            "label": "Not enough baseline data",
            "recent_count": recent_count,
        }

    percentage = round(
        ((recent_average - earlier_average) / earlier_average) * 100,
        1,
    )
    if percentage > 0:
        label = f"+{percentage:g}% improvement"
    elif percentage < 0:
        label = f"{percentage:g}% change"
    else:
        label = "No score change"
    return {
        "percentage": percentage,
        "status": "available",
        "label": label,
        "recent_count": recent_count,
        "recent_average": round(recent_average, 2),
        "earlier_average": round(earlier_average, 2),
    }


def _improvement(scored_rows):
    if len(scored_rows) < 2:
        return build_improvement_payload(
            len(scored_rows),
            len(scored_rows),
            _average([
                _number(row["overall_score"]) for row in scored_rows
            ]),
            None,
        )

    recent_count = min(IMPROVEMENT_WINDOW, max(1, len(scored_rows) // 2))
    recent_average = _mean([
        _number(row["overall_score"]) for row in scored_rows[:recent_count]
    ])
    earlier_average = _mean([
        _number(row["overall_score"]) for row in scored_rows[recent_count:]
    ])
    return build_improvement_payload(
        len(scored_rows),
        recent_count,
        recent_average,
        earlier_average,
    )


def build_recommendation_from_subject_averages(
    subject_averages,
    technical_performance,
    communication_performance,
    latest_round_type=None,
):
    """Build a recommendation from compact SQL aggregates."""
    weakest_subject = min(
        subject_averages,
        key=subject_averages.get,
        default=None,
    )

    if weakest_subject and (
        len(subject_averages) > 1 or subject_averages[weakest_subject] < 6
    ):
        return {
            "round_type": "technical",
            "subject": weakest_subject,
            "reason": (
                f"{weakest_subject} is currently your lowest-scoring technical "
                "subject, so another focused practice round should help."
            ),
        }

    if technical_performance is not None and communication_performance is not None:
        if technical_performance + 0.3 < communication_performance:
            return {
                "round_type": "technical",
                "subject": weakest_subject,
                "reason": (
                    "Technical accuracy is currently below communication performance, "
                    "so prioritize another technical round."
                ),
            }
        if communication_performance + 0.3 < technical_performance:
            return {
                "round_type": "hr",
                "subject": None,
                "reason": (
                    "Communication performance is currently your lower skill area, "
                    "so an HR round is the best next practice."
                ),
            }

    if weakest_subject:
        return {
            "round_type": "technical",
            "subject": weakest_subject,
            "reason": (
                f"Your skill scores are balanced; revisit {weakest_subject} to "
                "strengthen consistency."
            ),
        }

    if latest_round_type == "hr":
        return {
            "round_type": "technical",
            "subject": None,
            "reason": "Try a technical round next to keep your practice balanced.",
        }
    return {
        "round_type": "hr",
        "subject": None,
        "reason": "Try an HR round next to balance technical and communication practice.",
    }


def _recommendation(rows, technical_performance, communication_performance):
    scored_subjects = {}
    for row in rows:
        score = _number(row.get("overall_score"))
        subject = row.get("subject")
        if row.get("round_type") == "technical" and subject and score is not None:
            scored_subjects.setdefault(subject, []).append(score)

    subject_averages = {
        subject: _average(scores)
        for subject, scores in scored_subjects.items()
    }
    latest_round_type = rows[0].get("round_type") if rows else None
    return build_recommendation_from_subject_averages(
        subject_averages,
        technical_performance,
        communication_performance,
        latest_round_type,
    )


def build_dashboard_payload(interviews):
    """Build the complete API payload from rows ordered newest first."""
    if not interviews:
        return {
            "total_interviews": 0,
            "average_score": None,
            "highest_score": None,
            "best_score": None,
            "recent_interview_score": None,
            "technical_performance": None,
            "communication_performance": None,
            "weekly_practice_count": 0,
            "interviews_this_month": 0,
            "improvement": {
                "percentage": None,
                "status": "not_enough_data",
                "label": "Not enough data yet",
                "recent_count": 0,
            },
            "recommended_next_interview": None,
            "recent_interviews": [],
            "skill_performance_trend": [],
            "latest_interview": None,
            "score_trend": [],
            "weak_subjects": [],
        }

    scored_rows = [
        row for row in interviews if row.get("overall_score") is not None
    ]
    scores = [_number(row["overall_score"]) for row in scored_rows]
    technical_performance = _average([
        _number(row.get("technical_accuracy"))
        for row in interviews
    ])
    communication_performance = _average([
        _number(row.get("communication_clarity")) for row in interviews
    ])
    highest_score = max(scores) if scores else None
    latest = interviews[0]

    recent_interviews = []
    for row in interviews[:RECENT_HISTORY_LIMIT]:
        completion_at = row.get("completion_at") or row.get("started_at")
        recent_interviews.append({
            "id": row["id"],
            "round_type": row["round_type"],
            "subject": row.get("subject") or "HR",
            "difficulty": row["difficulty"],
            "score": _number(row.get("overall_score")),
            "date": _date_text(completion_at),
        })

    trend = []
    for row in reversed(interviews[:TREND_LIMIT]):
        completion_at = row.get("completion_at") or row.get("started_at")
        trend.append({
            "id": row["id"],
            "date": _date_text(completion_at),
            "overall_score": _number(row.get("overall_score")),
            "technical_accuracy": _number(row.get("technical_accuracy")),
            "communication_clarity": _number(
                row.get("communication_clarity")
            ),
            "confidence": _number(row.get("confidence")),
        })

    subject_scores = {}
    for row in scored_rows:
        subject = row.get("subject") or "HR"
        subject_scores.setdefault(subject, []).append(
            _number(row["overall_score"])
        )
    weak_subjects = [
        subject
        for subject, subject_values in subject_scores.items()
        if _average(subject_values) < 6
    ]

    latest_completion = latest.get("completion_at") or latest.get("started_at")
    latest_interview = {
        "id": latest["id"],
        "round_type": latest["round_type"],
        "subject": latest.get("subject") or "HR",
        "difficulty": latest["difficulty"],
        "score": _number(latest.get("overall_score")),
        "date": _date_text(latest_completion),
    }

    return {
        "total_interviews": len(interviews),
        "average_score": _average(scores),
        "highest_score": highest_score,
        "best_score": highest_score,
        "recent_interview_score": _number(latest.get("overall_score")),
        "technical_performance": technical_performance,
        "communication_performance": communication_performance,
        "weekly_practice_count": sum(
            bool(row.get("completed_last_7_days")) for row in interviews
        ),
        "interviews_this_month": sum(
            bool(row.get("started_this_month")) for row in interviews
        ),
        "improvement": _improvement(scored_rows),
        "recommended_next_interview": _recommendation(
            interviews,
            technical_performance,
            communication_performance,
        ),
        "recent_interviews": recent_interviews,
        "skill_performance_trend": trend,
        "latest_interview": latest_interview,
        "score_trend": [
            {"date": point["date"], "score": point["overall_score"]}
            for point in trend
            if point["overall_score"] is not None
        ],
        "weak_subjects": weak_subjects,
    }

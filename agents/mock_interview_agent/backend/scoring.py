"""Deterministic per-question scoring for completed interviews."""

import logging

logger = logging.getLogger(__name__)

VERDICT_MARKS = {
    "correct": 1,
    "partial": 0.5,
    "wrong": 0,
}


def build_scorecard(rows):
    """
    Score planned questions, preserving historical follow-up rows in old reports.

    A historical follow-up verdict replaces its parent verdict when present.
    Returns (scorecard, total_marks, max_marks).
    """
    scorecard = []
    i = 0

    while i < len(rows):
        row = rows[i]
        if row["is_followup"]:
            # Skip an orphan follow-up defensively.
            i += 1
            continue

        followup = None
        if i + 1 < len(rows) and rows[i + 1]["is_followup"]:
            followup = rows[i + 1]
            i += 2
        else:
            i += 1

        effective_verdict = (
            followup["verdict"]
            if followup and followup["verdict"]
            else row["verdict"]
        )
        effective_ideal_answer = (
            followup.get("ideal_answer")
            if followup and followup.get("ideal_answer")
            else row.get("ideal_answer")
        )
        marks = VERDICT_MARKS.get(effective_verdict) if effective_verdict else None
        status = (
            "timed_out" if row.get("timed_out") else
            "skipped" if row.get("processing_status") == "skipped" else
            "answered" if row.get("answer") is not None else "unanswered"
        )
        if status in {"timed_out", "skipped"}:
            marks = 0

        display_answer = (
            "Not answered (time expired)" if status == "timed_out" else
            "Skipped" if status == "skipped" else row["answer"]
        )

        scorecard.append({
            "question_number": len(scorecard) + 1,
            "question": row["question"],
            "answer": display_answer,
            "answer_audio_path": row.get("answer_audio_path"),
            "followup": ({
                "question": followup["question"],
                "answer": followup["answer"],
                "answer_audio_path": followup.get("answer_audio_path"),
                "verdict": followup["verdict"],
                "verdict_reason": followup["verdict_reason"],
            } if followup else None),
            "verdict": effective_verdict,
            "verdict_reason": (
                followup["verdict_reason"]
                if followup and followup["verdict"]
                else row["verdict_reason"]
            ),
            "ideal_answer": effective_ideal_answer,
            "marks": marks,
            "status": status,
            "timed_out": bool(row.get("timed_out")),
        })

    total_marks = sum(
        item["marks"] for item in scorecard if item["marks"] is not None
    )
    max_marks = len(scorecard)
    return scorecard, total_marks, max_marks


# How far the evaluator's 0-10 overall score may stray from the per-question
# marks. The marks are the ground truth the learner sees on the scorecard.
MARKS_TOLERANCE = 1.5


def align_scores_with_marks(result, total_marks, max_marks):
    """Keep the overall and accuracy scores consistent with the scorecard.

    The final evaluator writes its 0-10 scores without seeing the verdicts'
    arithmetic, so it can say 8/10 for an interview with one of five answers
    correct. Clamp both into a band around the marks' share out of 10.
    Communication and confidence describe delivery, not correctness, and
    are left alone.
    """
    if not max_marks:
        return result
    anchor = float(total_marks) / max_marks * 10
    low = max(0.0, anchor - MARKS_TOLERANCE)
    high = min(10.0, anchor + MARKS_TOLERANCE)
    for field in ("overall_score", "technical_accuracy"):
        value = result.get(field)
        if value is None:
            continue
        clamped = round(min(high, max(low, float(value))), 1)
        if clamped != float(value):
            logger.info(
                "Aligned %s with scorecard marks: %s -> %s (marks %s/%s)",
                field, value, clamped, total_marks, max_marks,
            )
        result[field] = clamped
    return result

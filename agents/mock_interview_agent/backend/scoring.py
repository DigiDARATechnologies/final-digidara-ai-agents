"""Deterministic per-question scoring for completed interviews."""

VERDICT_MARKS = {
    "correct": 1,
    "partial": 0.5,
    "wrong": 0,
}


def build_scorecard(rows):
    """
    Group each real question with its follow-up and score it as one item.

    When a follow-up is present, its verdict replaces the original verdict.
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

        scorecard.append({
            "question_number": len(scorecard) + 1,
            "question": row["question"],
            "answer": row["answer"],
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
        })

    total_marks = sum(
        item["marks"] for item in scorecard if item["marks"] is not None
    )
    max_marks = len(scorecard)
    return scorecard, total_marks, max_marks

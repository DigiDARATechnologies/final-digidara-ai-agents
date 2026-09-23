"""Pure business rules that can be tested without Flask or MySQL."""


INTEGRITY_EVENT_THRESHOLD = 4
INTEGRITY_AWAY_SECONDS_THRESHOLD = 60


def integrity_flagged(focus_loss_count, focus_loss_total_seconds):
    """Flag excessive focus loss without changing interview scoring."""
    return bool(
        int(focus_loss_count or 0) >= INTEGRITY_EVENT_THRESHOLD
        or int(focus_loss_total_seconds or 0)
        >= INTEGRITY_AWAY_SECONDS_THRESHOLD
    )


def counts_toward_daily_limit(*, enabled, is_followup, has_answer):
    return bool(enabled and has_answer and not is_followup)


def completion_progress(rows, required_main_questions):
    """Count evaluated main questions and decide whether completion is allowed."""
    answered_main_questions = sum(
        1
        for row in rows
        if not row["is_followup"] and row.get("verdict") is not None
    )
    return {
        "answered_main_questions": answered_main_questions,
        "required_main_questions": int(required_main_questions),
        "complete": answered_main_questions == int(required_main_questions),
    }


def exit_transition(status):
    """Classify an exit request before attempting the conditional update."""
    if status == "in_progress":
        return "exit"
    if status == "exited":
        return "already_exited"
    return "not_exit_eligible"

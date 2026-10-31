"""Phase 2 readiness skill: the learner's AI certification progress.

Score: the mean of the learner's best score in each topic they finished an
exam in (exam mode) or earned a certificate in (chat mode, which has no
`exams` row). Strengths are certified topics; gaps are topics attempted but
not yet certified.

Levels: an exam mixes beginner, intermediate and advanced questions, so each
finished exam is a session at every difficulty it asked enough questions of,
scored by the answers at that difficulty. A session at PASS_PERCENT or better
counts in full, a lower one in proportion; a level's progress is its best
LEVEL_SESSIONS sessions added up and divided by LEVEL_SESSIONS. So it grows
with every exam, a weaker exam never takes it down, and LEVEL_SESSIONS passed
ones complete the level. Professional has no questions of its own: it is the
advanced answers measured against PROFESSIONAL_PASS_PERCENT.
"""
from typing import Iterable, Optional

from cert_app.db.database import get_connection
from cert_app.services.role_periods import clean_periods, in_periods


LEVEL_SESSIONS = 5
PASS_PERCENT = 80
PROFESSIONAL_PASS_PERCENT = 90
# An exam counts at a difficulty only when it asked at least this many of its questions.
MIN_LEVEL_QUESTIONS = 3
QUESTION_LEVEL = {"beginner": "easy", "intermediate": "medium", "advanced": "hard"}


def level_scores(answers: Iterable[dict]) -> dict[str, float]:
    """answers: one row per (exam_id, difficulty) with `correct` and `asked`
    counts. Progress (0-100) at easy/medium/hard and professional."""
    percents: dict[str, list[float]] = {level: [] for level in QUESTION_LEVEL.values()}
    for row in answers:
        level = QUESTION_LEVEL.get(str(row.get("difficulty") or "").lower())
        asked = int(row.get("asked") or 0)
        if level is None or asked < MIN_LEVEL_QUESTIONS:
            continue
        percents[level].append(100.0 * float(row.get("correct") or 0) / asked)

    def progress(values, pass_percent):
        credits = sorted((min(100.0, max(0.0, value) * 100 / pass_percent) for value in values), reverse=True)
        return round(sum(credits[:LEVEL_SESSIONS]) / LEVEL_SESSIONS, 1)

    result = {level: progress(values, PASS_PERCENT) for level, values in percents.items()}
    result["professional"] = progress(percents["hard"], PROFESSIONAL_PASS_PERCENT)
    return result


def _date(value) -> Optional[str]:
    return value.date().isoformat() if hasattr(value, "date") else (value.isoformat() if hasattr(value, "isoformat") else None)


def build_student_summary(exams: Iterable[dict], certificates: Iterable[dict], answers: Iterable[dict] = ()) -> dict:
    empty = {"schema": "digidara.student_summary.v1", "score": None, "activity_count": 0,
             "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {}}
    exams, certificates = list(exams), list(certificates)
    best: dict[str, float] = {}
    times = []
    for row in exams + certificates:
        topic = str(row.get("topic") or "General")
        score = float(row.get("score_percentage") or 0)
        best[topic] = max(best.get(topic, 0.0), min(100.0, max(0.0, score)))
        when = row.get("completed_at") or row.get("issued_at")
        if when is not None:
            times.append(when)
    if not best:
        return empty
    certified = sorted({str(c.get("topic") or "General") for c in certificates})
    uncertified = sorted(topic for topic in best if topic not in certified)
    last = max(times) if times else None
    finished = {row.get("id") for row in exams}
    answers = [row for row in answers if row.get("exam_id") in finished]
    return {
        "schema": "digidara.student_summary.v1",
        "score": round(sum(best.values()) / len(best), 1),
        "activity_count": len(exams) + len(certificates),
        "last_activity_at": last.isoformat() if hasattr(last, "isoformat") else None,
        "strengths": [f"Certified: {topic}" for topic in certified[:3]],
        "gaps": [f"Not certified yet: {topic} (best {best[topic]:.0f}%)" for topic in uncertified[:3]],
        "metrics": {"certificates": len(certificates), "exams_finished": len(exams), "topics": len(best)},
        # Only exams record each answer; chat-mode certificates alone keep the score for levels.
        **({"level_scores": level_scores(answers)} if answers else {}),
        "resume": {"certifications": [
            {"name": f"{topic} Certification", "issuer": "SkillDARA AI Certification",
             "date": _date(next((c.get("issued_at") for c in certificates if str(c.get("topic") or "General") == topic), None)),
             "score": round(best[topic])}
            for topic in certified[:6]
        ]},
    }


def student_summary(email: Optional[str], periods=None) -> dict:
    """periods: the orchestrator's role periods; only exams and certificates inside them count."""
    windows = clean_periods(periods)
    if not email:
        return build_student_summary([], [])
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            return build_student_summary([], [])
        cursor.execute(
            "SELECT id, topic, score_percentage, completed_at FROM exams WHERE user_id = %s AND completed_at IS NOT NULL",
            (user["id"],),
        )
        exams = cursor.fetchall()
        cursor.execute(
            "SELECT ua.exam_id, q.difficulty, SUM(ua.score) AS correct, COUNT(*) AS asked FROM user_answers ua "
            "JOIN questions q ON q.id = ua.question_id JOIN exams e ON e.id = ua.exam_id "
            "WHERE e.user_id = %s AND e.completed_at IS NOT NULL GROUP BY ua.exam_id, q.difficulty",
            (user["id"],),
        )
        answers = cursor.fetchall()
        cursor.execute("SELECT topic, score_percentage, issued_at FROM certificates WHERE user_id = %s", (user["id"],))
        certificates = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return build_student_summary([e for e in exams if in_periods(e.get("completed_at"), windows)],
                                 [c for c in certificates if in_periods(c.get("issued_at"), windows)], answers)

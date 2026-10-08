"""Phase 2 readiness skill: the learner's AI certification progress.

Score: the mean of the learner's best score in each topic they finished an
exam in (exam mode) or earned a certificate in (chat mode, which has no
`exams` row). Strengths are certified topics; gaps are topics attempted but
not yet certified.
"""
from typing import Iterable, Optional

from cert_app.db.database import get_connection


def build_student_summary(exams: Iterable[dict], certificates: Iterable[dict]) -> dict:
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
    return {
        "schema": "digidara.student_summary.v1",
        "score": round(sum(best.values()) / len(best), 1),
        "activity_count": len(exams) + len(certificates),
        "last_activity_at": last.isoformat() if hasattr(last, "isoformat") else None,
        "strengths": [f"Certified: {topic}" for topic in certified[:3]],
        "gaps": [f"Not certified yet: {topic} (best {best[topic]:.0f}%)" for topic in uncertified[:3]],
        "metrics": {"certificates": len(certificates), "exams_finished": len(exams), "topics": len(best)},
    }


def student_summary(email: Optional[str]) -> dict:
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
            "SELECT topic, score_percentage, completed_at FROM exams WHERE user_id = %s AND completed_at IS NOT NULL",
            (user["id"],),
        )
        exams = cursor.fetchall()
        cursor.execute("SELECT topic, score_percentage, issued_at FROM certificates WHERE user_id = %s", (user["id"],))
        certificates = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return build_student_summary(exams, certificates)

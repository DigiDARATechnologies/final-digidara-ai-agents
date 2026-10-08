"""Phase 2 readiness skill: the learner's coding progress as a student summary.

Score = quality x breadth:
  quality: the learner's best score on every problem they attempted, weighted
           by difficulty (Easy 1, Medium 2, Hard 3), so hard problems count more;
  breadth: solved problems out of BREADTH_TARGET, from half credit with one
           solve to full credit at the target, so one solved problem is not
           a job-ready coding score.
"""

DIFFICULTY_WEIGHT = {"Easy": 1.0, "Medium": 2.0, "Hard": 3.0}
BREADTH_TARGET = 20


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else None


def build_student_summary(rows):
    """rows: one dict per attempted problem with difficulty, best_score,
    status, topic and updated_at (see MySqlRepository.student_problem_rows)."""
    empty = {"schema": "digidara.student_summary.v1", "score": None, "activity_count": 0,
             "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {}}
    attempted = [row for row in rows if row.get("status") in ("Attempted", "Solved")]
    if not attempted:
        return empty
    weights = [DIFFICULTY_WEIGHT.get(row.get("difficulty"), 1.0) for row in attempted]
    quality = sum(min(100, int(row.get("best_score") or 0)) * w for row, w in zip(attempted, weights)) / sum(weights)
    solved = [row for row in attempted if row.get("status") == "Solved"]
    breadth = 0.5 + 0.5 * min(1.0, len(solved) / BREADTH_TARGET) if solved else 0.5
    by_topic = {}
    for row in attempted:
        topic = by_topic.setdefault(row.get("topic") or "General", {"solved": 0, "attempted": 0})
        topic["attempted"] += 1
        topic["solved"] += row.get("status") == "Solved"
    strengths = sorted((t for t, v in by_topic.items() if v["solved"]), key=lambda t: -by_topic[t]["solved"])
    gaps = sorted((t for t, v in by_topic.items() if v["solved"] < v["attempted"]),
                  key=lambda t: by_topic[t]["solved"] - by_topic[t]["attempted"])
    last = max((row.get("updated_at") for row in attempted if row.get("updated_at")), default=None)
    solved_by_difficulty = {level: sum(1 for r in solved if r.get("difficulty") == level) for level in DIFFICULTY_WEIGHT}
    return {
        "schema": "digidara.student_summary.v1",
        "score": round(quality * breadth, 1),
        "activity_count": len(attempted),
        "last_activity_at": _iso(last),
        "strengths": [f"{t} ({by_topic[t]['solved']} solved)" for t in strengths[:3]],
        "gaps": [f"{t} ({by_topic[t]['attempted'] - by_topic[t]['solved']} unsolved)" for t in gaps[:3]],
        "metrics": {
            "problems_attempted": len(attempted),
            "problems_solved": len(solved),
            "easy_solved": solved_by_difficulty["Easy"],
            "medium_solved": solved_by_difficulty["Medium"],
            "hard_solved": solved_by_difficulty["Hard"],
        },
    }

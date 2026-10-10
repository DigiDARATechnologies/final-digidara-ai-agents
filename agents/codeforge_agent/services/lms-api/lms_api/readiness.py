"""Phase 2 readiness skill: the learner's coding progress as a student summary.

Score = quality x breadth:
  quality: the learner's best score on every problem they attempted, weighted
           by difficulty (Easy 1, Medium 2, Hard 3), so hard problems count more;
  breadth: solved problems out of BREADTH_TARGET, from half credit with one
           solve to full credit at the target, so one solved problem is not
           a job-ready coding score.

Level progress: solved problems at the learner's level (Easy for Beginner,
Medium, Hard for Hard and Professional) out of every such problem in the
technologies they practise. 50% lets them move up a level; 100% moves them
up automatically (the orchestrator's readiness service applies both).
"""

DIFFICULTY_WEIGHT = {"Easy": 1.0, "Medium": 2.0, "Hard": 3.0}
BREADTH_TARGET = 20


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else None


RESUME_MIN_SOLVED = 5


def _resume_block(solved):
    """Technologies with solved problems, and one checkable line per
    technology with enough of them, for the learner's resume."""
    by_tech = {}
    for row in solved:
        tech = row.get("technology")
        if tech:
            by_tech.setdefault(tech, {"Easy": 0, "Medium": 0, "Hard": 0})[row.get("difficulty") or "Easy"] += 1
    ranked = sorted(by_tech.items(), key=lambda item: -sum(item[1].values()))
    achievements = []
    for tech, counts in ranked:
        total = sum(counts.values())
        if total >= RESUME_MIN_SOLVED:
            split = ", ".join(f"{n} {level}" for level, n in counts.items() if n)
            achievements.append({"title": f"Solved {total} {tech} coding problems",
                                 "description": f"DigiDARA Coding Practice, tested against hidden test cases ({split})."})
    return {"skills": [tech for tech, _ in ranked], "achievements": achievements[:3]}


def _level_progress(solved, totals, difficulty):
    level = str(difficulty or "").strip().capitalize()
    total = (totals or {}).get(level, 0)
    if level not in DIFFICULTY_WEIGHT or not total:
        return None
    return round(100 * sum(1 for r in solved if r.get("difficulty") == level) / total, 1)


def build_student_summary(rows, totals=None, difficulty=None):
    """rows: one dict per attempted problem with difficulty, best_score,
    status, topic and updated_at (see MySqlRepository.student_problem_rows).
    totals: active problems per difficulty in the learner's technologies;
    difficulty: easy|medium|hard, the learner's level here."""
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
            "level_progress": _level_progress(solved, totals, difficulty),
            "level_total": (totals or {}).get(str(difficulty or "").strip().capitalize()),
        },
        "level_scores": {level.lower(): _level_progress(solved, totals, level) or 0.0 for level in DIFFICULTY_WEIGHT} if totals else None,
        "resume": _resume_block(solved),
    }

"""Phase 2 readiness skill: the learner's communication progress.

Score: the average of the learner's writing, speaking and pronunciation
scores (each the mean of their latest completed attempts, out of 100), over
whichever of the three they have practised.
"""
import json

from ..models import PronunciationAttempt, SpeakingSession, User, WritingSession
from ..utils.score_utils import to_score10
from .role_periods import clean_periods, in_periods

RECENT_SESSIONS = 5
RECENT_PRONUNCIATION = 20
LEVEL_HISTORY = 60

# Phase 2 levels, the same rule as Aptitude, Mock Interview and Certification:
# progress at a difficulty is the best LEVEL_SESSIONS sessions there, each
# counting in full at PASS_PERCENT or more and in part below it, added up and
# divided by LEVEL_SESSIONS. So LEVEL_SESSIONS good sessions complete the level
# and a weaker one never lowers it. Professional is measured on the Hard
# sessions at PROFESSIONAL_PASS_PERCENT. The orchestrator maps easy/medium/hard
# to the Beginner/Medium/Hard levels.
LEVEL_SESSIONS = 5
PASS_PERCENT = 80
PROFESSIONAL_PASS_PERCENT = 90


def _by_difficulty(sessions):
    return {difficulty: [max(0.0, min(100.0, float(score))) for level, score in sessions if level == difficulty and score is not None]
            for difficulty in ("easy", "medium", "hard")}


def _progress(scores, pass_percent):
    credits = sorted((min(100.0, score * 100 / pass_percent) for score in scores), reverse=True)
    return round(sum(credits[:LEVEL_SESSIONS]) / LEVEL_SESSIONS, 1)


def level_scores(sessions):
    """sessions: (difficulty, score 0-100) pairs."""
    scores = _by_difficulty(sessions)
    result = {difficulty: _progress(values, PASS_PERCENT) for difficulty, values in scores.items()}
    result["professional"] = _progress(scores["hard"], PROFESSIONAL_PASS_PERCENT)
    return result


def level_goals(sessions):
    """For each level, how many good sessions it needs, how many the learner
    has, and the pass mark -- shown on the Job Readiness page."""
    scores = _by_difficulty(sessions)

    def goal(values, pass_percent):
        good = sum(1 for score in values if score >= pass_percent)
        return {"needed": LEVEL_SESSIONS, "done": min(good, LEVEL_SESSIONS), "pass_percent": pass_percent, "unit": "session"}

    result = {difficulty: goal(values, PASS_PERCENT) for difficulty, values in scores.items()}
    result["professional"] = goal(scores["hard"], PROFESSIONAL_PASS_PERCENT)
    return result


def _items(raw):
    try:
        value = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return []
    return [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []


def _mean_out_of_100(rows):
    scores = [to_score10(row.overall_score) for row in rows]
    scores = [score * 10 for score in scores if score is not None]
    return round(sum(scores) / len(scores), 1) if scores else None


def student_summary(email, periods=None):
    """periods: the orchestrator's role periods; only activity inside them counts."""
    empty = {"schema": "digidara.student_summary.v1", "score": None, "activity_count": 0,
             "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {}}
    user = User.query.filter_by(email=email).first() if email else None
    if user is None:
        return empty
    periods = clean_periods(periods)
    # Without periods only the latest rows are needed; with them, filter first.
    fetch = LEVEL_HISTORY if periods else None

    def recent(query, when, limit):
        rows = query.limit(fetch or limit).all()
        return [row for row in rows if in_periods(getattr(row, when), periods)][:limit]

    writing = recent(WritingSession.query.filter(WritingSession.user_id == user.id, WritingSession.overall_score.isnot(None))
                     .order_by(WritingSession.completed_at.desc(), WritingSession.id.desc()), "completed_at", RECENT_SESSIONS)
    speaking = recent(SpeakingSession.query.filter(SpeakingSession.user_id == user.id, SpeakingSession.overall_score.isnot(None))
                      .order_by(SpeakingSession.completed_at.desc(), SpeakingSession.id.desc()), "completed_at", RECENT_SESSIONS)
    pronunciation = recent(PronunciationAttempt.query.filter(PronunciationAttempt.user_id == user.id, PronunciationAttempt.overall_score.isnot(None))
                           .order_by(PronunciationAttempt.created_at.desc()), "created_at", RECENT_PRONUNCIATION)
    parts = {"writing": _mean_out_of_100(writing), "speaking": _mean_out_of_100(speaking),
             "pronunciation": _mean_out_of_100(pronunciation)}
    practised = [score for score in parts.values() if score is not None]
    if not practised:
        return empty
    sessions = [s for s in writing + speaking if s.completed_at]
    latest = max(sessions, key=lambda s: s.completed_at) if sessions else None
    times = [s.completed_at for s in sessions] + [a.created_at for a in pronunciation if a.created_at]
    last = max(times) if times else None
    missing = [name for name, score in parts.items() if score is None]
    history = []
    for model in (WritingSession, SpeakingSession):
        history += [row for row in (model.query.filter(model.user_id == user.id, model.overall_score.isnot(None))
                    .order_by(model.completed_at.desc(), model.id.desc()).limit(LEVEL_HISTORY).all())
                    if in_periods(row.completed_at, periods)]
    history.sort(key=lambda s: (s.completed_at is not None, s.completed_at), reverse=True)
    by_level = []
    for session in history:
        score = to_score10(session.overall_score)
        by_level.append((str(session.difficulty or "").lower(), score * 10 if score is not None else None))
    return {
        "schema": "digidara.student_summary.v1",
        "score": round(sum(practised) / len(practised), 1),
        "activity_count": len(writing) + len(speaking) + len(pronunciation),
        "last_activity_at": last.isoformat() if last else None,
        "strengths": _items(latest.strengths_json)[:3] if latest else [],
        "gaps": (_items(latest.weaknesses_json)[:3] if latest else []) + [f"No {name} practice yet" for name in missing],
        "metrics": {"writing_score": parts["writing"], "speaking_score": parts["speaking"],
                    "pronunciation_score": parts["pronunciation"], "streak_days": user.streak_count or 0},
        "level_scores": level_scores(by_level),
        "level_goals": level_goals(by_level),
    }

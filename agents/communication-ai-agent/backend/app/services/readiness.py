"""Phase 2 readiness skill: the learner's communication progress.

Score: the average of the learner's writing, speaking and pronunciation
scores (each the mean of their latest completed attempts, out of 100), over
whichever of the three they have practised.
"""
import json

from ..models import PronunciationAttempt, SpeakingSession, User, WritingSession
from ..utils.score_utils import to_score10

RECENT_SESSIONS = 5
RECENT_PRONUNCIATION = 20
LEVEL_HISTORY = 60

# Phase 2 levels: progress at each difficulty, starting from 0. It is the sum
# of the latest LEVEL_SESSIONS scores (0-100) at that difficulty divided by
# LEVEL_SESSIONS, so it grows with every session and reaches 100 only after
# LEVEL_SESSIONS perfect ones. The orchestrator maps easy/medium/hard to the
# Beginner/Medium/Hard levels.
LEVEL_SESSIONS = 5


def level_scores(sessions):
    """sessions: (difficulty, score 0-100) pairs, newest first."""
    result = {}
    for difficulty in ("easy", "medium", "hard"):
        scores = [max(0.0, min(100.0, float(score))) for level, score in sessions if level == difficulty and score is not None]
        result[difficulty] = round(sum(scores[:LEVEL_SESSIONS]) / LEVEL_SESSIONS, 1)
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


def student_summary(email):
    empty = {"schema": "digidara.student_summary.v1", "score": None, "activity_count": 0,
             "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {}}
    user = User.query.filter_by(email=email).first() if email else None
    if user is None:
        return empty
    writing = (WritingSession.query.filter(WritingSession.user_id == user.id, WritingSession.overall_score.isnot(None))
               .order_by(WritingSession.completed_at.desc(), WritingSession.id.desc()).limit(RECENT_SESSIONS).all())
    speaking = (SpeakingSession.query.filter(SpeakingSession.user_id == user.id, SpeakingSession.overall_score.isnot(None))
                .order_by(SpeakingSession.completed_at.desc(), SpeakingSession.id.desc()).limit(RECENT_SESSIONS).all())
    pronunciation = (PronunciationAttempt.query.filter(PronunciationAttempt.user_id == user.id, PronunciationAttempt.overall_score.isnot(None))
                     .order_by(PronunciationAttempt.created_at.desc()).limit(RECENT_PRONUNCIATION).all())
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
        history += (model.query.filter(model.user_id == user.id, model.overall_score.isnot(None))
                    .order_by(model.completed_at.desc(), model.id.desc()).limit(LEVEL_HISTORY).all())
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
    }

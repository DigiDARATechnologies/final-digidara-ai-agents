"""Phase 2 readiness skill: get_student_summary."""
import json
from datetime import datetime

from app.extensions import db
from app.models import SpeakingSession, User, WritingSession

HEADERS = {"X-DigiDARA-User-Id": "platform-user-1"}


def _invoke(client, email="learner@example.com", headers=HEADERS):
    return client.post("/api/invoke", json={"action": "get_student_summary", "payload": {"email": email}}, headers=headers)


def _learner():
    user = User(name="Learner", email="learner@example.com", password_hash="x", streak_count=4)
    db.session.add(user)
    db.session.commit()
    return user


def test_requires_verified_identity(client):
    assert _invoke(client, headers={}).status_code == 401


def test_no_practice_has_no_score(client, app):
    _learner()
    body = _invoke(client).get_json()
    assert body["schema"] == "digidara.student_summary.v1" and body["score"] is None


def test_averages_writing_and_speaking_on_a_100_scale(client, app):
    user = _learner()
    # Writing stored out of 10, speaking out of 100: both normalised.
    db.session.add(WritingSession(user_id=user.id, mode="topic", status="completed", overall_score=8.0,
                                  completed_at=datetime(2026, 10, 2),
                                  strengths_json=json.dumps(["Clear structure"]), weaknesses_json=json.dumps(["Articles"])))
    db.session.add(SpeakingSession(user_id=user.id, mode="topic", status="completed", overall_score=60,
                                   completed_at=datetime(2026, 10, 1)))
    db.session.add(WritingSession(user_id=user.id, mode="topic", status="in_progress"))
    db.session.commit()
    body = _invoke(client).get_json()
    assert body["score"] == 70.0
    # Both at the default medium difficulty: 80% counts in full, 60% as 75% -> (100 + 75) / 5.
    assert body["level_scores"] == {"easy": 0.0, "medium": 35.0, "hard": 0.0, "professional": 0.0}
    assert body["level_goals"]["medium"] == {"needed": 5, "done": 1, "pass_percent": 80, "unit": "session"}
    assert body["metrics"]["writing_score"] == 80.0 and body["metrics"]["speaking_score"] == 60.0
    assert body["metrics"]["pronunciation_score"] is None and body["metrics"]["streak_days"] == 4
    assert body["strengths"] == ["Clear structure"]
    assert body["gaps"] == ["Articles", "No pronunciation practice yet"]
    assert body["activity_count"] == 2


def test_unknown_learner_is_empty(client, app):
    assert _invoke(client, email="nobody@example.com").get_json()["score"] is None


def test_levels_count_the_best_five_sessions_against_80_percent():
    from app.services.readiness import level_goals, level_scores
    # Five sessions at 80% complete a level; Professional is the Hard ones against 90%.
    assert level_scores([("hard", 80.0)] * 5) == {"easy": 0.0, "medium": 0.0, "hard": 100.0, "professional": 88.9}
    # A weaker session never lowers progress.
    assert level_scores([("easy", 40.0), ("easy", 80.0)])["easy"] == 30.0
    goals = level_goals([("hard", 92.0), ("hard", 85.0), ("hard", 50.0)])
    assert goals["hard"] == {"needed": 5, "done": 2, "pass_percent": 80, "unit": "session"}
    assert goals["professional"]["done"] == 1 and goals["professional"]["pass_percent"] == 90

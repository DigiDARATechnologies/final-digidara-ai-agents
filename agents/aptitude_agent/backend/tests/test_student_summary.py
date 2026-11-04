"""Phase 2 readiness skill: get_student_summary."""
import uuid
from datetime import datetime, timedelta, timezone

from backend.app.extensions import db
from backend.app.models import AptitudeTest, Student, TopicPerformance

BRIDGE_HEADERS = {"X-DigiDARA-User-ID": "platform-user-1"}


def _summary(client, email="learner@example.com", headers=BRIDGE_HEADERS):
    return client.post("/api/invoke", json={"action": "get_student_summary", "payload": {"email": email}}, headers=headers)


def test_summary_requires_verified_identity(client):
    assert _summary(client, headers={}).status_code == 401


def test_summary_for_a_learner_with_no_tests(client, auth_headers):
    body = _summary(client).get_json()
    assert body["schema"] == "digidara.student_summary.v1"
    assert body["score"] is None and body["activity_count"] == 0


def test_summary_averages_completed_tests_and_names_topics(client, auth_headers, app):
    with app.app_context():
        student = Student.query.filter_by(email="learner@example.com").one()
        now = datetime.now(timezone.utc)
        for index, percentage in enumerate((80, 60, 40)):
            db.session.add(AptitudeTest(
                id=str(uuid.uuid4()), student_id=student.id, status="completed",
                percentage=percentage, completed_at=now - timedelta(days=index),
                selected_level="Beginner" if index == 0 else None,
            ))
        db.session.add(AptitudeTest(id=str(uuid.uuid4()), student_id=student.id, status="abandoned", percentage=0))
        db.session.add(TopicPerformance(student_id=student.id, category="Quantitative", topic="Percentages", attempts=5, correct_count=5, accuracy=90))
        db.session.add(TopicPerformance(student_id=student.id, category="Logical", topic="Puzzles", attempts=4, correct_count=1, accuracy=25))
        db.session.add(TopicPerformance(student_id=student.id, category="Verbal", topic="Synonyms", attempts=1, correct_count=0, accuracy=0))
        db.session.commit()
    body = _summary(client).get_json()
    assert body["score"] == 60.0
    # Each level counts its own best five tests: one Beginner test at 80% (a pass) is a fifth of it.
    assert body["level_scores"] == {"easy": 20.0, "medium": 0.0, "hard": 0.0, "professional": 0.0}
    assert body["activity_count"] == 3
    assert body["strengths"] == ["Percentages (90%)"]
    assert body["gaps"] == ["Puzzles (25%)"]
    # Each recent test, newest first, with its date: Boss can list them for the learner.
    assert [row["score"] for row in body["recent"]] == [80.0, 60.0, 40.0]
    assert body["recent"][0]["level"] == "easy" and body["recent"][0]["date"].startswith(str(now.date()))


def test_summary_for_an_unknown_learner_is_empty(client):
    body = _summary(client, email="nobody@example.com").get_json()
    assert body["score"] is None


def test_level_progress_never_drops_and_five_passes_complete_a_level():
    from backend.app.routes.invoke import level_scores
    assert level_scores([("easy", 92.0)])["easy"] == 20.0
    # A weaker test after it does not take progress down.
    assert level_scores([("easy", 40.0), ("easy", 92.0)])["easy"] == 30.0
    assert level_scores([("easy", 85.0)] * 5 + [("easy", 30.0)])["easy"] == 100.0
    assert level_scores([("medium", 60.0)] * 5) == {"easy": 0.0, "medium": 75.0, "hard": 0.0, "professional": 0.0}
    # Professional is the Hard tests against 90%: five at 85% complete Hard but not Professional.
    hard = level_scores([("hard", 85.0)] * 5)
    assert hard["hard"] == 100.0 and hard["professional"] == 94.4
    assert level_scores([("hard", 90.0)] * 5)["professional"] == 100.0


def test_level_goals_count_good_tests_and_what_is_left():
    from backend.app.routes.invoke import level_goals
    goals = level_goals([("hard", 95.0), ("hard", 85.0), ("hard", 70.0), ("easy", 80.0)] + [("medium", 90.0)] * 7, "test")
    assert goals["hard"] == {"needed": 5, "done": 2, "pass_percent": 80, "unit": "test"}
    assert goals["professional"] == {"needed": 5, "done": 1, "pass_percent": 90, "unit": "test"}
    # Never more done than needed.
    assert goals["medium"]["done"] == 5 and goals["easy"]["done"] == 1

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
            ))
        db.session.add(AptitudeTest(id=str(uuid.uuid4()), student_id=student.id, status="abandoned", percentage=0))
        db.session.add(TopicPerformance(student_id=student.id, category="Quantitative", topic="Percentages", attempts=5, correct_count=5, accuracy=90))
        db.session.add(TopicPerformance(student_id=student.id, category="Logical", topic="Puzzles", attempts=4, correct_count=1, accuracy=25))
        db.session.add(TopicPerformance(student_id=student.id, category="Verbal", topic="Synonyms", attempts=1, correct_count=0, accuracy=0))
        db.session.commit()
    body = _summary(client).get_json()
    assert body["score"] == 60.0
    assert body["activity_count"] == 3
    assert body["strengths"] == ["Percentages (90%)"]
    assert body["gaps"] == ["Puzzles (25%)"]


def test_summary_for_an_unknown_learner_is_empty(client):
    body = _summary(client, email="nobody@example.com").get_json()
    assert body["score"] is None

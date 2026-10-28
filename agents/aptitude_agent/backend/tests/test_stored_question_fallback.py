"""A slot the model cannot write is filled with a stored, validated question
from another learner's test (never one this learner has seen)."""
import uuid

from backend.app.extensions import db
from backend.app.models import AptitudeTest, AptitudeTestQuestion, RecentQuestionHash, Student
from backend.app.services.test_question_service import stored_question_filler

SLOT = {"category": "Logical Reasoning", "topic": "Syllogism", "difficulty": "Medium"}
SEEN = "Every manager reviews reports, and Kiran is a manager. Which conclusion must hold?"
FRESH = "In a row of five chairs, Meera sits left of Ravi and right of Tara. Who sits in the middle position?"


def _register(client, email):
    response = client.post("/api/aptitude/auth/register", json={
        "name": "Other", "email": email, "password": "SecurePass123", "course": "CS", "department": "Engineering",
        "year": "Year 1", "institution": "Test Institute", "batch": "2026"})
    assert response.status_code == 201


def _stored(student_id, text, content_hash):
    test_id = str(uuid.uuid4())
    db.session.add(AptitudeTest(id=test_id, student_id=student_id, status="completed", total_questions=1, test_mode="mixed"))
    db.session.flush()
    db.session.add(AptitudeTestQuestion(
        id=str(uuid.uuid4()), test_id=test_id, sequence_no=1, category=SLOT["category"], topic=SLOT["topic"],
        difficulty=SLOT["difficulty"], question_text=text, option_a="First", option_b="Second", option_c="Third",
        option_d="Fourth", correct_answer="A", explanation="The stated rule shows that the correct option is A.",
        generation_model="test", content_hash=content_hash))


def test_a_missing_slot_gets_a_stored_question_the_learner_has_not_seen(app, client, auth_headers):
    _register(client, "other@example.com")
    with app.app_context():
        learner = Student.query.filter_by(email="learner@example.com").one()
        other = Student.query.filter_by(email="other@example.com").one()
        _stored(other.id, SEEN, "seen-hash")
        _stored(other.id, FRESH, "fresh-hash")
        own_test = str(uuid.uuid4())
        db.session.add(AptitudeTest(id=own_test, student_id=learner.id, status="completed", total_questions=1, test_mode="mixed"))
        db.session.flush()
        db.session.add(RecentQuestionHash(student_id=learner.id, test_id=own_test, category=SLOT["category"],
                                          topic=SLOT["topic"], content_hash="seen-hash"))
        db.session.commit()

        filled = stored_question_filler(learner.id)([SLOT], [])
        assert [item["question"] for item in filled] == [FRESH]
        assert filled[0]["correct_answer"] == "A" and filled[0]["content_hash"]

        # Nothing left that is unseen and not already in the test: no fill.
        assert stored_question_filler(learner.id)([SLOT], [FRESH]) is None

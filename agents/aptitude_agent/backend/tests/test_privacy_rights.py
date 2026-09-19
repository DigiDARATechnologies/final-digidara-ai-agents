from backend.app.extensions import db
from backend.app.models import AptitudeAnswer, AptitudeTest, Student


def test_privacy_endpoints_require_auth(client):
    assert client.post("/api/aptitude/me/consent", json={"version": "1.0"}).status_code == 401
    assert client.get("/api/aptitude/me/export").status_code == 401
    assert client.delete("/api/aptitude/me").status_code == 401


def test_record_consent(client, auth_headers):
    response = client.post("/api/aptitude/me/consent", headers=auth_headers, json={"version": "2.0"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["consented"] is True
    assert body["version"] == "2.0"

    profile = client.get("/api/aptitude/me", headers=auth_headers)
    assert profile.status_code == 200


def test_consent_rejects_explicit_refusal(client, auth_headers):
    response = client.post("/api/aptitude/me/consent", headers=auth_headers, json={"granted": False})
    assert response.status_code == 400
    assert response.get_json()["code"] == "consent_required"


def test_export_returns_profile_and_answers(client, auth_headers, app):
    with app.app_context():
        student = Student.query.filter_by(email="learner@example.com").first()
        test = AptitudeTest(id="test-1", student_id=student.id, status="completed", score=8, percentage=80, test_mode="mixed")
        db.session.add(test)
        db.session.flush()
        db.session.add(AptitudeAnswer(
            id="answer-1", test_id="test-1", student_id=student.id,
            question_id="question-1", correct_answer="A", is_correct=True,
            time_taken_seconds=30, evaluation_source="authoritative",
            reasoning_text="My reasoning here",
        ))
        db.session.commit()

    response = client.get("/api/aptitude/me/export", headers=auth_headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["profile"]["email"] == "learner@example.com"
    assert len(body["tests"]) == 1
    assert body["answers"][0]["reasoning_text"] == "My reasoning here"


def test_erase_anonymizes_profile_and_answers_and_revokes_token(client, auth_headers, app):
    with app.app_context():
        student = Student.query.filter_by(email="learner@example.com").first()
        test = AptitudeTest(id="test-2", student_id=student.id, status="completed", score=5, percentage=50, test_mode="mixed")
        db.session.add(test)
        db.session.flush()
        db.session.add(AptitudeAnswer(
            id="answer-2", test_id="test-2", student_id=student.id,
            question_id="question-2", correct_answer="B", is_correct=False,
            time_taken_seconds=20, evaluation_source="authoritative",
            reasoning_text="Sensitive personal reasoning",
            mistake_explanation="Careless mistake details",
        ))
        db.session.commit()
        student_id = student.id

    response = client.delete("/api/aptitude/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["id"] == student_id

    # The token used to make the request is now stale (token_version bumped).
    assert client.get("/api/aptitude/me", headers=auth_headers).status_code == 401

    with app.app_context():
        student = db.session.get(Student, student_id)
        assert student.name == "Erased User"
        assert student.email == f"erased-{student_id}@erased.invalid"
        assert student.phone is None
        assert student.password_hash is None

        answer = db.session.get(AptitudeAnswer, "answer-2")
        assert answer.reasoning_text is None
        assert answer.mistake_explanation is None

from backend.app.extensions import db
from backend.app.models import AptitudeAnswer, AptitudeTest, AptitudeTestQuestion, Student


def make_question(question_id, test_id, sequence_no=1):
    return AptitudeTestQuestion(
        id=question_id, test_id=test_id, sequence_no=sequence_no,
        category="Quantitative", topic="Percentages", difficulty="Easy",
        question_text="What is 10% of 200?",
        option_a="20", option_b="10", option_c="30", option_d="40",
        correct_answer="A", explanation="10% of 200 is 20.",
        content_hash=f"hash-{question_id}",
    )


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
        db.session.add(make_question("question-1", "test-1"))
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
        db.session.add(make_question("question-2", "test-2"))
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


BRIDGE_HEADERS = {"X-DigiDARA-User-ID": "platform-user-1"}


def _bridge(client, action, email="learner@example.com", headers=BRIDGE_HEADERS):
    return client.post("/api/invoke", json={"action": action, "payload": {"email": email}}, headers=headers)


def test_platform_bridge_requires_verified_identity(client, auth_headers):
    assert _bridge(client, "export_user_data", headers={}).status_code == 401
    assert _bridge(client, "delete_user_data", headers={}).status_code == 401


def test_platform_bridge_exports_and_erases_the_learner(client, auth_headers, app):
    exported = _bridge(client, "export_user_data")
    assert exported.status_code == 200
    assert exported.get_json()["profile"]["email"] == "learner@example.com"

    erased = _bridge(client, "delete_user_data")
    assert erased.status_code == 200
    assert erased.get_json()["status"] == "erased"
    with app.app_context():
        student = Student.query.filter_by(email="learner@example.com").first()
        assert student is None
        assert Student.query.filter(Student.email.like("erased-%@erased.invalid")).count() == 1


def test_platform_bridge_for_unknown_learner_is_not_an_error(client, app):
    exported = _bridge(client, "export_user_data", email="nobody@example.com")
    assert exported.status_code == 200 and exported.get_json() == {"profile": None}
    erased = _bridge(client, "delete_user_data", email="nobody@example.com")
    assert erased.status_code == 200 and erased.get_json() == {"status": "no_data"}


def test_platform_bridge_refuses_while_single_user_mode_is_on(client, app, monkeypatch):
    # Every request is served as one shared student in this mode, so an export or
    # erasure would act on the wrong person.
    monkeypatch.setitem(app.config, "SINGLE_USER_MODE", True)
    for action in ("export_user_data", "delete_user_data"):
        response = _bridge(client, action)
        assert response.status_code == 503
        assert response.get_json()["code"] == "single_user_mode"

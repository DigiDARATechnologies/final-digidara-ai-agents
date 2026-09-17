import importlib
import threading
import time
import uuid
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.extensions import db
from backend.app.models import (
    AIRecommendation,
    AIUsageEvent,
    AptitudeTest,
    AptitudeTestQuestion,
    BackgroundJob,
    Student,
)
from backend.app.models.base import utcnow
from backend.app.services.ai_service import AIProviderError
from backend.app.services.evaluation_service import evaluate_answer
from backend.app.services.hint_service import HintUnavailable


REMOVED_DIAGNOSTIC_FIELDS = {
    "confidence_rating",
    "confidence_calibration",
    "reasoning_text",
    "reasoning_quality",
    "reasoning_feedback",
    "reasoning_summary",
    "mistake_type",
    "mistake_explanation",
    "mistake_breakdown",
    "diagnostics_status",
    "diagnostics_error",
    "outcome_type",
}


def _assert_diagnostics_absent(payload):
    if isinstance(payload, dict):
        assert REMOVED_DIAGNOSTIC_FIELDS.isdisjoint(payload)
        for value in payload.values():
            _assert_diagnostics_absent(value)
    elif isinstance(payload, list):
        for value in payload:
            _assert_diagnostics_absent(value)


def _generated_batch(slots, prefix="batch"):
    return [
        {
            **slot,
            "question": f"{prefix} question {index} for {slot['topic']}?",
            "options": {
                "A": "Correct response",
                "B": "Second response",
                "C": "Third response",
                "D": "Fourth response",
            },
            "correct_answer": "A",
            "explanation": "The correct response is option A.",
            "content_hash": f"{prefix}-content-{index}",
            "structural_hash": f"{prefix}-structure-{index}",
        }
        for index, slot in enumerate(slots, 1)
    ]


def _install_batch_generator(monkeypatch, calls, prefix="batch"):
    def fake_generation(slots, *_args, **kwargs):
        calls.append({"slots": [dict(slot) for slot in slots], "kwargs": kwargs})
        return (
            _generated_batch(slots, prefix),
            "batch-test-model",
            {
                "input_tokens": 100,
                "output_tokens": 200,
                "total_tokens": 300,
                "provider_attempt_count": 1,
                "model": "batch-test-model",
            },
        )

    monkeypatch.setattr(
        "backend.app.services.test_question_service.generate_questions",
        fake_generation,
    )


def _recommendation(monkeypatch):
    assessment_routes = importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr(
        assessment_routes,
        "generate_recommendation",
        lambda *_args, **_kwargs: (
            "Continue practising the topics reviewed in this session.",
            "test-model",
            {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        ),
    )


def _seed_hint_attempt(app, *, total_questions=1, hints_allowed=3):
    with app.app_context():
        student = Student.query.filter_by(email="learner@example.com").one()
        test_id = str(uuid.uuid4())
        test = AptitudeTest(
            id=test_id,
            student_id=student.id,
            status="in_progress",
            current_sequence=1,
            total_questions=total_questions,
            test_mode="mixed",
            hints_allowed=hints_allowed,
            total_duration_seconds=60 * total_questions,
            assessment_started_at=utcnow(),
            expires_at=utcnow() + timedelta(seconds=60 * total_questions),
        )
        questions = []
        for sequence in range(1, total_questions + 1):
            question_id = str(uuid.uuid4())
            questions.append(AptitudeTestQuestion(
                id=question_id,
                test_id=test_id,
                sequence_no=sequence,
                category="Quantitative Aptitude",
                topic="Time & Work",
                difficulty="Easy",
                question_text=f"Workers complete task {sequence}. Which method should be used?",
                option_a="Add work rates",
                option_b="Subtract ages",
                option_c="Sort letters",
                option_d="Count vowels",
                correct_answer="A",
                explanation="Combine individual work rates.",
                question_started_at=utcnow() if sequence == 1 else None,
                generation_model="test-fixture",
                content_hash=f"hint-{question_id}",
            ))
        db.session.add_all([test, *questions])
        db.session.commit()
        return test_id, questions[0].id


def test_answer_evaluation_is_authoritative_and_local():
    question = type("Question", (), {"correct_answer": "C"})()
    assert evaluate_answer(question, "C") == (True, "authoritative")
    assert evaluate_answer(question, "A") == (False, "authoritative")


def test_category_test_is_generated_once_and_navigation_uses_only_stored_rows(
    app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, "category")
    _recommendation(monkeypatch)

    created = client.post(
        "/api/aptitude/tests",
        headers=auth_headers,
        json={
            "mode": "category_practice",
            "category": "Logical Reasoning",
            "level": "Beginner",
            "timezone": "Asia/Kolkata",
        },
    )
    assert created.status_code == 201, created.get_json()
    test_id = created.get_json()["test_id"]
    assert created.get_json()["status"] == "ready"
    assert len(calls) == 1
    assert len(calls[0]["slots"]) == 10

    with app.app_context():
        test = db.session.get(AptitudeTest, test_id)
        questions = AptitudeTestQuestion.query.filter_by(test_id=test_id).order_by(
            AptitudeTestQuestion.sequence_no
        ).all()
        assert test.status == "ready"
        assert test.timezone == "Asia/Kolkata"
        assert len(questions) == test.total_questions == 10
        assert [question.sequence_no for question in questions] == list(range(1, 11))
        assert {question.difficulty for question in questions} == {"Easy"}
        assert all(question.question_started_at is None for question in questions)

    for sequence in range(1, 11):
        question = client.get(
            f"/api/aptitude/tests/{test_id}/question", headers=auth_headers
        )
        assert question.status_code == 200, question.get_json()
        assert question.get_json()["sequence"] == sequence
        assert question.get_json()["total"] == 10
        answer = client.post(
            f"/api/aptitude/tests/{test_id}/answer",
            headers=auth_headers,
            json={"selected_answer": "A"},
        )
        assert answer.status_code == 200, answer.get_json()
        assert answer.get_json()["evaluation_source"] == "authoritative"
        assert answer.get_json()["complete"] is (sequence == 10)

    # Start, fetch, and answer never invoke generation again.
    assert len(calls) == 1
    detail = client.get(f"/api/aptitude/tests/{test_id}", headers=auth_headers)
    assert detail.status_code == 200, detail.get_json()
    assert detail.get_json()["score"] == 10
    assert detail.get_json()["total"] == 10
    assert len(detail.get_json()["questions"]) == 10
    _assert_diagnostics_absent(detail.get_json())


def test_mixed_test_batch_has_fixed_weighted_difficulties(
    app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, "mixed")
    created = client.post(
        "/api/aptitude/tests", headers=auth_headers, json={"mode": "mixed"}
    )
    assert created.status_code == 201, created.get_json()
    test_id = created.get_json()["test_id"]
    assert len(calls) == 1
    assert len(calls[0]["slots"]) == 21

    with app.app_context():
        questions = AptitudeTestQuestion.query.filter_by(test_id=test_id).all()
        assert len(questions) == 21
        assert {difficulty: sum(q.difficulty == difficulty for q in questions) for difficulty in ("Easy", "Medium", "Hard")} == {
            "Easy": 7,
            "Medium": 10,
            "Hard": 4,
        }
        original = [(q.sequence_no, q.difficulty) for q in questions]

    for sequence in range(1, 22):
        served = client.get(
            f"/api/aptitude/tests/{test_id}/question", headers=auth_headers
        )
        assert served.status_code == 200
        assert served.get_json()["sequence"] == sequence
        answered = client.post(
            f"/api/aptitude/tests/{test_id}/answer",
            headers=auth_headers,
            json={"selected_answer": "B" if sequence == 1 else "A"},
        )
        assert answered.status_code == 200
        assert answered.get_json()["complete"] is (sequence == 21)
    assert answered.get_json()["is_correct"] is True
    assert len(calls) == 1
    with app.app_context():
        assert db.session.get(AptitudeTest, test_id).status == "completed"
        current = [
            (q.sequence_no, q.difficulty)
            for q in AptitudeTestQuestion.query.filter_by(test_id=test_id).all()
        ]
        assert current == original


@pytest.mark.parametrize(
    ("level", "difficulty", "allowed_seconds"),
    [("Beginner", "Easy", 60), ("Intermediate", "Medium", 90), ("Advanced", "Hard", 120)],
)
def test_category_timer_is_persisted_from_fixed_difficulty(
    level, difficulty, allowed_seconds, app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, f"timer-{level}")
    created = client.post(
        "/api/aptitude/tests",
        headers=auth_headers,
        json={
            "mode": "category_practice",
            "category": "Logical Reasoning",
            "level": level,
        },
    )
    assert created.status_code == 201, created.get_json()
    served = client.get(
        f"/api/aptitude/tests/{created.get_json()['test_id']}/question",
        headers=auth_headers,
    )
    assert served.status_code == 200
    assert served.get_json()["difficulty"] == difficulty
    assert served.get_json()["allowed_seconds"] == allowed_seconds
    payload = served.get_json()
    assert payload["total_duration_seconds"] == 10 * allowed_seconds
    assert 0 < payload["remaining_seconds"] <= payload["total_duration_seconds"]
    assert payload["overall_remaining_seconds"] == payload["remaining_seconds"]
    assert payload["expires_at"].endswith("+00:00")


def test_unanswered_question_can_resume_without_resetting_timer(
    app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, "resume-timer")
    created = client.post(
        "/api/aptitude/tests", headers=auth_headers,
        json={"mode": "category_practice", "category": "Logical Reasoning", "level": "Beginner"},
    )
    assert created.status_code == 201, created.get_json()
    test_id = created.get_json()["test_id"]
    first = client.get(f"/api/aptitude/tests/{test_id}/question", headers=auth_headers)
    assert first.status_code == 200, first.get_json()
    first_payload = first.get_json()
    with app.app_context():
        question = AptitudeTestQuestion.query.filter_by(test_id=test_id, sequence_no=1).one()
        question.question_started_at = utcnow() - timedelta(seconds=8)
        db.session.commit()
    resumed = client.get(f"/api/aptitude/tests/{test_id}/question", headers=auth_headers)
    assert resumed.status_code == 200, resumed.get_json()
    resumed_payload = resumed.get_json()
    assert resumed_payload["id"] == first_payload["id"]
    assert resumed_payload["expires_at"] == first_payload["expires_at"]
    assert 0 < resumed_payload["remaining_seconds"] <= first_payload["remaining_seconds"]
    assert resumed_payload["total_duration_seconds"] == 600
    with app.app_context():
        test = db.session.get(AptitudeTest, test_id)
        assert test.status == "in_progress"
        assert AptitudeTestQuestion.query.filter_by(test_id=test_id).count() == 10


@pytest.mark.parametrize("mode", ["category_practice", "mixed"])
def test_exit_preserves_answers_and_blocks_resume_results_and_pdf(
    mode, app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, f"exit-{mode}")
    payload = {"mode": mode}
    if mode == "category_practice":
        payload.update(category="Logical Reasoning", level="Beginner")
    created = client.post("/api/aptitude/tests", headers=auth_headers, json=payload)
    assert created.status_code == 201, created.get_json()
    test_id = created.get_json()["test_id"]
    url = f"/api/aptitude/tests/{test_id}"
    first = client.get(f"{url}/question", headers=auth_headers)
    assert first.status_code == 200
    refreshed = client.get(f"{url}/question", headers=auth_headers)
    assert refreshed.status_code == 200
    assert refreshed.get_json()["id"] == first.get_json()["id"]
    assert refreshed.get_json()["expires_at"] == first.get_json()["expires_at"]
    answer = client.post(f"{url}/answer", headers=auth_headers, json={"selected_answer": "A"})
    assert answer.status_code == 200 and answer.get_json()["is_correct"] is True
    assert client.get(f"{url}/question", headers=auth_headers).status_code == 200
    skipped = client.post(f"{url}/skip", headers=auth_headers)
    assert skipped.status_code == 200 and skipped.get_json()["sequence"] == 3
    other = client.post(
        "/api/aptitude/auth/register",
        json={"name": "Other Learner", "email": "other@example.com", "password": "SecurePass123",
              "course": "Computer Science", "department": "Engineering", "year": "Year 1",
              "institution": "Test Institute", "batch": "2026"},
    )
    assert other.status_code == 201
    other_headers = {"Authorization": f"Bearer {other.get_json()['token']}"}
    assert client.post(f"{url}/abandon", headers=other_headers).status_code == 404
    exited = client.post(f"{url}/abandon", headers=auth_headers)
    assert exited.status_code == 200 and exited.get_json()["status"] == "abandoned"
    assert exited.get_json()["abandoned"] is True
    repeated = client.post(f"{url}/abandon", headers=auth_headers)
    assert repeated.status_code == 200 and repeated.get_json()["abandoned"] is False
    assert client.get(f"{url}/question", headers=auth_headers).status_code == 409
    assert client.post(f"{url}/answer", headers=auth_headers, json={"selected_answer": "A"}).status_code == 409
    assert client.get(url, headers=auth_headers).status_code == 409
    assert client.get(f"{url}/download", headers=auth_headers).status_code == 409
    assert all(row["id"] != test_id for row in client.get("/api/aptitude/history", headers=auth_headers).get_json()["tests"])
    with app.app_context():
        test = db.session.get(AptitudeTest, test_id)
        assert test.status == "abandoned"
        assert (test.correct_count, test.wrong_count, test.score) == (1, 0, 0)
        assert AptitudeTestQuestion.query.filter_by(test_id=test_id).count() == test.total_questions
    replacement = client.post("/api/aptitude/tests", headers=auth_headers, json=payload)
    assert replacement.status_code == 201, replacement.get_json()
    assert replacement.get_json()["test_id"] != test_id


def test_expired_and_completed_tests_cannot_be_exited(
    app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, "exit-expiry")
    created = client.post(
        "/api/aptitude/tests", headers=auth_headers,
        json={"mode": "category_practice", "category": "Logical Reasoning", "level": "Beginner"},
    )
    assert created.status_code == 201, created.get_json()
    test_id = created.get_json()["test_id"]
    url = f"/api/aptitude/tests/{test_id}"
    assert client.get(f"{url}/question", headers=auth_headers).status_code == 200
    with app.app_context():
        test = db.session.get(AptitudeTest, test_id)
        test.expires_at = utcnow() - timedelta(seconds=1)
        db.session.commit()
    expired_exit = client.post(f"{url}/abandon", headers=auth_headers)
    assert expired_exit.status_code == 409
    assert expired_exit.get_json()["code"] == "test_timed_out"
    timeout = client.post(f"{url}/answer", headers=auth_headers, json={"selected_answer": "", "timed_out": True})
    assert timeout.status_code == 200 and timeout.get_json()["complete"] is True
    completed_exit = client.post(f"{url}/abandon", headers=auth_headers)
    assert completed_exit.status_code == 409
    with app.app_context():
        assert db.session.get(AptitudeTest, test_id).status == "completed"


def test_exit_and_timeout_race_persists_only_one_final_state(
    app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, "exit-race")
    created = client.post(
        "/api/aptitude/tests", headers=auth_headers,
        json={"mode": "category_practice", "category": "Logical Reasoning", "level": "Beginner"},
    )
    assert created.status_code == 201, created.get_json()
    test_id = created.get_json()["test_id"]
    url = f"/api/aptitude/tests/{test_id}"
    assert client.get(f"{url}/question", headers=auth_headers).status_code == 200
    barrier = threading.Barrier(2)

    def send(action):
        with app.test_client() as racing_client:
            barrier.wait()
            if action == "exit":
                return racing_client.post(f"{url}/abandon", headers=auth_headers).status_code
            return racing_client.post(
                f"{url}/answer", headers=auth_headers,
                json={"selected_answer": "", "timed_out": True},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        exit_result = pool.submit(send, "exit")
        timeout_result = pool.submit(send, "timeout")
        assert sorted([exit_result.result(), timeout_result.result()]) == [200, 409]
    with app.app_context():
        test = db.session.get(AptitudeTest, test_id)
        assert test.status in {"abandoned", "completed"}
        assert (test.status == "completed") == (test.completed_at is not None)


def test_generation_provider_failure_stores_no_partial_questions(
    app, client, auth_headers, monkeypatch
):
    def unavailable(*_args, **_kwargs):
        raise AIProviderError("unavailable", "provider unavailable", transient=True)

    monkeypatch.setattr(
        "backend.app.services.test_question_service.generate_questions", unavailable
    )
    response = client.post(
        "/api/aptitude/tests", headers=auth_headers, json={"mode": "mixed"}
    )
    assert response.status_code == 503
    assert response.get_json()["code"] == "ai_unavailable"
    with app.app_context():
        test = AptitudeTest.query.one()
        assert test.status == "failed"
        assert AptitudeTestQuestion.query.filter_by(test_id=test.id).count() == 0


def test_database_failure_rolls_back_entire_question_batch(
    app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, "rollback")
    with app.app_context():
        original_flush = db.session.flush
        def fail_batch_flush(*args, **kwargs):
            if any(isinstance(row, AptitudeTestQuestion) for row in db.session.new):
                raise RuntimeError("forced batch persistence failure")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(db.session, "flush", fail_batch_flush)
        response = client.post(
            "/api/aptitude/tests", headers=auth_headers, json={"mode": "mixed"}
        )

    assert response.status_code == 503
    assert response.get_json()["code"] == "generation_failed"
    with app.app_context():
        test = AptitudeTest.query.one()
        assert test.status == "failed"
        assert AptitudeTestQuestion.query.filter_by(test_id=test.id).count() == 0


def test_partial_legacy_attempt_is_abandoned_and_requires_restart(
    app, client, auth_headers
):
    with app.app_context():
        student = Student.query.filter_by(email="learner@example.com").one()
        test = AptitudeTest(
            id=str(uuid.uuid4()),
            student_id=student.id,
            status="in_progress",
            current_sequence=1,
            total_questions=2,
            test_mode="mixed",
        )
        question = AptitudeTestQuestion(
            id=str(uuid.uuid4()),
            test_id=test.id,
            sequence_no=1,
            category="Logical Reasoning",
            topic="Series",
            difficulty="Easy",
            difficulty_reason="Legacy fixture",
            question_text="What comes next: 2, 4, 6, ?",
            option_a="7",
            option_b="8",
            option_c="9",
            option_d="10",
            correct_answer="B",
            explanation="The sequence increases by two.",
            generation_model="legacy",
            content_hash=f"legacy-{uuid.uuid4()}",
        )
        db.session.add_all([test, question])
        db.session.commit()
        test_id = test.id

    response = client.get(
        f"/api/aptitude/tests/{test_id}/question", headers=auth_headers
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "legacy_attempt_restart_required"
    with app.app_context():
        assert db.session.get(AptitudeTest, test_id).status == "abandoned"


def test_answer_without_diagnostics_preserves_results_contract(
    app, client, auth_headers, monkeypatch
):
    calls = []
    _install_batch_generator(monkeypatch, calls, "contract")
    _recommendation(monkeypatch)
    created = client.post(
        "/api/aptitude/tests",
        headers=auth_headers,
        json={
            "mode": "category_practice",
            "category": "Verbal Ability",
            "level": "Beginner",
        },
    )
    test_id = created.get_json()["test_id"]
    for _ in range(10):
        client.get(f"/api/aptitude/tests/{test_id}/question", headers=auth_headers)
        answer = client.post(
            f"/api/aptitude/tests/{test_id}/answer",
            headers=auth_headers,
            json={"selected_answer": "A"},
        )
        _assert_diagnostics_absent(answer.get_json())
    with app.app_context():
        assert BackgroundJob.query.filter_by(
            test_id=test_id, job_type="answer_diagnostics"
        ).count() == 0


def test_results_returns_final_recommendation_fallback_without_worker(
    app, client, auth_headers, monkeypatch
):
    with app.app_context():
        student = Student.query.filter_by(email="learner@example.com").one()
        test_id = str(uuid.uuid4())
        db.session.add(
            AptitudeTest(
                id=test_id,
                student_id=student.id,
                status="completed",
                current_sequence=1,
                total_questions=0,
                test_mode="mixed",
                score=0,
                percentage=0,
                completed_at=utcnow(),
            )
        )
        db.session.commit()

    assessment_routes = importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr(
        assessment_routes,
        "generate_recommendation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )
    response = client.get(f"/api/aptitude/tests/{test_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.get_json()["recommendation_status"] == "failed"
    assert "Review your incorrect answers" in response.get_json()["recommendation"]
    with app.app_context():
        saved = AIRecommendation.query.filter_by(test_id=test_id).one()
        assert saved.model_version == "deterministic-fallback"


def test_hint_returns_topic_fallback_when_provider_is_not_configured(
    app, client, auth_headers
):
    test_id, question_id = _seed_hint_attempt(app)

    response = client.post(
        f"/api/aptitude/tests/{test_id}/hint", headers=auth_headers
    )
    assert response.status_code == 200
    second = client.post(f"/api/aptitude/tests/{test_id}/hint", headers=auth_headers)
    assert second.status_code == 200
    assert second.get_json()["hint"] == response.get_json()["hint"]
    with app.app_context():
        saved_test = db.session.get(AptitudeTest, test_id)
        saved_question = db.session.get(AptitudeTestQuestion, question_id)
        assert saved_test.hints_used == 1
        assert saved_question.hint_text == response.get_json()["hint"]
        assert saved_question.hint_requested is True


def test_first_hint_calls_provider_once_and_repeat_uses_persisted_hint(
    app, client, auth_headers, monkeypatch
):
    test_id, question_id = _seed_hint_attempt(app)
    calls = []

    def generated_hint(question):
        calls.append(question.id)
        return "Compare how each method combines contributions without calculating the result.", {
            "input_tokens": 18,
            "output_tokens": 9,
            "total_tokens": 27,
            "provider_attempt_count": 1,
            "model": "hint-test-model",
        }

    assessment_routes = importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr(assessment_routes, "generate_hint", generated_hint)
    first = client.post(f"/api/aptitude/tests/{test_id}/hint", headers=auth_headers)
    second = client.post(f"/api/aptitude/tests/{test_id}/hint", headers=auth_headers)

    assert first.status_code == second.status_code == 200
    assert first.get_json()["hint"] == second.get_json()["hint"]
    assert calls == [question_id]
    assert "Add work rates" not in first.get_json()["hint"]
    with app.app_context():
        saved = db.session.get(AptitudeTestQuestion, question_id)
        assert saved.hint_text == first.get_json()["hint"]
        usage = AIUsageEvent.query.filter_by(
            test_id=test_id, question_id=question_id, operation="hint"
        ).all()
        assert len(usage) == 1
        assert usage[0].total_tokens == 27


def test_hint_limit_is_enforced_for_a_different_question(
    app, client, auth_headers, monkeypatch
):
    test_id, _question_id = _seed_hint_attempt(
        app, total_questions=2, hints_allowed=1
    )
    calls = []
    assessment_routes = importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr(
        assessment_routes,
        "generate_hint",
        lambda question: (
            calls.append(question.id) or "Compare the governing rules before selecting a method.",
            {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "provider_attempt_count": 1, "model": "hint-test-model"},
        ),
    )
    assert client.post(f"/api/aptitude/tests/{test_id}/hint", headers=auth_headers).status_code == 200
    assert client.post(
        f"/api/aptitude/tests/{test_id}/answer",
        headers=auth_headers,
        json={"selected_answer": "A"},
    ).status_code == 200
    assert client.get(f"/api/aptitude/tests/{test_id}/question", headers=auth_headers).status_code == 200
    blocked = client.post(f"/api/aptitude/tests/{test_id}/hint", headers=auth_headers)
    assert blocked.status_code == 409
    assert blocked.get_json()["code"] == "no_hints_remaining"
    assert len(calls) == 1


def test_hint_provider_failure_preserves_test_and_answer_flow(
    app, client, auth_headers, monkeypatch
):
    test_id, question_id = _seed_hint_attempt(app)
    assessment_routes = importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr(
        assessment_routes,
        "generate_hint",
        lambda _question: (_ for _ in ()).throw(HintUnavailable("unsafe hint")),
    )
    failed = client.post(f"/api/aptitude/tests/{test_id}/hint", headers=auth_headers)
    assert failed.status_code == 503
    assert failed.get_json()["code"] == "hint_unavailable"
    with app.app_context():
        test = db.session.get(AptitudeTest, test_id)
        question = db.session.get(AptitudeTestQuestion, question_id)
        assert test.status == "in_progress"
        assert test.hints_used == 0
        assert question.hint_text is None
        assert question.hint_requested is False
    answered = client.post(
        f"/api/aptitude/tests/{test_id}/answer",
        headers=auth_headers,
        json={"selected_answer": "A"},
    )
    assert answered.status_code == 200
    assert answered.get_json()["is_correct"] is True


def test_concurrent_duplicate_hint_requests_use_one_provider_call(
    app, auth_headers, monkeypatch
):
    test_id, question_id = _seed_hint_attempt(app)
    calls = []
    calls_lock = threading.Lock()
    start = threading.Barrier(2)

    def generated_hint(question):
        with calls_lock:
            calls.append(question.id)
        time.sleep(0.2)
        return "Identify the shared contribution rule before comparing the choices.", {
            "input_tokens": 4,
            "output_tokens": 3,
            "total_tokens": 7,
            "provider_attempt_count": 1,
            "model": "hint-test-model",
        }

    assessment_routes = importlib.import_module("backend.app.routes.assessment")
    monkeypatch.setattr(assessment_routes, "generate_hint", generated_hint)

    def request_hint():
        with app.test_client() as thread_client:
            start.wait(timeout=2)
            response = thread_client.post(
                f"/api/aptitude/tests/{test_id}/hint", headers=auth_headers
            )
            return response.status_code, response.get_json()["hint"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: request_hint(), range(2)))

    assert [status for status, _hint in results] == [200, 200]
    assert results[0][1] == results[1][1]
    assert calls == [question_id]
    with app.app_context():
        assert db.session.get(AptitudeTest, test_id).hints_used == 1

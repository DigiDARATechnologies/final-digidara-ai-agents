import httpx

from app.extensions import db
from app.models import SpeakingSession, SpeakingTurn
from app.routes import speaking
from app.services import groq_speaking


def test_full_speaking_turn_creates_score_and_next_question(client, auth_headers, monkeypatch):
    questions = ["What is your current career goal?", "What is one step you will take next?"]

    def fake_question(*args, **kwargs):
        return questions.pop(0)

    def fake_feedback(*args, **kwargs):
        return {
            "appreciation": "Good attempt.",
            "status": "Mostly Correct",
            "original_answer": "I want to improve my communication.",
            "corrected_answer": "I want to improve my communication.",
            "explanation": "The answer is clear.",
            "mistakes": [],
            "vocabulary_suggestions": [],
            "better_natural_answer": "I want to improve my communication skills.",
            "short_feedback": "Clear and relevant answer.",
            "scores": {
                "confidence": 80,
                "fluency": 75,
                "grammar": 85,
                "knowledge": 70,
                "overall": 78,
            },
        }

    monkeypatch.setattr(speaking.groq_service, "generate_speaking_question", fake_question)
    monkeypatch.setattr(speaking.groq_service, "evaluate_speaking_answer", fake_feedback)

    start_response = client.post(
        "/api/speaking/start",
        json={
            "mode": "topic",
            "difficulty": "medium",
            "generated_topic_id": "test-topic-1",
            "topic_title": "Career Goals",
            "topic_description": "Discuss professional goals and communication habits.",
            "conversation_length": 5,
        },
        headers=auth_headers,
    )
    assert start_response.status_code == 201
    started = start_response.get_json()
    assert started["question"] == "What is your current career goal?"

    respond_response = client.post(
        "/api/speaking/respond",
        json={
            "session_id": started["session_id"],
            "answer": "I want to improve my communication.",
            "answer_time_seconds": 42,
        },
        headers=auth_headers,
    )
    assert respond_response.status_code == 200
    payload = respond_response.get_json()
    assert payload["done"] is False
    assert payload["feedback"]["scores"]["overall"] == 7.8
    assert payload["next_question"] == "What is one step you will take next?"

    session = db.session.get(SpeakingSession, started["session_id"])
    assert session.answered_turns == 1
    assert len(session.turns) == 2
    assert session.turns[0].overall_score == 78
    assert session.turns[0].answer_time_seconds == 42


def test_normalize_feedback_preserves_mistake_points():
    feedback = groq_speaking._normalize_feedback(
        {
            "has_errors": True,
            "correction_available": True,
            "corrected_answer": "I am going to work hard.",
            "explanation": "",
            "mistake_points": ["Use the correct verb form.", "Add one clear detail."],
            "mistakes": [
                {
                    "incorrect": "I am go",
                    "correct": "I am going",
                    "type": "Verb Tense",
                    "mistake_points": ["Use the correct verb form."],
                    "explanation": "The verb needs to be in the right form.",
                }
            ],
            "scores": {"confidence": 80, "fluency": 70, "grammar": 65, "knowledge": 60, "overall": 70},
        },
        "topic",
        "I am go",
    )

    assert feedback["mistake_points"] == ["Use the correct verb form.", "Add one clear detail."]
    assert feedback["mistakes"][0]["mistake_points"] == ["Use the correct verb form."]


def test_generate_speaking_question_retries_transient_groq_failure(app, monkeypatch):
    calls = {"count": 0}

    def flaky_chat(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("temporary malformed response")
        return "What is one step you will take next?"

    monkeypatch.setattr(groq_speaking, "_chat", flaky_chat)
    monkeypatch.setattr(groq_speaking, "SPEAKING_QUESTION_BACKOFF_SECONDS", (0, 0))
    monkeypatch.setattr(groq_speaking, "_jittered_delay", lambda delay: 0)
    monkeypatch.setattr(groq_speaking.time, "sleep", lambda delay: None)

    with app.app_context():
        question = groq_speaking.generate_speaking_question(
            "topic",
            "medium",
            "Career Goals",
            2,
            [{"question": "What is your current career goal?", "answer": "I want to improve my communication."}],
            total_turns=5,
            previous_questions=["What is your current career goal?"],
            topic_description="Discuss professional goals and communication habits.",
        )

    assert question == "What is one step you will take next?"
    assert calls["count"] == 3


def test_generate_speaking_question_retries_empty_response(app, monkeypatch):
    responses = iter(["", "How can you explain that with one example?"])

    monkeypatch.setattr(groq_speaking, "_chat", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(groq_speaking, "SPEAKING_QUESTION_BACKOFF_SECONDS", (0, 0))
    monkeypatch.setattr(groq_speaking, "_jittered_delay", lambda delay: 0)
    monkeypatch.setattr(groq_speaking.time, "sleep", lambda delay: None)

    with app.app_context():
        question = groq_speaking.generate_speaking_question(
            "topic",
            "easy",
            "My Family",
            2,
            [{"question": "Do you have a big family or a small family?", "answer": "big family and done"}],
            total_turns=5,
            previous_questions=["Do you have a big family or a small family?"],
            topic_description="Talk about your family.",
        )

    assert question == "How can you explain that with one example?"


def test_generate_speaking_question_respects_retry_after_for_rate_limit(app, monkeypatch):
    calls = {"count": 0}
    delays = []
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request, headers={"Retry-After": "2.5"})

    def flaky_chat(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)
        return "What is one step you will take next?"

    monkeypatch.setattr(groq_speaking, "_chat", flaky_chat)
    monkeypatch.setattr(groq_speaking.time, "sleep", delays.append)

    with app.app_context():
        question = groq_speaking.generate_speaking_question(
            "topic",
            "medium",
            "Career Goals",
            2,
            [{"question": "What is your current career goal?", "answer": "I want to improve my communication."}],
            total_turns=5,
            previous_questions=["What is your current career goal?"],
            topic_description="Discuss professional goals and communication habits.",
        )

    assert question == "What is one step you will take next?"
    assert calls["count"] == 2
    assert delays == [2.5]


def test_generate_speaking_question_logs_connect_error_distinctly(app, monkeypatch, caplog):
    calls = {"count": 0}

    def flaky_chat(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("dns lookup failed")
        return "What is one step you will take next?"

    monkeypatch.setattr(groq_speaking, "_chat", flaky_chat)
    monkeypatch.setattr(groq_speaking, "SPEAKING_QUESTION_BACKOFF_SECONDS", (0, 0))
    monkeypatch.setattr(groq_speaking, "_jittered_delay", lambda delay: 0)
    monkeypatch.setattr(groq_speaking.time, "sleep", lambda delay: None)

    with app.app_context():
        with caplog.at_level("WARNING"):
            question = groq_speaking.generate_speaking_question(
                "topic",
                "medium",
                "Career Goals",
                2,
                [{"question": "What is your current career goal?", "answer": "I want to improve my communication."}],
                total_turns=5,
                previous_questions=["What is your current career goal?"],
                topic_description="Discuss professional goals and communication habits.",
            )

    assert question == "What is one step you will take next?"
    assert calls["count"] == 2
    assert "DNS/network error" in caplog.text


def test_generate_speaking_question_caps_long_retry_after_and_stops_quickly(app, monkeypatch):
    calls = {"count": 0}
    delays = []
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request, headers={"Retry-After": "30"})

    def rate_limited_chat(*args, **kwargs):
        calls["count"] += 1
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)

    monkeypatch.setattr(groq_speaking, "_chat", rate_limited_chat)
    monkeypatch.setattr(groq_speaking.time, "sleep", delays.append)

    with app.app_context():
        try:
            groq_speaking.generate_speaking_question(
                "topic",
                "medium",
                "Career Goals",
                2,
                [{"question": "What is your current career goal?", "answer": "I want to improve my communication."}],
                total_turns=5,
                previous_questions=["What is your current career goal?"],
                topic_description="Discuss professional goals and communication habits.",
            )
        except groq_speaking.GroqRateLimitError:
            pass
        else:
            raise AssertionError("Expected GroqRateLimitError")

    assert calls["count"] == 3
    assert delays == [3.0, 3.0]


def test_generate_speaking_question_does_not_retry_configuration_error(app, monkeypatch):
    calls = {"count": 0}

    def missing_key(*args, **kwargs):
        calls["count"] += 1
        raise RuntimeError("GROQ_API_KEY is not set in backend/.env")

    monkeypatch.setattr(groq_speaking, "_chat", missing_key)
    monkeypatch.setattr(groq_speaking, "SPEAKING_QUESTION_BACKOFF_SECONDS", (0, 0))

    with app.app_context():
        try:
            groq_speaking.generate_speaking_question(
                "topic",
                "easy",
                "My Family",
                1,
                [],
                total_turns=5,
                previous_questions=[],
                topic_description="Talk about your family.",
            )
        except RuntimeError as exc:
            assert "GROQ_API_KEY" in str(exc)
        else:
            raise AssertionError("Expected configuration RuntimeError")

    assert calls["count"] == 1


def test_speaking_start_distinguishes_configuration_error(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        speaking.groq_service,
        "generate_speaking_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("GROQ_API_KEY is not set in backend/.env")),
    )

    response = client.post(
        "/api/speaking/start",
        json={
            "mode": "topic",
            "difficulty": "easy",
            "generated_topic_id": "test-topic-config",
            "topic_title": "My Family",
            "topic_description": "Talk about your family.",
            "conversation_length": 5,
        },
        headers=auth_headers,
    )

    assert response.status_code == 503
    assert response.get_json()["error_code"] == "GROQ_CONFIG_ERROR"
    assert response.get_json()["message"] == "AI setup issue - please contact support."


def test_speaking_start_uses_fallback_first_question_after_rate_limit(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        speaking.groq_service,
        "generate_speaking_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(speaking.groq_service.GroqRateLimitError("rate limit exhausted")),
    )

    response = client.post(
        "/api/speaking/start",
        json={
            "mode": "topic",
            "difficulty": "easy",
            "generated_topic_id": "test-topic-start-rate-limit",
            "topic_title": "My Family",
            "topic_description": "Talk about your family.",
            "conversation_length": 5,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["question_source"] == "fallback"
    assert payload["question"]


def test_speaking_evaluation_does_not_use_long_rate_limit_retry(app, monkeypatch):
    kwargs_seen = {}

    def fail_chat(*args, **kwargs):
        kwargs_seen.update(kwargs)
        raise httpx.HTTPStatusError(
            "rate limited",
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
            response=httpx.Response(429),
        )

    monkeypatch.setattr(groq_speaking, "_chat", fail_chat)

    with app.app_context():
        feedback = groq_speaking.evaluate_speaking_answer(
            "topic",
            "easy",
            "My Family",
            "Do you have a big family or a small family?",
            "I have a small family.",
        )

    assert kwargs_seen["retry_rate_limit"] is False
    assert kwargs_seen["timeout"] == 12
    assert feedback["short_feedback"] == "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved."
    assert feedback["correction_available"] is False
    assert feedback["fallback_reason"] == "rate_limited"


def test_speaking_respond_uses_fallback_next_question_after_rate_limit(client, auth_headers, monkeypatch):
    def fake_first_question(*args, **kwargs):
        return "What is your current career goal?"

    def fake_feedback(*args, **kwargs):
        return {
            "appreciation": "Good attempt.",
            "status": "Mostly Correct",
            "original_answer": "I want to improve my communication.",
            "corrected_answer": "I want to improve my communication.",
            "explanation": "The answer is clear.",
            "mistakes": [],
            "vocabulary_suggestions": [],
            "better_natural_answer": "I want to improve my communication skills.",
            "short_feedback": "Clear and relevant answer.",
            "scores": {
                "confidence": 80,
                "fluency": 75,
                "grammar": 85,
                "knowledge": 70,
                "overall": 78,
            },
        }

    monkeypatch.setattr(speaking.groq_service, "generate_speaking_question", fake_first_question)
    monkeypatch.setattr(speaking.groq_service, "evaluate_speaking_answer", fake_feedback)

    start_response = client.post(
        "/api/speaking/start",
        json={
            "mode": "topic",
            "difficulty": "medium",
            "generated_topic_id": "test-topic-rate-limit",
            "topic_title": "Career Goals",
            "topic_description": "Discuss professional goals and communication habits.",
            "conversation_length": 5,
        },
        headers=auth_headers,
    )
    assert start_response.status_code == 201
    started = start_response.get_json()

    monkeypatch.setattr(
        speaking.groq_service,
        "generate_speaking_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(speaking.groq_service.GroqRateLimitError("rate limit exhausted")),
    )

    respond_response = client.post(
        "/api/speaking/respond",
        json={
            "session_id": started["session_id"],
            "answer": "I want to improve my communication.",
            "answer_time_seconds": 42,
        },
        headers=auth_headers,
    )

    assert respond_response.status_code == 200
    payload = respond_response.get_json()
    assert payload["done"] is False
    assert payload["next_question_source"] == "fallback"
    assert payload["next_question"]

    session = db.session.get(SpeakingSession, started["session_id"])
    assert session.answered_turns == 1
    assert len(session.turns) == 2


def test_speaking_start_uses_fallback_question_after_transient_generation_error(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        speaking.groq_service,
        "generate_speaking_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("temporary malformed response")),
    )

    response = client.post(
        "/api/speaking/start",
        json={
            "mode": "topic",
            "difficulty": "easy",
            "generated_topic_id": "test-topic-transient",
            "topic_title": "My Family",
            "topic_description": "Talk about your family.",
            "conversation_length": 5,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["question_source"] == "fallback"
    assert payload["question"]


def test_speaking_start_uses_fallback_question_after_groq_404(client, auth_headers, monkeypatch):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response_404 = httpx.Response(404, request=request)

    monkeypatch.setattr(
        speaking.groq_service,
        "generate_speaking_question",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            httpx.HTTPStatusError("not found", request=request, response=response_404)
        ),
    )

    response = client.post(
        "/api/speaking/start",
        json={
            "mode": "topic",
            "difficulty": "easy",
            "generated_topic_id": "test-topic-groq-404",
            "topic_title": "My Family",
            "topic_description": "Talk about your family.",
            "conversation_length": 5,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["question_source"] == "fallback"
    assert payload["question"]


def test_retry_correction_updates_existing_turn_without_duplicate_question(client, auth_headers, monkeypatch):
    questions = ["What did you do this morning?", "What else did you do?"]

    monkeypatch.setattr(speaking.groq_service, "generate_speaking_question", lambda *args, **kwargs: questions.pop(0))
    monkeypatch.setattr(
        speaking.groq_service,
        "evaluate_speaking_answer",
        lambda *args, **kwargs: {
            "appreciation": "Correction unavailable",
            "status": "Needs Review",
            "original_answer": "In this morning I am bring some coffee.",
            "has_errors": None,
            "transcript_clear": None,
            "unclear_phrases": [],
            "correction_available": False,
            "corrected_answer": None,
            "better_natural_answer": None,
            "explanation": "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved.",
            "mistakes": [],
            "vocabulary_suggestions": [],
            "rules_applied": [],
            "short_feedback": "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved.",
            "source": "fallback",
            "feedback_source": "fallback",
            "fallback_reason": "rate_limited",
            "scores_verified": False,
            "scores": {"confidence": None, "fluency": None, "grammar": None, "knowledge": None, "overall": None},
        },
    )

    start_response = client.post(
        "/api/speaking/start",
        json={
            "mode": "topic",
            "difficulty": "easy",
            "generated_topic_id": "retry-correction-topic",
            "topic_title": "Morning Routine",
            "topic_description": "Talk about this morning.",
            "conversation_length": 5,
        },
        headers=auth_headers,
    )
    started = start_response.get_json()

    respond_response = client.post(
        "/api/speaking/respond",
        json={"session_id": started["session_id"], "answer": "In this morning I am bring some coffee."},
        headers=auth_headers,
    )
    payload = respond_response.get_json()
    turn_id = payload["feedback_turn_id"]
    before_count = SpeakingTurn.query.filter_by(session_id=started["session_id"]).count()

    monkeypatch.setattr(
        speaking.groq_service,
        "repair_speaking_correction",
        lambda *args, **kwargs: {
            "appreciation": "Good repair.",
            "status": "Needs Improvement",
            "original_answer": "In this morning I am bring some coffee.",
            "has_errors": True,
            "transcript_clear": True,
            "unclear_phrases": [],
            "correction_available": True,
            "corrected_answer": "This morning, I brought some coffee.",
            "better_natural_answer": "I brought some coffee this morning.",
            "explanation": "Use 'this morning' and past tense.",
            "mistakes": [{"incorrect": "I am bring", "correct": "I brought", "type": "Verb Form", "explanation": "Use past tense."}],
            "vocabulary_suggestions": [],
            "rules_applied": [],
            "short_feedback": "Good repair.",
            "source": "groq",
            "feedback_source": "groq",
            "fallback_reason": None,
            "scores_verified": True,
            "scores": {"confidence": 70, "fluency": 65, "grammar": 55, "knowledge": 60, "overall": 63},
        },
    )

    retry_response = client.post(
        f"/api/speaking/turns/{turn_id}/retry-correction",
        json={"session_id": started["session_id"]},
        headers=auth_headers,
    )

    assert retry_response.status_code == 200
    assert retry_response.get_json()["updated"] is True
    assert SpeakingTurn.query.filter_by(session_id=started["session_id"]).count() == before_count
    turn = db.session.get(SpeakingTurn, turn_id)
    assert turn.corrected_answer == "This morning, I brought some coffee."

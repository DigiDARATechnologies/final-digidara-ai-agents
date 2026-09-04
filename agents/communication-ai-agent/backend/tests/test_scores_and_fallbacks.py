import httpx

from app.routes import practice
from app.services import groq_common, groq_service, groq_speaking
from app.services.speaking_local_rules import apply_local_speaking_correction


def test_score_average_ignores_none_values():
    assert groq_common._score_average([80, None, 70, 90]) == 80.0
    assert groq_common._score_average([None, None]) is None


def test_speaking_feedback_falls_back_when_groq_fails(monkeypatch):
    def fail_chat(*args, **kwargs):
        raise RuntimeError("Groq unavailable")

    monkeypatch.setattr(groq_speaking, "_chat", fail_chat)

    feedback = groq_speaking.evaluate_speaking_answer(
        mode="topic",
        difficulty="medium",
        topic_title="Communication",
        question="Why is communication important?",
        answer="It helps people understand each other.",
    )

    assert feedback["short_feedback"] == "Detailed grammar correction is temporarily unavailable. Your original answer has been preserved."
    assert feedback["scores"]["overall"] is None
    assert feedback["scores"]["knowledge"] is None
    assert feedback["correction_available"] is False
    assert feedback["source"] == "fallback"
    assert feedback["corrected_answer"] is None


def test_speaking_feedback_prompt_requires_faithful_grammar_correction(monkeypatch):
    prompts = {}

    def fake_chat(system_prompt, user_prompt, **kwargs):
        prompts["system"] = system_prompt
        prompts["user"] = user_prompt
        return """
        {
          "appreciation": "Good attempt.",
          "status": "Needs Improvement",
          "original_answer": "in this morning I am bring some I'm copy and I am them done",
          "corrected_answer": "This morning, I brought some copies, and I have done them.",
          "explanation": "Use 'this morning' without 'in', past tense 'brought', and the plural noun 'copies'.",
          "mistakes": [
            {
              "incorrect": "in this morning",
              "correct": "this morning",
              "type": "Preposition",
              "explanation": "Do not use 'in' before 'this morning'."
            }
          ],
          "vocabulary_suggestions": [],
          "better_natural_answer": "This morning, I brought some copies and finished them.",
          "short_feedback": "Good try. Fix the time phrase, verb tense, and noun form.",
          "scores": {"confidence": 45, "fluency": 35, "grammar": 25, "knowledge": 50, "overall": 39}
        }
        """

    monkeypatch.setattr(groq_speaking, "_chat", fake_chat)

    feedback = groq_speaking.evaluate_speaking_answer(
        mode="topic",
        difficulty="easy",
        topic_title="Morning Routine",
        question="What did you do this morning?",
        answer="in this morning I am bring some I'm copy and I am them done",
    )

    assert "correct every clear grammar" in prompts["system"]
    assert "Do not invent personal facts" in prompts["system"]
    assert "possibly misrecognized speech" in prompts["system"]
    assert "corrected_answer different from the incorrect transcript" in prompts["user"]
    assert feedback["corrected_answer"] == "This morning, I brought some copies, and I have done them."
    assert feedback["scores"]["grammar"] == 25


def test_speaking_feedback_accepts_already_correct_answer(monkeypatch):
    monkeypatch.setattr(
        groq_speaking,
        "_chat",
        lambda *args, **kwargs: """
        {
          "appreciation": "Nice sentence.",
          "status": "Correct",
          "original_answer": "This morning, I made some coffee.",
          "has_errors": false,
          "correction_available": true,
          "source": "groq",
          "fallback_reason": null,
          "corrected_answer": null,
          "explanation": "No grammatical correction was needed.",
          "mistakes": [],
          "vocabulary_suggestions": [],
          "better_natural_answer": null,
          "short_feedback": "No grammatical correction was needed.",
          "scores": {"confidence": 90, "fluency": 90, "grammar": 95, "knowledge": 80, "overall": 89}
        }
        """,
    )

    feedback = groq_speaking.evaluate_speaking_answer(
        "topic",
        "easy",
        "Morning Routine",
        "What did you do this morning?",
        "This morning, I made some coffee.",
    )

    assert feedback["has_errors"] is False
    assert feedback["correction_available"] is True
    assert feedback["corrected_answer"] is None
    assert feedback["mistakes"] == []


def test_speaking_feedback_rejects_missing_corrected_answer(monkeypatch):
    calls = {"count": 0}

    def fake_chat(*args, **kwargs):
        calls["count"] += 1
        return """
        {
          "appreciation": "Good attempt.",
          "status": "Needs Improvement",
          "has_errors": true,
          "correction_available": true,
          "source": "groq",
          "corrected_answer": "",
          "explanation": "There is a grammar mistake.",
          "mistakes": [{"incorrect": "I am bring", "correct": "I brought", "type": "Verb Tense", "explanation": "Use past tense."}],
          "vocabulary_suggestions": [],
          "better_natural_answer": "",
          "short_feedback": "Check verb tense.",
          "scores": {"confidence": 50, "fluency": 40, "grammar": 30, "knowledge": 50, "overall": 42}
        }
        """

    monkeypatch.setattr(groq_speaking, "_chat", fake_chat)

    feedback = groq_speaking.evaluate_speaking_answer(
        "topic",
        "easy",
        "Morning Routine",
        "What did you do this morning?",
        "In this morning I am bring some coffee.",
    )

    assert calls["count"] == 2
    assert feedback["correction_available"] is True
    assert feedback["source"] == "local_rules"
    assert feedback["corrected_answer"] == "This morning I brought some coffee."
    assert feedback["scores"]["overall"] is None


def test_speaking_feedback_rejects_identical_incorrect_correction(monkeypatch):
    monkeypatch.setattr(
        groq_speaking,
        "_chat",
        lambda *args, **kwargs: """
        {
          "appreciation": "Good attempt.",
          "status": "Needs Improvement",
          "has_errors": true,
          "correction_available": true,
          "source": "groq",
          "corrected_answer": "In this morning I am bring some coffee.",
          "explanation": "There is a grammar mistake.",
          "mistakes": [{"incorrect": "I am bring", "correct": "I brought", "type": "Verb Tense", "explanation": "Use past tense."}],
          "vocabulary_suggestions": [],
          "better_natural_answer": "I brought some coffee this morning.",
          "short_feedback": "Check verb tense.",
          "scores": {"confidence": 50, "fluency": 40, "grammar": 30, "knowledge": 50, "overall": 42}
        }
        """,
    )

    feedback = groq_speaking.evaluate_speaking_answer(
        "topic",
        "easy",
        "Morning Routine",
        "What did you do this morning?",
        "In this morning I am bring some coffee.",
    )

    assert feedback["correction_available"] is True
    assert feedback["source"] == "local_rules"
    assert feedback["corrected_answer"] == "This morning I brought some coffee."


def test_speaking_feedback_handles_http_429_without_long_retry(monkeypatch):
    calls = {"count": 0}

    def rate_limited(*args, **kwargs):
        calls["count"] += 1
        raise httpx.HTTPStatusError(
            "rate limited",
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
            response=httpx.Response(429),
        )

    monkeypatch.setattr(groq_speaking, "_chat", rate_limited)

    feedback = groq_speaking.evaluate_speaking_answer(
        "topic",
        "easy",
        "Morning Routine",
        "What did you do this morning?",
        "In this morning I am bring some coffee.",
    )

    assert calls["count"] == 1
    assert feedback["correction_available"] is True
    assert feedback["source"] == "local_rules"
    assert feedback["groq_status"] == "rate_limited"
    assert feedback["corrected_answer"] == "This morning I brought some coffee."
    assert feedback["scores"]["overall"] is None


def test_local_rules_use_present_continuous_context():
    feedback = apply_local_speaking_correction(
        "What are you doing this morning?",
        "In this morning I am bring some coffee.",
    )

    assert feedback["source"] == "local_rules"
    assert feedback["corrected_answer"] == "This morning I am bringing some coffee."
    assert any(mistake["correct"] == "I am bringing" for mistake in feedback["mistakes"])


def test_local_rules_do_not_invent_ambiguous_fragment():
    feedback = apply_local_speaking_correction(
        "Tell me about your hobby.",
        "because photos life",
    )

    assert feedback["correction_available"] is False
    assert feedback["transcript_clear"] is False
    assert feedback["unclear_phrases"] == ["because photos life"]


def test_local_rules_give_family_answer_correction_when_ai_is_unavailable():
    feedback = apply_local_speaking_correction(
        "Can you describe your experience with My Family?",
        "one family is so beautiful and the kind persons are there in my only that is thrown of the most in my family and done and then I am done",
    )

    assert feedback["correction_available"] is True
    assert feedback["source"] == "local_rules"
    assert feedback["corrected_answer"]
    assert "My family" in feedback["corrected_answer"]
    assert feedback["mistake_points"]
    assert feedback["mistakes"]


def test_local_rules_give_planning_answer_correction_when_ai_is_unavailable():
    feedback = apply_local_speaking_correction(
        "What are you planning for your temple visit?",
        "planning to going Temple that is my we can plan",
    )

    assert feedback["correction_available"] is True
    assert feedback["source"] == "local_rules"
    assert feedback["corrected_answer"] == "I am planning to go to the temple, and we can plan the visit together."
    assert "planning to go" in feedback["mistakes"][0]["correct"]
    assert feedback["mistake_points"]


def test_completion_command_is_removed_before_evaluation(monkeypatch):
    prompts = {}

    def fake_chat(system_prompt, user_prompt, **kwargs):
        prompts["user"] = user_prompt
        return """
        {
          "appreciation": "Nice sentence.",
          "status": "Correct",
          "has_errors": false,
          "correction_available": true,
          "source": "groq",
          "corrected_answer": null,
          "explanation": "No grammatical correction was needed.",
          "mistakes": [],
          "vocabulary_suggestions": [],
          "better_natural_answer": null,
          "short_feedback": "No grammatical correction was needed.",
          "scores": {"confidence": 90, "fluency": 90, "grammar": 95, "knowledge": 80, "overall": 89}
        }
        """

    monkeypatch.setattr(groq_speaking, "_chat", fake_chat)

    groq_speaking.evaluate_speaking_answer(
        "topic",
        "easy",
        "Morning Routine",
        "What did you do this morning?",
        "This morning I made coffee and I am them done.",
    )

    assert "This morning I made coffee" in prompts["user"]
    assert "I am them done" not in prompts["user"]


def test_groq_service_exports_writing_helpers():
    assert callable(groq_service.detect_tone)
    assert callable(groq_service.generate_writing_hint)
    assert callable(groq_service.quick_grammar_check)


def test_practice_topics_batch_generation_uses_one_groq_call(app, monkeypatch):
    calls = {"count": 0, "kwargs": None}

    def fake_chat(*args, **kwargs):
        calls["count"] += 1
        calls["kwargs"] = kwargs
        return """
        {
          "topics": [
            {"title":"Morning Routine","description":"Talk about what you do every morning.","expected_duration_seconds":60,"minimum_word_count":null,"maximum_word_count":null},
            {"title":"A Favorite Meal","description":"Describe a meal you enjoy eating.","expected_duration_seconds":60,"minimum_word_count":null,"maximum_word_count":null},
            {"title":"Going Shopping","description":"Practice talking about buying something you need.","expected_duration_seconds":60,"minimum_word_count":null,"maximum_word_count":null},
            {"title":"Meeting a Friend","description":"Talk about plans with a friend.","expected_duration_seconds":60,"minimum_word_count":null,"maximum_word_count":null},
            {"title":"A Small Problem","description":"Explain a simple problem and how you solved it.","expected_duration_seconds":60,"minimum_word_count":null,"maximum_word_count":null},
            {"title":"Weekend Plans","description":"Share what you want to do this weekend.","expected_duration_seconds":60,"minimum_word_count":null,"maximum_word_count":null}
          ]
        }
        """

    monkeypatch.setattr(groq_common, "_chat", fake_chat)

    with app.app_context():
        topics = groq_common.generate_practice_topics("speaking", "topic_wise", "easy", count=6)

    assert calls["count"] == 1
    assert calls["kwargs"]["retry_rate_limit"] is False
    assert calls["kwargs"]["timeout"] == 8
    assert calls["kwargs"]["max_tokens"] == 900
    assert len(topics) == 6
    assert {topic["source"] for topic in topics} == {"groq"}


def test_practice_topics_batch_generation_falls_back_without_extra_groq_calls(app, monkeypatch):
    calls = {"count": 0}

    def fail_chat(*args, **kwargs):
        calls["count"] += 1
        raise ValueError("malformed batch")

    monkeypatch.setattr(groq_common, "_chat", fail_chat)

    with app.app_context():
        topics = groq_common.generate_practice_topics("speaking", "topic_wise", "easy", count=6)

    assert calls["count"] == 1
    assert len(topics) == 6
    assert {topic["source"] for topic in topics} == {"fallback"}


def test_chat_respects_retry_after_for_rate_limits(app, monkeypatch):
    calls = {"count": 0}
    delays = []

    class FakeResponse:
        def __init__(self, status_code, headers=None):
            self.status_code = status_code
            self.headers = headers or {}
            self.request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "rate limited",
                    request=self.request,
                    response=self,
                )

        def json(self):
            return {"choices": [{"message": {"content": "Recovered"}}]}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse(429, {"Retry-After": "1.25"})
        return FakeResponse(200)

    monkeypatch.setattr(groq_common.httpx, "post", fake_post)
    monkeypatch.setattr(groq_common.time, "sleep", delays.append)

    with app.app_context():
        app.config["GROQ_API_KEY"] = "test-key"
        result = groq_common._chat("system", "user")

    assert result == "Recovered"
    assert calls["count"] == 2
    assert delays == [1.25]


def test_chat_hides_reasoning_for_gpt_oss_models(app, monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{\"ok\":true}"}}]}

    def fake_post(*args, **kwargs):
        captured["payload"] = kwargs["json"]
        return FakeResponse()

    monkeypatch.setattr(groq_common.httpx, "post", fake_post)

    with app.app_context():
        app.config["GROQ_API_KEY"] = "test-key"
        app.config["GROQ_MODEL"] = "openai/gpt-oss-120b"
        result = groq_common._chat("system", "user")

    assert result == "{\"ok\":true}"
    assert captured["payload"]["reasoning_format"] == "hidden"


def test_chat_retries_connect_errors_with_longer_backoff(app, monkeypatch):
    calls = {"count": 0}
    delays = []

    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.headers = {}
            self.request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")

        def raise_for_status(self):
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("request failed", request=self.request, response=self)

        def json(self):
            return {"choices": [{"message": {"content": "Recovered"}}]}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise httpx.ConnectError("dns lookup failed")
        return FakeResponse(200)

    monkeypatch.setattr(groq_common.httpx, "post", fake_post)
    monkeypatch.setattr(groq_common.time, "sleep", delays.append)

    with app.app_context():
        app.config["GROQ_API_KEY"] = "test-key"
        result = groq_common._chat("system", "user")

    assert result == "Recovered"
    assert calls["count"] == 2
    assert delays == [2.0]


def test_generate_topics_route_returns_cached_cards_without_second_groq_call(client, auth_headers, monkeypatch):
    calls = {"count": 0}

    def fake_generate_topics(*args, **kwargs):
        calls["count"] += 1
        return [
            {
                "title": f"Cached Topic {index}",
                "description": f"Practice with cached topic {index}.",
                "expected_duration_seconds": 60,
                "minimum_word_count": None,
                "maximum_word_count": None,
                "source": "groq",
            }
            for index in range(1, 7)
        ]

    monkeypatch.setattr(practice.groq_service, "generate_practice_topics", fake_generate_topics)

    request_payload = {
        "practice_type": "speaking",
        "mode": "topic_wise",
        "difficulty": "easy",
    }
    first = client.post("/api/practice/generate-topics", json=request_payload, headers=auth_headers)
    second = client.post("/api/practice/generate-topics", json=request_payload, headers=auth_headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert len(second.get_json()["data"]) == 6

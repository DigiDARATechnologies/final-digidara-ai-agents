"""Grading must fit its time limit. With gpt-5-mini at its default reasoning,
grading five answers took ~36 s against a 20 s request limit: every try timed
out and learners only ever got the provisional "still generating" report."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import groq_client
from ai import chat_client


class FakeClient:
    def __init__(self):
        self.calls = []

    def with_options(self, **options):
        self.calls.append({"options": options})
        return self

    @property
    def chat(self):
        return SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.calls.append({"request": request})
        content = json.dumps({"evaluations": [{"question_id": 1, "verdict": "correct", "reason": "ok", "ideal_answer": "x"}]})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=None)


def _run_batch():
    fake = FakeClient()
    with patch.object(chat_client, "_get_client", return_value=fake), \
            patch.object(chat_client, "_record_usage_safely"), \
            patch.object(groq_client, "EVAL_MODEL", "gpt-5-mini"):
        groq_client.evaluate_answers_batch("technical", "python", "beginner",
                                           [{"question_id": 1, "question": "Q", "answer": "A", "unanswered": False}])
    options = next(call["options"] for call in fake.calls if "options" in call)
    request = next(call["request"] for call in fake.calls if "request" in call)
    return options, request


def test_grading_asks_gpt5_for_low_reasoning():
    _options, request = _run_batch()
    assert request["model"] == "gpt-5-mini"
    assert request["reasoning_effort"] == "low"
    assert "temperature" not in request


def test_grading_gets_one_try_with_room_to_finish():
    options, _request = _run_batch()
    assert options["timeout"] >= 45
    assert options["max_retries"] == 0


def test_non_gpt5_models_get_no_reasoning_setting():
    fake = FakeClient()
    with patch.object(chat_client, "_get_client", return_value=fake), \
            patch.object(chat_client, "_record_usage_safely"):
        chat_client.chat([{"role": "user", "content": "hi"}], model_override="gpt-4o-mini", reasoning_effort="low")
    request = next(call["request"] for call in fake.calls if "request" in call)
    assert "reasoning_effort" not in request and request["temperature"] == 0.7

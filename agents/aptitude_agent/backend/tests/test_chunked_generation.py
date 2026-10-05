"""Large Mixed Tests are generated as parallel chunks instead of one request.

One request for a 60-question test had to write ~15,000 tokens before a 120 s
timeout and a 16,000-token cap, so big tests intermittently failed with 503.
"""
import hashlib
import threading
import time

import pytest

from backend.app.services import test_question_service as service


def slot(index):
    return {"category": "Quantitative Aptitude", "topic": f"Topic {index}", "difficulty": "Easy"}


def wording(topic):
    """Distinct wording per topic, so the real near-duplicate check passes it."""
    digest = hashlib.sha256(topic.encode()).hexdigest()
    return " ".join(digest[i:i + 8] for i in range(0, 64, 8))


def item(text):
    return {"question": text, "content_hash": f"hash:{text}", "category": "Quantitative Aptitude",
            "topic": "t", "difficulty": "Easy", "options": {}, "correct_answer": "A", "explanation": "e"}


def fake_generator(calls, fail_first_call_for=None, duplicate=None):
    lock = threading.Lock()

    def generate(slots, avoid_questions=None, **_):
        with lock:
            calls.append([s["topic"] for s in slots])
            first = calls.count([s["topic"] for s in slots]) == 1
        if fail_first_call_for and slots[0]["topic"] == fail_first_call_for and first:
            raise ValueError("chunk failed validation")
        def text(s):
            # The repeated wording comes back unless the caller asked to avoid it.
            if duplicate and s["topic"] in duplicate[1] and duplicate[0] not in (avoid_questions or []):
                return duplicate[0]
            return wording(s["topic"])
        questions = [item(text(s)) for s in slots]
        return questions, "gpt-test", {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
    return generate


def test_a_small_test_keeps_its_single_request(app, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "generate_questions", fake_generator(calls))
    with app.app_context():
        questions, _, _ = service.generate_question_set([slot(i) for i in range(10)], avoid_questions=[], deadline=time.monotonic() + 60)
    assert len(calls) == 1 and len(questions) == 10


def test_a_sixty_question_test_is_six_parallel_chunks_in_order(app, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "generate_questions", fake_generator(calls))
    with app.app_context():
        questions, model, usage = service.generate_question_set([slot(i) for i in range(60)], avoid_questions=[], deadline=time.monotonic() + 60)
    assert sorted(len(c) for c in calls) == [10] * 6
    assert [q["question"] for q in questions] == [wording(f"Topic {i}") for i in range(60)]
    assert model == "gpt-test" and usage["total_tokens"] == 180


def test_a_failed_chunk_is_retried_once_instead_of_failing_the_test(app, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "generate_questions", fake_generator(calls, fail_first_call_for="Topic 20"))
    with app.app_context():
        questions, _, _ = service.generate_question_set([slot(i) for i in range(30)], avoid_questions=[], deadline=time.monotonic() + 60)
    assert len(questions) == 30
    assert sum(1 for c in calls if c[0] == "Topic 20") == 2


def test_a_chunk_that_fails_twice_still_fails_the_test(app, monkeypatch):
    def always_fail(slots, **_):
        raise ValueError("provider down")
    monkeypatch.setattr(service, "generate_questions", always_fail)
    with app.app_context(), pytest.raises(ValueError):
        service.generate_question_set([slot(i) for i in range(30)], avoid_questions=[], deadline=time.monotonic() + 60)


def test_a_question_repeated_across_chunks_is_replaced(app, monkeypatch):
    calls = []
    # Topic 3 (chunk 1) and Topic 15 (chunk 2) both come back as the same question.
    monkeypatch.setattr(service, "generate_questions", fake_generator(calls, duplicate=("Same question", {"Topic 3", "Topic 15"})))
    with app.app_context():
        questions, _, _ = service.generate_question_set([slot(i) for i in range(20)], avoid_questions=[], deadline=time.monotonic() + 60)
    texts = [q["question"] for q in questions]
    assert texts.count("Same question") == 1
    assert calls[-1] == ["Topic 15"]  # only the repeat was regenerated

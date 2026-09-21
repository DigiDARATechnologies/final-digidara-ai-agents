"""A retry replaces only the questions that failed, not the whole batch."""
import pytest
from flask import Flask

from backend.app.services import test_generation

SLOT = {"category": "Logical Reasoning", "topic": "Syllogism", "difficulty": "Medium"}
OPTIONS = {"A": "First", "B": "Second", "C": "Third", "D": "Fourth"}
USAGE = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}

Q_MANAGER = "Every manager reviews reports, and Kiran is a manager. Which conclusion must hold?"
Q_CODE = "A code uses the values 180, 195, and 210. Which statement follows?"
Q_CHAIRS = "In a row of five chairs, Meera sits left of Ravi and right of Tara. Who sits in the middle position?"
Q_AGES = "Four friends compare ages; Asha is older than Bala but younger than Charu. Who is the eldest?"


def good(question):
    return {**SLOT, "question": question, "options": dict(OPTIONS), "correct_answer": "A",
            "explanation": "The stated rule shows that the correct option is A."}


def bad(question):
    # Names a different option than the one marked correct: always rejected.
    return {**good(question), "explanation": "The correct option is B."}


class Provider:
    """Scripted json_completion that records what each call asked for."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, system_prompt, prompt, temperature, **kwargs):
        schema = kwargs["response_schema"]["properties"]["questions"]
        self.calls.append({"prompt": prompt, "asked_for": schema["minItems"]})
        return ({"questions": self.responses[len(self.calls) - 1]}, dict(USAGE))

    @property
    def asked_for(self):
        return [call["asked_for"] for call in self.calls]


def run(monkeypatch, provider, slots, attempts=3):
    monkeypatch.setattr(test_generation, "json_completion", provider)
    app = Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model", ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():
        return test_generation.generate_questions(slots, max_validation_attempts=attempts)


def test_all_valid_on_the_first_attempt_is_unchanged(monkeypatch):
    provider = Provider([good(Q_MANAGER), good(Q_CODE), good(Q_CHAIRS)])
    questions, _model, usage = run(monkeypatch, provider, [SLOT] * 3)
    assert [q["question"] for q in questions] == [Q_MANAGER, Q_CODE, Q_CHAIRS]
    assert provider.asked_for == [3]
    assert usage["validation_attempt_count"] == 1


def test_only_the_failed_slot_is_asked_for_again_and_order_is_preserved(monkeypatch):
    provider = Provider(
        [good(Q_MANAGER), bad(Q_CODE), good(Q_CHAIRS)],
        [good(Q_AGES)],
    )
    questions, _model, usage = run(monkeypatch, provider, [SLOT] * 3)

    assert provider.asked_for == [3, 1]  # the retry asked for one question, not three
    assert [q["question"] for q in questions] == [Q_MANAGER, Q_AGES, Q_CHAIRS]  # replacement keeps slot 2
    assert usage["validation_attempt_count"] == 2
    retry_prompt = provider.calls[1]["prompt"]
    assert "Generate exactly 1 original" in retry_prompt
    # The accepted questions are passed as things to avoid, so a replacement can't repeat them.
    assert Q_MANAGER in retry_prompt and Q_CHAIRS in retry_prompt


def test_several_failures_are_all_replaced_in_one_retry(monkeypatch):
    provider = Provider(
        [bad(Q_MANAGER), good(Q_CODE), bad(Q_CHAIRS)],
        [good(Q_AGES), good("Which day comes two days after Monday, if today is Friday?")],
    )
    questions, _model, _usage = run(monkeypatch, provider, [SLOT] * 3)
    assert provider.asked_for == [3, 2]
    assert [q["question"] for q in questions] == [Q_AGES, Q_CODE, "Which day comes two days after Monday, if today is Friday?"]


def test_a_slot_that_keeps_failing_still_fails_but_only_ever_asks_for_that_slot(monkeypatch):
    provider = Provider(
        [good(Q_MANAGER), bad(Q_CODE), good(Q_CHAIRS)],
        [bad(Q_AGES)],
        [bad(Q_AGES)],
    )
    with pytest.raises(ValueError, match="question 2"):
        run(monkeypatch, provider, [SLOT] * 3, attempts=3)
    assert provider.asked_for == [3, 1, 1]


def test_a_wrong_count_on_the_retry_is_retried_without_losing_accepted_questions(monkeypatch):
    provider = Provider(
        [good(Q_MANAGER), bad(Q_CODE), good(Q_CHAIRS)],
        [good(Q_AGES), good("Extra question that should not be here at all?")],  # 2 instead of 1
        [good(Q_AGES)],
    )
    questions, _model, _usage = run(monkeypatch, provider, [SLOT] * 3)
    assert provider.asked_for == [3, 1, 1]
    assert [q["question"] for q in questions] == [Q_MANAGER, Q_AGES, Q_CHAIRS]


def test_a_replacement_that_repeats_an_accepted_question_is_asked_for_again_alone(monkeypatch):
    provider = Provider(
        [good(Q_MANAGER), bad(Q_CODE), good(Q_CHAIRS)],
        [good(Q_MANAGER)],  # replacement repeats an accepted question: only the replacement is blamed
        [good(Q_CODE)],
    )
    questions, _model, _usage = run(monkeypatch, provider, [SLOT] * 3)
    assert provider.asked_for == [3, 1, 1]  # never a full 3 again
    assert [q["question"] for q in questions] == [Q_MANAGER, Q_CODE, Q_CHAIRS]


def test_two_valid_but_duplicate_questions_replace_only_the_later_one(monkeypatch):
    twin = "Every manager checks reports, and Kiran is a manager. Which conclusion must hold?"
    provider = Provider(
        [good(Q_MANAGER), good(Q_CHAIRS), good(twin)],  # 3 is a paraphrase of 1
        [good(Q_AGES)],
    )
    questions, _model, _usage = run(monkeypatch, provider, [SLOT] * 3)
    assert provider.asked_for == [3, 1]
    assert [q["question"] for q in questions] == [Q_MANAGER, Q_CHAIRS, Q_AGES]


def test_a_question_repeating_a_recent_one_is_the_only_one_replaced(monkeypatch):
    provider = Provider(
        [good(Q_MANAGER), good(Q_CODE), good(Q_CHAIRS)],
        [good(Q_AGES)],
    )
    monkeypatch.setattr(test_generation, "json_completion", provider)
    app = Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model", ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():
        questions, _model, _usage = test_generation.generate_questions(
            [SLOT] * 3, avoid_questions=["In a row of five chairs, Meera sits left of Ravi and right of Tara. Who sits in the middle?"],
            max_validation_attempts=3,
        )
    assert provider.asked_for == [3, 1]
    assert [q["question"] for q in questions] == [Q_MANAGER, Q_CODE, Q_AGES]


def test_offender_selection_prefers_the_fresh_question_and_otherwise_the_later_one():
    def item(text):
        return {"question": text, "content_hash": text, "structural_hash": None}
    twin_a, twin_b = "What is the purpose of RAM?", "What function does RAM perform in a computer?"
    validated = [item(twin_a), item("Which protocol assigns IP addresses on a network?"), item(twin_b)]
    assert test_generation._cross_check_offenders(validated, {0, 1, 2}, [])[0] == {2}  # all fresh: later one
    assert test_generation._cross_check_offenders(validated, {0}, [])[0] == {0}  # only the first is fresh
    assert test_generation._cross_check_offenders(validated, set(), [])[0] == {2}  # neither fresh: later one
    assert test_generation._cross_check_offenders(validated[1:2], {0}, [])[0] == set()


def test_a_single_slot_batch_still_works(monkeypatch):
    provider = Provider([bad(Q_MANAGER)], [good(Q_MANAGER)])
    questions, _model, _usage = run(monkeypatch, provider, [SLOT], attempts=2)
    assert provider.asked_for == [1, 1]
    assert questions[0]["question"] == Q_MANAGER

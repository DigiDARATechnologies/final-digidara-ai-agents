"""One bad question no longer sinks a whole mixed test (the live 503).

Only the OpenAI call is faked. Everything else -- slot planning, the model's
real response format, canonicalizing, validation, the retry, storing 21
questions -- is the production path.
"""
import json
import re

from backend.app.extensions import db
from backend.app.models import AptitudeTest, AptitudeTestQuestion
from backend.app.models.operations import AuditEvent


class ScriptedProvider:
    """Answers a batch prompt with one valid question per requested slot,
    except the first Quantitative slot of the first call, which gets the
    exact degenerate output seen in production."""

    def __init__(self, duplicate_last=False):
        self.duplicate_last = duplicate_last
        self.asked_for = []
        self.prompts = []
        self._word = 0

    def _next_word(self):
        self._word += 1
        return "".join(chr(97 + (self._word * k + j) % 26) for j, k in enumerate((3, 5, 7, 11, 13, 17, 19)))

    def _good(self, slot):
        word = self._next_word()
        base = {"distractor_codes": [None, None, None], "correct_option_code": None}
        if slot["category"] == "Quantitative Aptitude":
            a, b = 40 + self._word * 7, 13 + self._word * 3
            total = a + b
            other = word[::-1]
            return {**base, "question": f"{word.capitalize()} holds {a} {other} and {other[2:]} adds {b} more {other}. How many {other} are there in all?",
                    "correct_option": str(total), "distractors": [str(total + 5), str(total + 11), str(total - 9)],
                    "reason": "", "calculation_step_1": f"{a} + {b} = {total}", "calculation_step_2": f"Combined load = {total}"}
        return {**base, "question": f"Among {word}, {word[::-1]}, {word[2:]+word[:2]} and {word[3:]+word[:3]}, which one best fits {word[4:]+word[:4]}?",
                "correct_option": f"The {word} rule always applies", "distractors": [f"The {word} rule never applies", f"The {word} rule sometimes applies", f"The {word} rule is unrelated"],
                "reason": f"The premises about {word} force this conclusion.", "calculation_step_1": "", "calculation_step_2": ""}

    def _degenerate(self):
        # What the model actually returned for a Coordinate Geometry slot: a
        # non-numeric "matching" answer with empty calculation fields.
        return {"question": "Which coordinate point pairs are matched by the given graph?",
                "correct_option": "A matches with C",
                "distractors": ["A does not match with C", "B does not match with A", "C matches with A"],
                "reason": "", "calculation_step_1": "", "calculation_step_2": "/",
                "distractor_codes": [None, None, None], "correct_option_code": None}

    def __call__(self, system_prompt, prompt, temperature, **kwargs):
        match = re.search(r"Ordered slots \((\d+) total\): (\[.*?\])\nReturn all", prompt, re.DOTALL)
        slots = json.loads(match.group(2))
        self.asked_for.append(len(slots))
        self.prompts.append(prompt)
        items = []
        degenerate_index = next((i for i, s in enumerate(slots) if s["category"] == "Quantitative Aptitude"), None) if len(self.asked_for) == 1 else None
        for index, slot in enumerate(slots):
            items.append(self._degenerate() if index == degenerate_index and not self.duplicate_last else self._good(slot))
        if self.duplicate_last and len(self.asked_for) == 1:
            # Two individually valid questions with the same wording: the batch must not be thrown away.
            items[-1]["question"] = items[0]["question"]
        return {"questions": items}, {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300, "model": "test-model"}


def test_one_degenerate_question_is_replaced_alone_and_the_test_is_created(app, client, auth_headers, monkeypatch):
    provider = ScriptedProvider()
    monkeypatch.setattr("backend.app.services.test_generation.json_completion", provider)
    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(app.config, "ALLOW_DEMO_QUESTIONS", False)
    monkeypatch.setitem(app.config, "BATCH_GENERATION_MAX_ATTEMPTS", 2)

    created = client.post("/api/aptitude/tests", headers=auth_headers, json={"mode": "mixed"})

    if created.status_code != 201:
        with app.app_context():
            reasons = [e.metadata_json for e in AuditEvent.query.filter_by(event_type="generation_failed").all()]
        raise AssertionError((created.get_json(), reasons, provider.asked_for))
    # 21 questions asked for once; the retry asked for the single bad slot, not 21 again.
    assert provider.asked_for == [21, 1]
    assert "Generate exactly 1 original" in provider.prompts[1]

    with app.app_context():
        test = db.session.get(AptitudeTest, created.get_json()["test_id"])
        assert test.status == "ready"
        questions = AptitudeTestQuestion.query.filter_by(test_id=test.id).order_by(AptitudeTestQuestion.sequence_no).all()
        assert len(questions) == 21
        assert not any("matches with" in q.question_text for q in questions)


def test_two_duplicate_questions_replace_only_the_later_one_and_the_test_is_created(app, client, auth_headers, monkeypatch):
    provider = ScriptedProvider(duplicate_last=True)
    monkeypatch.setattr("backend.app.services.test_generation.json_completion", provider)
    monkeypatch.setitem(app.config, "OPENAI_API_KEY", "test-key")
    monkeypatch.setitem(app.config, "ALLOW_DEMO_QUESTIONS", False)
    monkeypatch.setitem(app.config, "BATCH_GENERATION_MAX_ATTEMPTS", 2)

    created = client.post("/api/aptitude/tests", headers=auth_headers, json={"mode": "mixed"})

    assert created.status_code == 201, created.get_json()
    assert provider.asked_for == [21, 1]  # not 21 again
    with app.app_context():
        questions = AptitudeTestQuestion.query.filter_by(test_id=created.get_json()["test_id"]).all()
        assert len(questions) == 21 and len({q.question_text for q in questions}) == 21
        assert all(q.generation_model != "demo-fixture-fallback" for q in questions)

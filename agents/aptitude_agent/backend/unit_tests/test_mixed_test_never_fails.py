"""Production 2026-11-17..19: 36 mixed tests failed with "We could not prepare a
quality assessment" because one Technical Aptitude question did not repeat
the learner's saved skill word for word, and a single-question chunk that the
model never got right was not filled from the stored, validated questions."""
import pytest
from flask import Flask

from backend.app.config import Config
from backend.app.services import test_generation
from backend.app.services.question_validation import _validate_saved_skill_alignment

from test_partial_batch_retry import SLOT, Provider, bad, good

Q_AGES = "Four friends compare ages; Asha is older than Bala but younger than Charu. Who is the eldest?"
Q_ROW = "Five people sit in a row and Ravi sits at the left end. Who can sit beside Ravi?"


def _technical(skill):
    return {"category": "Technical Aptitude", "technical_skill": skill}


@pytest.mark.parametrize("skill, question", [
    ("Data Analysis with Excel", "Which Excel function returns the largest value in a range?"),
    ("Machine Learning Basics", "Which machine learning task predicts a continuous value?"),
    ("SQL Fundamentals", "Which SQL clause filters grouped rows?"),
])
def test_a_distinctive_word_of_the_saved_skill_is_enough(skill, question):
    _validate_saved_skill_alignment(question, {"A": "a"}, "Because.", _technical(skill))


@pytest.mark.parametrize("skill, question", [
    ("Machine Learning", "Which Power BI visual shows a trend over time?"),
    ("Data Analysis with Excel", "Which data structure gives constant-time lookup by key?"),
])
def test_another_skill_or_only_generic_words_still_fail(skill, question):
    with pytest.raises(ValueError, match="saved technical skill"):
        _validate_saved_skill_alignment(question, {"A": "a"}, "Because.", _technical(skill))


def test_a_chunk_the_model_never_got_right_is_filled_from_stored_questions(monkeypatch):
    provider = Provider([bad(Q_AGES)], [bad(Q_AGES)], [bad(Q_AGES)])
    stored = []

    def fill(slots, keep):
        stored.append((len(slots), list(keep)))
        return [{**good(Q_ROW), "content_hash": "stored", "structural_hash": None}]

    monkeypatch.setattr(test_generation, "json_completion", provider)
    app = Flask(__name__)
    app.config.update(OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model", ALLOW_DEMO_QUESTIONS=False)
    with app.app_context():
        questions, _model, _usage = test_generation.generate_questions(
            [SLOT], max_validation_attempts=3, _rescue=False, fill_missing=fill,
        )
    assert [q["question"] for q in questions] == [Q_ROW]
    assert stored == [(1, [])]


def test_tests_are_written_three_questions_per_request():
    assert Config.QUESTION_GENERATION_CHUNK_SIZE == 3
    assert Config.QUESTION_GENERATION_PARALLEL_CHUNKS >= 7  # a 21-question test at once

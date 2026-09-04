import pytest
from flask import Flask

from backend.app.services.question_validation import content_hash, normalize_question_text, questions_are_near_duplicates
from backend.app.services.test_generation import build_category_slots, demo_questions


@pytest.mark.parametrize("first,second",[
    ("What is RAM?", "WHAT IS RAM?"),
    ("What is RAM?", "What   is   RAM?"),
    ("What is RAM?", "What is RAM"),
    ("Which OS component manages CPU scheduling? (Local practice abc123)", "Which OS component manages CPU scheduling? (Local practice xyz999)"),
])
def test_normalized_question_fingerprint_rejects_surface_variations(first,second):
    assert content_hash(first)==content_hash(second)
    assert questions_are_near_duplicates(first,second)


def test_near_duplicate_concept_is_rejected():
    assert questions_are_near_duplicates(
        "What is the purpose of RAM?",
        "What function does RAM perform in a computer?",
    )


def test_meaningfully_different_questions_remain_distinct():
    assert not questions_are_near_duplicates(
        "Which protocol automatically assigns IP addresses on a network?",
        "What is the main purpose of a database index?",
    )


@pytest.mark.parametrize("category",[
    "Quantitative Aptitude", "Logical Reasoning", "Verbal Ability",
    "Analytical Reasoning", "Computer Fundamentals", "Technical Aptitude",
])
def test_local_category_fixture_produces_five_unique_sample_questions(category):
    app=Flask(__name__)
    with app.app_context():
        # The handcrafted demo fixture is a five-item validation sample. The
        # learner-facing Category Practice route uses live generation and does
        # not enable this local fallback.
        questions=demo_questions(build_category_slots(category,"Beginner")[:5])
    fingerprints=[content_hash(question["question"]) for question in questions]
    assert len(questions)==5
    assert len(fingerprints)==len(set(fingerprints))
    assert all("local practice" not in question["question"].casefold() for question in questions)

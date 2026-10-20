import pytest

from backend.app.services.question_validation import validate_generated_item


SLOT = {"category": "Analytical Reasoning", "topic": "Constraint Optimization", "difficulty": "Easy"}


def item(explanation):
    return {
        **SLOT,
        "question": "A store sells pencils for $0.50 each. If you buy 10 pencils, how much will you spend?",
        "options": {"A": "$4.00", "B": "$5.00", "C": "$6.00", "D": "$7.50"},
        "correct_answer": "B",
        "explanation": explanation,
    }


def test_an_explanation_that_only_states_the_answer_is_rejected():
    # The model sometimes left its reason empty, and the report printed just this.
    with pytest.raises(ValueError, match="explain why"):
        validate_generated_item(item("Answer = $5.00."), SLOT)


def test_an_explanation_with_a_reason_is_accepted():
    validated = validate_generated_item(item("Ten pencils at fifty cents each cost ten times the unit price. Answer = $5.00."), SLOT)
    assert validated["explanation"].startswith("Ten pencils")

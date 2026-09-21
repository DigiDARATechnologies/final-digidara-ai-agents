"""Seating/ordering puzzles where the option content is itself a bare letter (e.g.
correct_answer="B", options={"B": "A", ...} -- "the answer is entity A") were being
rejected in production: 'explanation does not support the correct answer'."""
import pytest

from backend.app.services.question_validation import _states_correct_answer


@pytest.mark.parametrize("explanation,option_text,answer_key", [
    # The three exact failures from the live server log (Sept 21).
    ("A is directly to the right of B, making A the one between B and C. Answer = A.", "A", "B"),
    ("D is opposite B, and since A is to the right of B, D must be to the right of C. Answer = D.", "D", "A"),
    ("B is positioned between A and C based on the seating arrangement described. Answer = B.", "B", "C"),
])
def test_a_concluded_entity_letter_matching_the_option_content_is_accepted(explanation, option_text, answer_key):
    assert _states_correct_answer(explanation, option_text, answer_key)


def test_a_concluded_letter_that_matches_neither_the_content_nor_the_key_is_still_rejected():
    # option content is "D" (for the correct key "D" itself), but the explanation concludes "B".
    assert not _states_correct_answer("Some reasoning that ends up somewhere else. Answer = B.", "D", "D")


def test_ordinary_bare_option_key_conclusions_are_unaffected():
    # option text is not a bare A-D letter, so this still checks the conclusion against answer_key.
    assert _states_correct_answer("Binary search runs in logarithmic time. The correct option is B.", "O(log n)", "B")
    assert not _states_correct_answer("Binary search runs in logarithmic time. The correct option is B.", "O(log n)", "C")


def test_a_lettered_option_conclusion_naming_the_wrong_entity_is_rejected():
    # correct key is "B" (content "A"); the explanation concludes with a letter
    # that matches neither the correct key nor the correct entity's content.
    assert not _states_correct_answer("C is seated at the head of the table. Answer = C.", "A", "B")

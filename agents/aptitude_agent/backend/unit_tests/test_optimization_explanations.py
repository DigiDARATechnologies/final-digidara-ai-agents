"""Correct quantitative answers that used to be rejected, and the checks that must stay strict."""
import pytest

from backend.app.services.question_validation import _has_matching_math_conclusion, questions_are_near_duplicates


def explanation(step_1, step_2, answer):
    return f"Step 1: {step_1}\nStep 2: {step_2}\nStep 3: Answer = {answer}."


@pytest.mark.parametrize("option,step_1,step_2", [
    ("40m", "Side = 160 / 4 = 40", "Length = 40 m"),  # unit written on the option, spaced in the working
    ("15cm", "Side = 60 / 4 = 15cm", "Length = 15cm"),
    ("20%", "Increase = 10 / 50 = 0.2", "Percent = 0.2 x 100 = 20"),  # percent option, plain number in the working
    ("12kg", "Weight per box = 3 x 4", "Total = 3 x 4"),  # ASCII x for multiplication, result never written out
    ("50 km/h", "Speed = 200 / 4 = 50", "Speed = 50 km/h"),
    ("$1,600", "Revenue = 40 * 40 = 1600", "Max revenue = $1,600"),
])
def test_a_correctly_derived_answer_is_accepted_whatever_units_or_percent_signs_it_carries(option, step_1, step_2):
    assert _has_matching_math_conclusion(explanation(step_1, step_2, option), option)


@pytest.mark.parametrize("option,step_1,step_2", [
    ("25", "Let x be the width; 2x + 2y = 40", "y = 20 - x, so A = x(20 - x)"),  # answer never derived
    ("99", "a = 2 + 2", "b = 3 + 3"),
    ("30%", "Ratio = 3 / 10", "Value = 0.4"),
    ("7m", "Side = 160 / 4 = 40", "Length = 40 m"),  # a different number than the one derived
])
def test_an_answer_that_was_not_derived_is_still_rejected(option, step_1, step_2):
    assert not _has_matching_math_conclusion(explanation(step_1, step_2, option), option)


def test_long_scenario_questions_that_share_a_keyword_are_not_concept_duplicates():
    first = "A print server keeps a queue of jobs; each job takes 3 minutes and 4 jobs arrive every 10 minutes. How long is the queue after an hour?"
    second = "In a bank queue, a teller serves one customer every 2 minutes while 5 customers join every 8 minutes. How many customers remain waiting after an hour?"
    assert not questions_are_near_duplicates(first, second)


def test_short_definitional_questions_about_the_same_concept_are_still_duplicates():
    assert questions_are_near_duplicates("What is the purpose of RAM?", "What function does RAM perform in a computer?")
    assert questions_are_near_duplicates("What is a queue?", "Define a queue.")

"""MCQ problems have no code to execute (see migrations/005_mcq_problems_up.sql
and repository.submit_mcq_answer) so there's nothing to run against a real
interpreter the way test_sql_catalog_content.py etc. do -- this instead
checks every MCQ problem's own internal consistency: the correct key must
actually be one of the offered options, there must be at least two distinct
options, and neither the question nor its explanation may be empty.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.problem_catalog import PROBLEMS

MCQ_PROBLEMS = [problem for problem in PROBLEMS if problem.get("question_type") == "mcq"]


def test_at_least_one_mcq_problem_exists():
    assert MCQ_PROBLEMS


@pytest.mark.parametrize("problem", MCQ_PROBLEMS, ids=lambda problem: problem["slug"])
def test_mcq_problem_is_internally_consistent(problem):
    options = problem.get("mcq_options")
    assert isinstance(options, dict) and len(options) >= 2, f"{problem['slug']}: needs at least 2 options"
    assert len(set(options.values())) == len(options), f"{problem['slug']}: two options have identical text"
    correct_key = problem.get("mcq_correct_key")
    assert correct_key in options, f"{problem['slug']}: mcq_correct_key {correct_key!r} is not one of {list(options)}"
    assert problem["description"].strip(), f"{problem['slug']}: empty question text"
    assert problem.get("mcq_explanation", "").strip(), f"{problem['slug']}: empty explanation"


@pytest.mark.parametrize("problem", MCQ_PROBLEMS, ids=lambda problem: problem["slug"])
def test_mcq_problem_has_no_code_execution_fields(problem):
    """MCQ rows should not carry code-problem fields that no longer apply --
    catches an entry accidentally copy-pasted from a code problem."""
    assert not problem.get("tests"), f"{problem['slug']}: MCQ problems should have no test cases"
    assert problem.get("language_id") is None, f"{problem['slug']}: MCQ problems should have no judge0 language id"

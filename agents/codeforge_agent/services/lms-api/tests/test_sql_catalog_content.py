"""Every SQL/SQLite problem in problem_catalog.py carries a "reference_query"
(test-only; not a DB column, ignored by scripts/seed.py's explicit-key
inserts). This actually runs that query against each test case's fixture with
Python's sqlite3 module -- the same engine Judge0 language 82 uses -- and
checks it reproduces the stored expected_output exactly. This is the guardrail
against a hand-typed expected_output being wrong, and it fails loudly the
moment a future SQL problem is added without one.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.evaluation import SQL_LANGUAGE_ID
from lms_api.problem_catalog import PROBLEMS


def run(fixture, query):
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(fixture)
        cur = con.execute(query)
        lines = ["|".join("" if v is None else str(v) for v in row) for row in cur.fetchall()]
        return ("\n".join(lines) + "\n") if lines else ""
    finally:
        con.close()


SQL_PROBLEMS = [problem for problem in PROBLEMS if problem["language_id"] == SQL_LANGUAGE_ID]


def test_every_sql_problem_has_a_reference_query():
    missing = [problem["slug"] for problem in SQL_PROBLEMS if not problem.get("reference_query")]
    assert not missing, f"SQL problems missing a reference_query for content verification: {missing}"


@pytest.mark.parametrize("problem", SQL_PROBLEMS, ids=lambda problem: problem["slug"])
def test_reference_query_reproduces_every_stored_expected_output(problem):
    for index, (fixture, expected_output, _hidden, _weight) in enumerate(problem["tests"]):
        actual = run(fixture, problem["reference_query"])
        assert actual == expected_output, (
            f"{problem['slug']} test case {index}: reference query produced {actual!r}, "
            f"catalog stores {expected_output!r}"
        )


@pytest.mark.parametrize("problem", SQL_PROBLEMS, ids=lambda problem: problem["slug"])
def test_expected_outputs_are_not_trivially_empty(problem):
    """Every test case must expect actual content, not blank output -- a
    query that produces no rows would otherwise "pass" against any query."""
    for _fixture, expected_output, _hidden, _weight in problem["tests"]:
        assert expected_output.strip(), f"{problem['slug']}: a test case expects empty output"

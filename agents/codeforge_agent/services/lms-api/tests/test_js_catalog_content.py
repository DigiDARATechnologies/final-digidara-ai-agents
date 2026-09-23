"""Every generated JavaScript problem carries a "reference_source" (test-only;
not a DB column, ignored by scripts/seed.py's explicit-key inserts). This
actually runs that source with the real node binary against each test case's
stdin and checks it reproduces the stored expected_output exactly -- the
guardrail against a hand-typed expected_output being wrong. Reference sources
are kept to a conservative pre-ES2020 subset (no optional chaining, no
nullish coalescing, no Array.prototype.at, no String.prototype.replaceAll) so
they behave identically on the Node 24 used here and Judge0's Node 12.14.0
(db/languages/active.rb:159-164 in the vendored judge0/ checkout).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.evaluation import SQL_LANGUAGE_ID
from lms_api.problem_catalog import PROBLEMS

JS_LANGUAGE_ID = 63

NODE = shutil.which("node")


def run(source, stdin_text):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        result = subprocess.run([NODE, path], input=stdin_text, capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"node exited {result.returncode}\nstderr: {result.stderr}"
        return result.stdout
    finally:
        Path(path).unlink()


JS_PROBLEMS = [problem for problem in PROBLEMS if problem["language_id"] == JS_LANGUAGE_ID]
GENERATED_JS_PROBLEMS = [problem for problem in JS_PROBLEMS if problem.get("reference_source")]

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed in this environment")


def test_every_generated_js_problem_has_a_reference_source():
    # Excludes the one hand-authored problem that predates this convention.
    missing = [
        problem["slug"] for problem in JS_PROBLEMS
        if not problem.get("reference_source") and problem["slug"] != "add-two-numbers-js"
    ]
    assert not missing, f"JS problems missing a reference_source for content verification: {missing}"


@pytest.mark.parametrize("problem", GENERATED_JS_PROBLEMS, ids=lambda problem: problem["slug"])
def test_reference_source_reproduces_every_stored_expected_output(problem):
    for index, (stdin_text, expected_output, _hidden, _weight) in enumerate(problem["tests"]):
        actual = run(problem["reference_source"], stdin_text)
        assert actual == expected_output, (
            f"{problem['slug']} test case {index}: reference source produced {actual!r}, "
            f"catalog stores {expected_output!r}"
        )


@pytest.mark.parametrize("problem", GENERATED_JS_PROBLEMS, ids=lambda problem: problem["slug"])
def test_expected_outputs_are_not_trivially_empty(problem):
    for _stdin_text, expected_output, _hidden, _weight in problem["tests"]:
        assert expected_output.strip(), f"{problem['slug']}: a test case expects empty output"


def test_sql_language_id_constant_is_not_reused_by_javascript():
    assert SQL_LANGUAGE_ID != JS_LANGUAGE_ID

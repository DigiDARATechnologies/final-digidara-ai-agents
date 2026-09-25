"""Every generated Pandas problem carries a "reference_source" (test-only;
not a DB column, ignored by scripts/seed.py's explicit-key inserts). This
runs that source with the pinned pandas==2.0.3 / numpy==1.24.4 versions --
the same ones baked into the Judge0 image (see
agents/codeforge_agent/judge0-worker-image/Dockerfile) -- against each test
case's stdin and checks it reproduces the stored expected_output exactly.
Falls back to whatever pandas is importable if the pinned versions aren't
installed in this environment (CI's python-quality job doesn't have pandas
at all), so this degrades to a skip rather than a false failure -- the
authoritative check is that the content was generated against the pinned
versions in the first place (see the scratch generator script referenced in
the PR description).
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.problem_catalog import PROBLEMS

PYTHON_LANGUAGE_ID = 71


def _python_with_pandas():
    try:
        import pandas  # noqa: F401
    except ImportError:
        return None
    return sys.executable


PYTHON_BIN = _python_with_pandas()


def run(source, stdin_text):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(source)
        path = f.name
    try:
        result = subprocess.run([PYTHON_BIN, path], input=stdin_text, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, f"python exited {result.returncode}\nstderr: {result.stderr}"
        return result.stdout
    finally:
        Path(path).unlink()


PANDAS_PROBLEMS = [
    problem for problem in PROBLEMS
    if problem["technology"] == "pandas" and problem.get("reference_source")
]

pytestmark = pytest.mark.skipif(PYTHON_BIN is None, reason="pandas is not installed in this environment")


def test_every_pandas_problem_has_a_reference_source():
    missing = [problem["slug"] for problem in PROBLEMS if problem["technology"] == "pandas" and not problem.get("reference_source")]
    assert not missing, f"Pandas problems missing a reference_source for content verification: {missing}"


@pytest.mark.parametrize("problem", PANDAS_PROBLEMS, ids=lambda problem: problem["slug"])
def test_reference_source_reproduces_every_stored_expected_output(problem):
    for index, (stdin_text, expected_output, _hidden, _weight) in enumerate(problem["tests"]):
        actual = run(problem["reference_source"], stdin_text)
        assert actual == expected_output, (
            f"{problem['slug']} test case {index}: reference source produced {actual!r}, "
            f"catalog stores {expected_output!r}"
        )


@pytest.mark.parametrize("problem", PANDAS_PROBLEMS, ids=lambda problem: problem["slug"])
def test_expected_outputs_are_not_trivially_empty(problem):
    for _stdin_text, expected_output, _hidden, _weight in problem["tests"]:
        assert expected_output.strip(), f"{problem['slug']}: a test case expects empty output"

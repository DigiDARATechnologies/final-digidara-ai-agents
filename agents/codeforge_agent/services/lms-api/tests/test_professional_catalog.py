"""Every Professional problem's expected outputs come from running its
reference solution; this re-runs each one (Python, Node, SQLite) so a hand
edit can never leave a wrong expected output."""
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.problem_catalog import PROBLEMS  # noqa: E402
from lms_api.professional_catalog import PRO_PROBLEMS, PRO_TECHNOLOGIES, PRO_TOPICS  # noqa: E402

NODE = shutil.which("node")


def run_source(binary, suffix, source, stdin):
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as f:
        f.write(source)
    try:
        result = subprocess.run([binary, f.name], input=stdin, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stderr
        return result.stdout
    finally:
        Path(f.name).unlink()


def run_sql(fixture, query):
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(fixture)
        rows = []
        statements = [s.strip() for s in query.split(";") if s.strip()]
        for i, statement in enumerate(statements):
            cursor = con.execute(statement)
            if i == len(statements) - 1:
                rows = cursor.fetchall()
        lines = ["|".join("" if v is None else str(v) for v in row) for row in rows]
        return ("\n".join(lines) + "\n") if lines else ""
    finally:
        con.close()


def test_every_language_has_ten_expert_problems_and_five_real_world_tasks():
    for technology in PRO_TECHNOLOGIES:
        mine = [p for p in PRO_PROBLEMS if p["technology"] == technology]
        assert sum(p["kind"] == "expert" for p in mine) == 10, technology
        assert sum(p["kind"] == "real_world" for p in mine) == 5, technology
    topics = {slug for _, slug in PRO_TOPICS}
    assert all(p["topic"] in topics and p["track"] == "professional" for p in PRO_PROBLEMS)


def test_slugs_are_unique_across_all_content():
    slugs = [(p["technology"], p["slug"]) for p in PROBLEMS + PRO_PROBLEMS]
    assert len(slugs) == len(set(slugs))


def test_every_problem_has_hidden_tests_and_inputs_fit_the_column():
    for problem in PRO_PROBLEMS:
        assert any(hidden for _, _, hidden, _ in problem["tests"]), problem["slug"]
        assert all(len(stdin.encode()) < 65535 and len(out.encode()) < 65535 for stdin, out, _, _ in problem["tests"]), problem["slug"]


@pytest.mark.parametrize("problem", [p for p in PRO_PROBLEMS if p["language"] == "python"], ids=lambda p: p["slug"])
def test_python_reference_reproduces_expected_output(problem):
    for stdin, expected, _, _ in problem["tests"]:
        assert run_source(sys.executable, ".py", problem["reference_source"], stdin) == expected


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("problem", [p for p in PRO_PROBLEMS if p["language"] == "javascript"], ids=lambda p: p["slug"])
def test_javascript_reference_reproduces_expected_output(problem):
    for stdin, expected, _, _ in problem["tests"]:
        assert run_source(NODE, ".js", problem["reference_source"], stdin) == expected


@pytest.mark.parametrize("problem", [p for p in PRO_PROBLEMS if p["language"] == "mysql"], ids=lambda p: p["slug"])
def test_sql_reference_reproduces_expected_output(problem):
    for fixture, expected, _, _ in problem["tests"]:
        assert run_sql(fixture, problem["reference_query"]) == expected

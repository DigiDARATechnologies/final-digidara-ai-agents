"""SQL problems (Judge0 language 82) can't vary Judge0's own "stdin" per test
case -- its run_cmd is `cat script.sql | sqlite3 db.sqlite`, and `cat` with a
filename argument never reads its own stdin, so that field is silently
discarded (see the comment on SQL_LANGUAGE_ID in evaluation.py, and the proof:
`printf X | (cat file | cat)` prints only the file's content, never X). Each
SQL test case's data therefore lives in a fixture script stored in
stdin_text, prepended to the student's submitted query."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.evaluation import SQL_LANGUAGE_ID, EvaluationService

PYTHON_PROBLEM = {"id": 1, "judge0_language_id": 71, "max_score": 100}
SQL_PROBLEM = {"id": 2, "judge0_language_id": SQL_LANGUAGE_ID, "max_score": 100}


class FakeRepository:
    def __init__(self, problem, cases):
        self.problem = problem
        self.cases = cases
        self.saved = []

    def problem_for_evaluation(self, student_id, problem_id):
        del student_id, problem_id
        return self.problem

    def evaluation_cases(self, problem_id, include_hidden):
        del problem_id
        return self.cases if include_hidden else [case for case in self.cases if not case["is_hidden"]]

    def save_submission(self, student_id, problem, source_code, mode, outcome):
        self.saved.append((student_id, problem["id"], source_code, mode, outcome))
        return len(self.saved)


class RecordingJudge:
    def __init__(self):
        self.calls = []

    def execute(self, source_code, language_id, stdin_text, expected_output):
        self.calls.append({"source_code": source_code, "language_id": language_id, "stdin_text": stdin_text, "expected_output": expected_output})
        return {"passed": True, "status": "Accepted", "stdout": expected_output, "stderr": "", "compileOutput": "", "message": "", "time": "0.01", "memory": 900}


def test_sql_prepends_the_fixture_and_sends_no_stdin():
    fixture = "CREATE TABLE students(id INT, score INT);\nINSERT INTO students VALUES (1, 90), (2, 70);"
    cases = [{"stdin_text": fixture, "expected_output": "2\n", "is_hidden": False, "score_weight": 1}]
    judge = RecordingJudge()
    service = EvaluationService(FakeRepository(SQL_PROBLEM, cases), judge)

    service.evaluate("student-1", 2, "SELECT COUNT(*) FROM students;", "run")

    assert len(judge.calls) == 1
    assert judge.calls[0]["source_code"] == fixture + "\nSELECT COUNT(*) FROM students;"
    assert judge.calls[0]["stdin_text"] == ""


def test_sql_test_cases_use_independent_fixtures_not_shared_stdin():
    cases = [
        {"stdin_text": "CREATE TABLE t(n INT);\nINSERT INTO t VALUES (1),(2);", "expected_output": "2\n", "is_hidden": False, "score_weight": 1},
        {"stdin_text": "CREATE TABLE t(n INT);\nINSERT INTO t VALUES (1),(2),(3),(4);", "expected_output": "4\n", "is_hidden": True, "score_weight": 1},
    ]
    judge = RecordingJudge()
    service = EvaluationService(FakeRepository(SQL_PROBLEM, cases), judge)

    service.evaluate("student-1", 2, "SELECT COUNT(*) FROM t;", "submit")

    assert len(judge.calls) == 2
    assert "VALUES (1),(2);" in judge.calls[0]["source_code"]
    assert "VALUES (1),(2),(3),(4);" in judge.calls[1]["source_code"]


def test_non_sql_languages_are_unaffected():
    cases = [{"stdin_text": "4 7\n", "expected_output": "11\n", "is_hidden": False, "score_weight": 1}]
    judge = RecordingJudge()
    service = EvaluationService(FakeRepository(PYTHON_PROBLEM, cases), judge)

    service.evaluate("student-1", 1, "a, b = map(int, input().split())\nprint(a + b)", "run")

    assert judge.calls[0]["source_code"] == "a, b = map(int, input().split())\nprint(a + b)"
    assert judge.calls[0]["stdin_text"] == "4 7\n"


def test_a_public_sql_test_shows_its_fixture_as_the_input():
    fixture = "CREATE TABLE t(n INT);\nINSERT INTO t VALUES (5);"
    cases = [{"stdin_text": fixture, "expected_output": "5\n", "is_hidden": False, "score_weight": 1}]
    service = EvaluationService(FakeRepository(SQL_PROBLEM, cases), RecordingJudge())

    outcome = service.evaluate("student-1", 2, "SELECT n FROM t;", "run")

    assert outcome["tests"][0]["input"] == fixture

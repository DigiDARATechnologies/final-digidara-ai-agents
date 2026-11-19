"""A test whose correct answer is "print nothing" (Inheritance Basics with
n = 0, set difference of equal sets) must pass a correct program. Judge0 reports
"printed nothing" as null, which never equalled the expected "", so every
correct solution got Wrong Answer on these tests."""

from lms_api.judge0_client import Judge0Client


class FakeJudge0(Judge0Client):
    """Judge0 as it behaves: compares stdout (null when empty) with expected_output."""

    def __init__(self, stdout):
        self.stdout = stdout
        self.sent = []

    def _request(self, method, path, payload=None, query=None):
        self.sent.append(payload)
        expected = payload["expected_output"]
        accepted = expected is None or expected == self.stdout
        return {"token": "t", "stdout": self.stdout, "stderr": None, "compile_output": None, "message": None,
                "time": "0.01", "memory": 900, "status": {"id": 3 if accepted else 4,
                                                          "description": "Accepted" if accepted else "Wrong Answer"}}


def test_printing_nothing_passes_a_test_that_expects_nothing():
    judge = FakeJudge0(stdout=None)
    result = judge.execute("n = int(input())", 71, "0\n", "")
    assert result["passed"] and result["status"] == "Accepted"
    assert judge.sent[0]["expected_output"] is None


def test_printing_something_fails_a_test_that_expects_nothing():
    result = FakeJudge0(stdout="Woof\n").execute("print('Woof')", 71, "0\n", "")
    assert not result["passed"] and result["status"] == "Wrong Answer"


def test_whitespace_only_output_counts_as_nothing():
    assert FakeJudge0(stdout="\n").execute("print()", 71, "0\n", "\n")["passed"]


def test_ordinary_tests_still_go_to_judge0_unchanged():
    judge = FakeJudge0(stdout="Woof\n")
    assert judge.execute("print('Woof')", 71, "1\n", "Woof\n")["passed"]
    assert judge.sent[0]["expected_output"] == "Woof\n"
    assert not FakeJudge0(stdout="Meow\n").execute("print('Meow')", 71, "1\n", "Woof\n")["passed"]

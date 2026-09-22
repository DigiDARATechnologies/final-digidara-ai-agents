from .errors import ApiError
from .judge0_client import Judge0Client

# Judge0 "SQL (SQLite 3.27.2)" -- db/languages/active.rb:304 in the vendored
# judge0/ checkout. Its run_cmd is `cat script.sql | sqlite3 db.sqlite`: `cat`
# with a filename argument never reads its own stdin, so whatever a submission
# sends as "stdin" is silently discarded -- proven with `printf X | (cat file |
# cat)`, which prints only the file's content. Every other language here reuses
# one submission across differently-parameterized stdin to catch hardcoded
# answers; SQL can't, so its test cases instead store a full fixture script
# (schema + sample rows) in stdin_text, which is prepended to the student's
# submitted query to form the actual script. Nothing is sent to Judge0 as
# stdin for this language.
SQL_LANGUAGE_ID = 82


class EvaluationService:
    def __init__(self, repository, judge=None):
        self.repository = repository
        self.judge = judge or Judge0Client()

    def evaluate(self, student_id, problem_id, source_code, mode):
        if mode not in ("run", "submit"):
            raise ApiError("Evaluation mode is invalid.", 400, "invalid_mode")
        if not isinstance(source_code, str) or not source_code.strip() or len(source_code) > 50000:
            raise ApiError("Source code must contain 1 to 50,000 characters.", 400, "invalid_source")
        problem = self.repository.problem_for_evaluation(student_id, problem_id)
        cases = self.repository.evaluation_cases(problem_id, include_hidden=mode == "submit")
        if not cases:
            raise ApiError("No test cases are configured for this problem.", 409, "tests_unavailable")

        results = []
        passed_weight = 0
        total_weight = sum(int(case["score_weight"]) for case in cases)
        if total_weight <= 0:
            raise ApiError("The problem test weights are invalid.", 409, "invalid_test_weights")
        is_sql = problem["judge0_language_id"] == SQL_LANGUAGE_ID
        for index, case in enumerate(cases, start=1):
            effective_source = f"{case['stdin_text']}\n{source_code}" if is_sql else source_code
            judge_stdin = "" if is_sql else case["stdin_text"]
            result = self.judge.execute(effective_source, problem["judge0_language_id"], judge_stdin, case["expected_output"])
            if result["passed"]:
                passed_weight += int(case["score_weight"])
            hidden = bool(case["is_hidden"])
            results.append({
                "sequence": index,
                "label": f"Hidden test {index}" if hidden else f"Public test {index}",
                "hidden": hidden,
                "passed": result["passed"],
                "status": result["status"],
                "input": None if hidden else case["stdin_text"],
                "expectedOutput": None if hidden else case["expected_output"],
                "actualOutput": None if hidden else result["stdout"],
                "stderr": result["stderr"],
                "compileOutput": result["compileOutput"],
                "message": result["message"],
                "time": result["time"],
                "memory": result["memory"],
            })
        passed_tests = sum(1 for result in results if result["passed"])
        score = round(problem["max_score"] * passed_weight / total_weight) if mode == "submit" else 0
        status = "Accepted" if passed_tests == len(results) else "Partial" if passed_tests else self._failure_status(results)
        outcome = {"status": status, "score": score, "passedTests": passed_tests, "totalTests": len(results), "tests": results}
        submission_id = self.repository.save_submission(student_id, problem, source_code, mode, outcome)
        return {"submissionId": submission_id, "mode": mode, **outcome}

    def health(self):
        return self.judge.health()

    @staticmethod
    def _failure_status(results):
        statuses = {result["status"] for result in results}
        if any("Compilation" in status for status in statuses):
            return "Compilation Error"
        if any("Runtime" in status for status in statuses):
            return "Runtime Error"
        if any("Time Limit" in status for status in statuses):
            return "Time Limit Exceeded"
        if any("Memory Limit" in status for status in statuses):
            return "Memory Limit Exceeded"
        return "Wrong Answer"

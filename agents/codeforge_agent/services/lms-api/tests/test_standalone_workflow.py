import hashlib
import hmac
import json
import sys
import time
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lms_api.app import create_app
from lms_api.evaluation import EvaluationService
from lms_api.errors import ApiError
from lms_api.judge0_client import Judge0Client


STUDENT = {"id": 7, "email": "student@example.com", "display_name": "Test Student", "bio": None, "timezone": "Asia/Kolkata", "is_active": True}
COURSE = {"id": 1, "name": "Data Analytics", "slug": "data-analytics", "description": "Analytics", "icon": "chart", "technology_count": 1}
TECH = {"id": 2, "name": "Python", "slug": "python", "description": "Python", "icon": "PY", "topic_count": 1}
TOPIC = {"id": 3, "name": "Print and Input", "slug": "print-and-input", "description": "Input", "sequence": 1, "problem_count": 1, "progress": "Not Started", "learning_objectives": [], "suggested_concepts": [], "previous": None, "next": None}
PROBLEM = {"id": 1, "name": "Add Two Numbers", "slug": "add-two-numbers", "description": "Add", "input_format": "two integers", "output_format": "sum", "constraints": "small", "examples": [], "starter_code": "", "language_key": "python", "judge0_language_id": 71, "difficulty": "Easy", "max_score": 100, "display_order": 1}


class FakeRepository:
    def __init__(self):
        self.requests = set(); self.sessions = {"valid-session": STUDENT}; self.revoked = set(); self.saved = []; self.tutor_saved = []
    def claim_request(self, request_id, timestamp):
        del timestamp
        if request_id in self.requests: return False
        self.requests.add(request_id); return True
    def register_account(self, email, password, display_name):
        del password
        student = {**STUDENT, "email": email, "display_name": display_name}; self.sessions["registered-session"] = student
        return student, "registered-session", "2099-01-01T00:00:00+00:00"
    def login_account(self, email, password):
        if email != STUDENT["email"] or password != "Password1!": raise ApiError("Email or password is incorrect.", 401, "invalid_credentials")
        return STUDENT, "valid-session", "2099-01-01T00:00:00+00:00"
    def student_for_session(self, token): return None if token in self.revoked else self.sessions.get(token)
    def revoke_session(self, token): self.revoked.add(token)
    def health(self): return True
    def dashboard(self, student_id): return {"courses": self.list_courses(student_id), "continue": {"label": "Coding Practice", "href": "/coding", "kind": "dashboard"}}
    def progress_summary(self, student_id): del student_id; return {"totalProblems": 1, "solvedProblems": 0, "averageScore": 0}
    def list_courses(self, student_id): del student_id; return [COURSE]
    def list_technologies(self, course_slug):
        if course_slug != COURSE["slug"]: raise ApiError("Unavailable", 404, "course_not_found")
        return COURSE, [TECH]
    def list_topics(self, course_slug, technology_slug, student_id=None):
        del student_id
        self.list_technologies(course_slug)
        if technology_slug != TECH["slug"]: raise ApiError("Unavailable", 404, "technology_not_found")
        return COURSE, TECH, [TOPIC]
    def get_topic(self, course_slug, technology_slug, topic_slug):
        self.list_topics(course_slug, technology_slug)
        if topic_slug != TOPIC["slug"]: raise ApiError("Unavailable", 404, "topic_not_found")
        return COURSE, TECH, TOPIC
    def list_problems(self, student_id, course_slug, technology_slug, topic_slug):
        del student_id; course, technology, topic = self.get_topic(course_slug, technology_slug, topic_slug)
        summary = {"id": 1, "name": PROBLEM["name"], "slug": PROBLEM["slug"], "description": "Add", "difficulty": "Easy", "max_score": 100, "language": "python", "sequence": 1, "progress": "Not Started", "best_score": 0, "attempts": 0}
        return course, technology, topic, [summary]
    def problem_for_evaluation(self, student_id, problem_id): del student_id; return PROBLEM if problem_id == 1 else None
    def evaluation_cases(self, problem_id, include_hidden):
        cases = [{"id": 1, "stdin_text": "4 7\n", "expected_output": "11\n", "is_hidden": False, "score_weight": 1, "display_order": 1}, {"id": 2, "stdin_text": "-2 5\n", "expected_output": "3\n", "is_hidden": True, "score_weight": 1, "display_order": 2}]
        return cases if include_hidden else cases[:1]
    def save_submission(self, student_id, problem, source_code, mode, outcome):
        self.saved.append((student_id, problem["id"], source_code, mode, outcome)); return len(self.saved)
    def get_submission(self, student_id, problem_id, submission_id):
        del student_id, problem_id
        saved = self.saved[submission_id - 1]
        return {"id": submission_id, "status": saved[4]["status"], "source_code": saved[2], "result_json": saved[4]["tests"]}
    def save_tutor_interaction(self, *args): self.tutor_saved.append(args)
    def continue_destination(self, student_id): del student_id; return {"label": "Coding Practice", "href": "/coding", "kind": "dashboard"}
    def get_profile(self, student_id): del student_id; return STUDENT
    def update_profile(self, student_id, display_name, bio, timezone): del student_id; return {**STUDENT, "display_name": display_name, "bio": bio, "timezone": timezone}


class FakeJudge:
    def health(self):
        return True

    def execute(self, source_code, language_id, stdin_text, expected_output):
        del language_id, stdin_text
        passed = "print(a + b)" in source_code
        return {"passed": passed, "status": "Accepted" if passed else "Wrong Answer", "stdout": expected_output if passed else "0\n", "stderr": "", "compileOutput": "", "message": "", "time": "0.01", "memory": 1000}


class FailingJudge:
    def health(self):
        return False

    def execute(self, *_args):
        raise ApiError("The secure evaluator worker is unhealthy.", 503, "evaluator_worker_error")


class RecordingJudge0Client(Judge0Client):
    def __init__(self, result):
        self.result = result
        self.calls = []
    def _request(self, method, path, payload=None, query=None):
        self.calls.append((method, path, payload, query))
        return self.result


class StandaloneWorkflowTests(unittest.TestCase):
    secret = "test-shared-secret"
    def setUp(self):
        self.repo = FakeRepository()
        self.app = create_app({"TESTING": True, "LMS_API_SHARED_SECRET": self.secret, "CODING_PRACTICE_ENABLED": True, "SIGNATURE_MAX_AGE_SECONDS": 300}, self.repo)
        self.app.extensions["evaluation"] = EvaluationService(self.repo, FakeJudge())
        self.client = self.app.test_client()
    def signed(self, method, path, payload=None, token="", request_id=None):
        body = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode(); timestamp = str(int(time.time())); request_id = request_id or str(uuid.uuid4())
        session_hash = hashlib.sha256(token.encode()).hexdigest() if token else ""
        canonical = "\n".join((timestamp, request_id, method, path, hashlib.sha256(body).hexdigest(), session_hash))
        headers = {"X-CodeForge-Timestamp": timestamp, "X-CodeForge-Request-Id": request_id, "X-CodeForge-Signature": hmac.new(self.secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()}
        if token: headers["X-CodeForge-Session"] = token
        if body: headers["Content-Type"] = "application/json"
        return headers, body
    def request(self, method, path, payload=None, token="", request_id=None):
        headers, body = self.signed(method, path, payload, token, request_id); return self.client.open(path, method=method, headers=headers, data=body)
    def test_register_login_session_and_logout(self):
        registered = self.request("POST", "/api/auth/register", {"displayName": "Ada", "email": "ada@example.com", "password": "Password1!"})
        login = self.request("POST", "/api/auth/login", {"email": STUDENT["email"], "password": "Password1!"})
        session = self.request("GET", "/api/auth/session", token="valid-session")
        logout = self.request("POST", "/api/auth/logout", {}, token="valid-session")
        expired = self.request("GET", "/api/auth/session", token="valid-session")
        self.assertEqual((registered.status_code, login.status_code, session.status_code, logout.status_code, expired.status_code), (201, 200, 200, 200, 401))
    def test_dashboard_requires_session(self):
        self.assertEqual(self.request("GET", "/api/coding/dashboard").status_code, 401)
        response = self.request("GET", "/api/coding/dashboard", token="valid-session")
        self.assertEqual(response.status_code, 200); self.assertEqual(response.json["progress"]["totalProblems"], 1)
    def test_health_reports_database_and_judge0_status(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["checks"], {"database": "ok", "judge0": "ok"})

        self.app.extensions["evaluation"] = EvaluationService(self.repo, FailingJudge())
        failed = self.client.get("/health")
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(failed.json["checks"]["judge0"], "unavailable")
    def test_run_submit_score_and_tutor(self):
        wrong = self.request("POST", "/api/coding/problems/1/run", {"sourceCode": "print(0)"}, "valid-session")
        guidance = self.request("POST", "/api/coding/problems/1/tutor", {"submissionId": 1, "hintLevel": 2}, "valid-session")
        correct = self.request("POST", "/api/coding/problems/1/submit", {"sourceCode": "a,b=1,2\nprint(a + b)"}, "valid-session")
        self.assertEqual(wrong.json["status"], "Wrong Answer"); self.assertFalse(guidance.json["guidance"]["fullSolutionAllowed"])
        self.assertEqual((correct.json["status"], correct.json["score"], correct.json["passedTests"]), ("Accepted", 100, 2))
        self.assertEqual(len(correct.json["tests"]), 2)
        hidden = correct.json["tests"][1]
        self.assertTrue(hidden["hidden"])
        self.assertIsNone(hidden["input"])
        self.assertIsNone(hidden["expectedOutput"])
        self.assertIsNone(hidden["actualOutput"])
    def test_evaluator_failure_does_not_save_a_submission(self):
        self.app.extensions["evaluation"] = EvaluationService(self.repo, FailingJudge())
        failed = self.request("POST", "/api/coding/problems/1/submit", {"sourceCode": "print(1)"}, "valid-session")
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(failed.json["error"]["code"], "evaluator_worker_error")
        self.assertEqual(self.repo.saved, [])
    def test_judge0_payload_and_internal_error_mapping(self):
        accepted_client = RecordingJudge0Client({"token": "job-1", "status": {"id": 3, "description": "Accepted"}, "stdout": "11\n"})
        with self.app.app_context():
            result = accepted_client.execute("print(11)", 71, "4 7\n", "11\n")
        method, path, payload, query = accepted_client.calls[0]
        self.assertEqual((method, path, query), ("POST", "/submissions", {"base64_encoded": "false", "wait": "true"}))
        self.assertEqual((payload["language_id"], payload["stdin"], payload["expected_output"]), (71, "4 7\n", "11\n"))
        self.assertFalse(payload["enable_network"])
        self.assertTrue(result["passed"])

        unhealthy_client = RecordingJudge0Client({"status": {"id": 13, "description": "Internal Error"}, "message": "sandbox failure"})
        with self.app.app_context(), self.assertRaises(ApiError) as raised:
            unhealthy_client.execute("print(11)", 71, "", "11\n")
        self.assertEqual((raised.exception.status, raised.exception.code), (503, "evaluator_worker_error"))
    def test_replay_and_bad_signature_are_rejected(self):
        request_id = str(uuid.uuid4())
        self.assertEqual(self.request("GET", "/api/coding/courses", token="valid-session", request_id=request_id).status_code, 200)
        self.assertEqual(self.request("GET", "/api/coding/courses", token="valid-session", request_id=request_id).status_code, 401)
    def test_evaluation_status_classifies_common_judge0_errors(self):
        cases = [
            ([{"status": "Compilation Error"}], "Compilation Error"),
            ([{"status": "Runtime Error (NZEC)"}], "Runtime Error"),
            ([{"status": "Time Limit Exceeded"}], "Time Limit Exceeded"),
            ([{"status": "Memory Limit Exceeded"}], "Memory Limit Exceeded"),
            ([{"status": "Wrong Answer"}], "Wrong Answer"),
        ]
        for results, expected in cases:
            self.assertEqual(EvaluationService._failure_status(results), expected)


if __name__ == "__main__": unittest.main()

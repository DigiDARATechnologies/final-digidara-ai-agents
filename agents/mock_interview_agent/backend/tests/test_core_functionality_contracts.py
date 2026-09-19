import ast
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).parents[1]
PROJECT_DIR = BACKEND_DIR.parent
DB_SOURCE = (BACKEND_DIR / "db.py").read_text(encoding="utf-8")
APP_SOURCE = (BACKEND_DIR / "app.py").read_text(encoding="utf-8")
HTTP_CONTEXT_SOURCE = (BACKEND_DIR / "http_context.py").read_text(encoding="utf-8")
INTERVIEWS_SOURCE = (
    BACKEND_DIR / "routes" / "interviews.py"
).read_text(encoding="utf-8")
INTERVIEW_SCREEN = (
    PROJECT_DIR / "frontend" / "src" / "components" / "InterviewScreen.jsx"
).read_text(encoding="utf-8")
SETUP_SCREEN = (
    PROJECT_DIR / "frontend" / "src" / "components" / "SetupScreen.jsx"
).read_text(encoding="utf-8")
CANDIDATE_ANSWER_PANEL = (
    PROJECT_DIR / "frontend" / "src" / "components" / "interview" / "CandidateAnswerPanel.jsx"
).read_text(encoding="utf-8")


def load_db_function(name, get_conn):
    tree = ast.parse(DB_SOURCE)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
)
    namespace = {"get_conn": get_conn}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "db.py", "exec"), namespace)
    return namespace[name]


class FakeConnection:
    def __init__(
        self,
        *,
        fail_first_question=False,
        active_session=False,
        questionless_active=False,
    ):
        self.fail_first_question = fail_first_question
        self.active_session = active_session
        self.questionless_active = questionless_active
        self.started = False
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.cursor_instance = FakeCursor(self)
        self.pending_writes = []
        self.persisted_writes = []

    def cursor(self, dictionary=False):
        return self.cursor_instance

    def start_transaction(self):
        self.started = True

    def commit(self):
        self.committed = True
        self.persisted_writes.extend(self.pending_writes)
        self.pending_writes.clear()

    def rollback(self):
        self.rolled_back = True
        self.pending_writes.clear()

    def close(self):
        self.closed = True


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.lastrowid = 42
        self.rowcount = 1
        self.closed = False
        self.statements = []
        self.last_sql = ""

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.last_sql = normalized
        self.statements.append((normalized, params))
        if normalized.startswith(("INSERT ", "UPDATE ", "DELETE ")):
            self.connection.pending_writes.append((normalized, params))
        if (
            self.connection.fail_first_question
            and "INSERT INTO interview_details" in normalized
        ):
            raise RuntimeError("simulated first-question insert failure")

    def fetchone(self):
        if "SELECT id FROM students" in self.last_sql:
            return {"id": 1}
        if "FROM interviews" in self.last_sql:
            if not self.connection.active_session:
                return None
            return {
                "id": 7,
                "round_type": "technical",
                "difficulty": "intermediate",
                "num_questions": 5,
            }
        if "SELECT question_order" in self.last_sql:
            if self.connection.questionless_active:
                return None
            return {
                "question_order": 3,
                "question": "Existing question?",
                "is_followup": 0,
            }
        if "real_question_index" in self.last_sql:
            return {"real_question_index": 3}
        return None

    def close(self):
        self.closed = True


class AtomicInterviewCreationTests(unittest.TestCase):
    def test_first_question_failure_rolls_back_the_interview_insert(self):
        connection = FakeConnection(fail_first_question=True)
        create_or_resume = load_db_function(
            "create_or_resume_interview", lambda: connection
        )

        with self.assertRaisesRegex(RuntimeError, "first-question insert failure"):
            create_or_resume(1, "technical", "Python", "beginner", 5, "Question?")

        self.assertTrue(connection.started)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)
        self.assertEqual(connection.persisted_writes, [])
        self.assertEqual(connection.pending_writes, [])
        self.assertTrue(connection.closed)
        self.assertTrue(connection.cursor_instance.closed)

    def test_concurrent_start_resumes_the_locked_active_session(self):
        connection = FakeConnection(active_session=True)
        create_or_resume = load_db_function(
            "create_or_resume_interview", lambda: connection
        )

        result = create_or_resume(
            1, "technical", "React", "advanced", 10, "Unused generated question?"
        )

        self.assertFalse(result["created"])
        self.assertEqual(result["interview_id"], 7)
        self.assertEqual(result["question_order"], 3)
        self.assertTrue(connection.committed)
        self.assertTrue(any(
            "SELECT id FROM students" in sql and "FOR UPDATE" in sql
            for sql, _ in connection.cursor_instance.statements
        ))
        self.assertFalse(any(
            "INSERT INTO interviews" in sql
            for sql, _ in connection.cursor_instance.statements
        ))

    def test_questionless_replacement_rolls_back_old_status_and_new_rows(self):
        connection = FakeConnection(
            fail_first_question=True,
            active_session=True,
            questionless_active=True,
        )
        create_or_resume = load_db_function(
            "create_or_resume_interview", lambda: connection
        )

        with self.assertRaisesRegex(RuntimeError, "first-question insert failure"):
            create_or_resume(1, "technical", "Python", "beginner", 5, "Question?")

        self.assertTrue(any(
            "SET status = 'exited'" in sql
            for sql, _ in connection.cursor_instance.statements
        ))
        self.assertTrue(connection.rolled_back)
        self.assertEqual(connection.persisted_writes, [])


class CrossLayerLifecycleContractTests(unittest.TestCase):
    def test_start_route_uses_atomic_create_or_resume_helper(self):
        self.assertIn("db.create_or_resume_interview(", INTERVIEWS_SOURCE)
        self.assertIn('"resumed_existing": True', INTERVIEWS_SOURCE)
        self.assertIn("realQuestionIndex: res.real_question_index || 1", SETUP_SCREEN)
        tree = ast.parse(INTERVIEWS_SOURCE)
        start_node = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "start_interview"
        )
        start_source = ast.get_source_segment(INTERVIEWS_SOURCE, start_node)
        self.assertNotIn("db.execute_update", start_source)

    def test_request_ids_and_structured_logging_are_wired(self):
        self.assertIn('@app.before_request', HTTP_CONTEXT_SOURCE)
        self.assertIn('response.headers["X-Request-ID"]', HTTP_CONTEXT_SOURCE)
        self.assertNotIn("app.logger.exception", HTTP_CONTEXT_SOURCE)
        self.assertIn("register_http_context(app)", APP_SOURCE)

    def test_exit_route_checks_the_affected_row_count(self):
        self.assertIn("affected = db.execute_update(", INTERVIEWS_SOURCE)
        self.assertIn("if affected != 1:", INTERVIEWS_SOURCE)

    def test_manual_answer_fallback_uses_the_normal_submission_path(self):
        self.assertIn("isSpeechRecognitionSupported", INTERVIEW_SCREEN)
        self.assertIn('id="manual-interview-answer"', CANDIDATE_ANSWER_PANEL)
        self.assertIn("onAnswerReadyRef.current(typedAnswer, { timedOut: false })", (
            PROJECT_DIR / "frontend" / "src" / "hooks" / "useAnswerCapture.js"
        ).read_text(encoding="utf-8"))
        self.assertIn("maxLength={20000}", CANDIDATE_ANSWER_PANEL)


if __name__ == "__main__":
    unittest.main()

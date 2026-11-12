import unittest
from unittest.mock import patch

from flask import Flask

from services.interview_evaluation_lock import interview_evaluation_lock


class FakeCursor:
    def __init__(self, lock_result):
        self.lock_result = lock_result
        self.statements = []
        self.closed = False

    def execute(self, sql, params):
        self.statements.append((sql, params))

    def fetchone(self):
        return (self.lock_result,)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, lock_result):
        self.fake_cursor = FakeCursor(lock_result)
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


class InterviewEvaluationLockTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = False

    def test_acquired_lock_is_released_and_connection_is_closed(self):
        connection = FakeConnection(1)
        with self.app.app_context(), patch(
            "services.interview_evaluation_lock.db.get_conn", return_value=connection
        ):
            with interview_evaluation_lock(42) as acquired:
                self.assertTrue(acquired)

        self.assertEqual(connection.fake_cursor.statements, [
            ("SELECT GET_LOCK(%s, 0)", ("mi_final_eval:42",)),
            ("SELECT RELEASE_LOCK(%s)", ("mi_final_eval:42",)),
        ])
        self.assertTrue(connection.fake_cursor.closed)
        self.assertTrue(connection.closed)

    def test_busy_lock_is_reported_without_running_a_duplicate_evaluation(self):
        connection = FakeConnection(0)
        with self.app.app_context(), patch(
            "services.interview_evaluation_lock.db.get_conn", return_value=connection
        ):
            with interview_evaluation_lock(42) as acquired:
                self.assertFalse(acquired)

        self.assertEqual(len(connection.fake_cursor.statements), 1)
        self.assertTrue(connection.closed)


if __name__ == "__main__":
    unittest.main()

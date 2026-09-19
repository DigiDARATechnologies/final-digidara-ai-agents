import unittest
from unittest.mock import Mock, patch

from services import background_question_search as background


class _Cursor:
    def __init__(self, status="in_progress", pending=None):
        self.status = status
        self.pending = pending or []
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def fetchone(self):
        return {"status": self.status} if self.status else None

    def fetchall(self):
        return list(self.pending)

    def close(self):
        pass


class _Connection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.committed = False
        self.rolled_back = False

    def cursor(self, **_kwargs):
        return self.cursor_value

    def start_transaction(self):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class BackgroundQuestionSearchTests(unittest.TestCase):
    def test_upgrades_only_future_slots_and_leaves_current_slot_unchanged(self):
        cursor = _Cursor(pending=[
            {"id": 10, "question_order": 1},
            {"id": 11, "question_order": 2},
            {"id": 12, "question_order": 3},
        ])
        conn = _Connection(cursor)
        real = [{"question": "Real question one?"}, {"question": "Real question two?"}]
        with patch.object(background.db, "get_conn", return_value=conn):
            result = background.upgrade_unserved_questions_with_real(5, real)

        updates = [params for sql, params in cursor.executed if sql.lstrip().startswith("UPDATE")]
        self.assertEqual(result["upgraded"], 2)
        self.assertEqual([params[-1] for params in updates], [11, 12])
        self.assertTrue(conn.committed)

    def test_completed_interview_discards_late_search_results(self):
        cursor = _Cursor(status="completed")
        conn = _Connection(cursor)
        with patch.object(background.db, "get_conn", return_value=conn):
            result = background.upgrade_unserved_questions_with_real(
                5, [{"question": "Too late?"}]
            )

        self.assertEqual(result, {"upgraded": 0, "skipped": 1, "reason": "interview_not_active"})
        self.assertFalse(any(sql.lstrip().startswith("UPDATE") for sql, _ in cursor.executed))

    def test_schedule_returns_immediately_without_running_search_in_request_thread(self):
        executor = Mock()
        future = object()
        executor.submit.return_value = future
        with patch.object(background, "_executor", executor):
            returned = background.schedule_live_question_search(
                7, "Data Analyst", "beginner", "technical", 5, [], set()
            )

        self.assertIs(returned, future)
        executor.submit.assert_called_once()


if __name__ == "__main__":
    unittest.main()

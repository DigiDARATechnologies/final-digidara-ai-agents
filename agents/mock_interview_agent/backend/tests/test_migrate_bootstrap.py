"""Base-schema bootstrap: only on an empty database, tolerant of races."""
import os
import re
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("OPENAI_API_KEY", "test-unused")

import db  # noqa: E402
import migrate  # noqa: E402


class FakeCursor:
    def __init__(self, has_students, fail_on=None):
        self.has_students = has_students
        self.fail_on = fail_on or {}
        self.executed = []
        self.with_rows = False
        self.drained = 0
        self.closed = False
        self.ledger_rows = []

    def execute(self, statement):
        self.executed.append(statement)
        self.with_rows = statement.upper().startswith(("SHOW", "SELECT"))
        for prefix, errno in self.fail_on.items():
            if statement.startswith(prefix):
                error = Exception("boom")
                error.errno = errno
                raise error

    def executemany(self, statement, rows):
        self.ledger_statement = statement
        self.ledger_rows = list(rows)

    def fetchall(self):
        self.drained += 1
        if self.executed[-1].startswith("SHOW TABLES LIKE"):
            return [("students",)] if self.has_students else []
        return []

    def close(self):
        self.closed = True


def run_bootstrap(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    with patch.object(db, "get_conn", return_value=conn):
        migrate.bootstrap_base_schema()
    return conn


class BootstrapTests(unittest.TestCase):
    def test_existing_database_is_left_alone(self):
        cursor = FakeCursor(has_students=True)
        conn = run_bootstrap(cursor)
        self.assertEqual(len(cursor.executed), 1)
        self.assertEqual(cursor.ledger_rows, [])
        conn.commit.assert_not_called()
        self.assertTrue(cursor.closed)

    def test_empty_database_gets_the_schema_without_switching_database(self):
        cursor = FakeCursor(has_students=False)
        conn = run_bootstrap(cursor)
        joined = "\n".join(cursor.executed).upper()
        self.assertIn("CREATE TABLE IF NOT EXISTS STUDENTS", joined)
        # schema.sql glues "-- comment" lines onto CREATE DATABASE / USE, so
        # check the text itself rather than only the start of each statement.
        for statement in cursor.executed:
            self.assertNotIn("CREATE DATABASE", statement.upper())
            self.assertIsNone(re.search(r"(^|\n)\s*USE\s", statement, re.I))
            self.assertFalse(statement.lstrip().startswith("--"))
        conn.commit.assert_called_once()

    def test_fresh_install_records_every_shipped_migration_as_applied(self):
        cursor = FakeCursor(has_students=False)
        run_bootstrap(cursor)
        shipped = sorted(path.name for path in migrate.MIGRATIONS_DIR.glob("*.sql"))
        self.assertGreater(len(shipped), 10)
        self.assertEqual([name for (name,) in cursor.ledger_rows], shipped)
        self.assertIn("INSERT IGNORE INTO schema_migrations", cursor.ledger_statement)

    def test_row_returning_statements_are_read(self):
        cursor = FakeCursor(has_students=False)
        run_bootstrap(cursor)
        returning = [s for s in cursor.executed if s.upper().startswith(("SHOW", "SELECT"))]
        self.assertGreater(len(returning), 1)  # SHOW TABLES LIKE + schema.sql's own SHOW TABLES
        self.assertEqual(cursor.drained, len(returning))

    def test_already_exists_errors_from_a_concurrent_worker_are_ignored(self):
        cursor = FakeCursor(has_students=False, fail_on={"RENAME TABLE": 1050, "ALTER TABLE": 1060})
        conn = run_bootstrap(cursor)
        conn.commit.assert_called_once()

    def test_other_errors_propagate_and_still_close(self):
        cursor = FakeCursor(has_students=False, fail_on={"RENAME TABLE": 1064})
        with self.assertRaises(Exception):
            run_bootstrap(cursor)
        self.assertTrue(cursor.closed)


class ExecutableStatementsTests(unittest.TestCase):
    def test_leading_comments_are_removed_but_inner_ones_kept(self):
        self.assertEqual(migrate.strip_leading_comments("-- header\n\n# note\nUSE mock_interview_db"), "USE mock_interview_db")
        self.assertEqual(migrate.strip_leading_comments("SELECT 1 -- inline\n, 2"), "SELECT 1 -- inline\n, 2")
        self.assertEqual(migrate.strip_leading_comments("-- only a comment"), "")

    def test_use_and_create_database_are_dropped_even_behind_comments(self):
        sql = "-- header\nCREATE DATABASE IF NOT EXISTS x;\n-- switch\nUSE x;\nuse x;\nALTER TABLE t ADD COLUMN c INT;\n"
        self.assertEqual(migrate.executable_statements(sql), ["ALTER TABLE t ADD COLUMN c INT"])

    def test_every_shipped_migration_is_free_of_hardcoded_database_switches(self):
        for path in migrate.MIGRATIONS_DIR.glob("*.sql"):
            for statement in migrate.executable_statements(path.read_text(encoding="utf-8")):
                self.assertFalse(statement.upper().startswith(("USE ", "CREATE DATABASE")), path.name)


class PoolSizeTests(unittest.TestCase):
    def test_pool_size_is_capped_for_the_shared_mysql_server(self):
        self.assertEqual(db.pool_size_from_env("10"), 4)  # a stale .env value
        self.assertEqual(db.pool_size_from_env("2"), 2)
        self.assertEqual(db.pool_size_from_env(None), 4)
        self.assertEqual(db.pool_size_from_env("abc"), 4)
        self.assertEqual(db.pool_size_from_env("0"), 1)


if __name__ == "__main__":
    unittest.main()

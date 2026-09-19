import re
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).parents[1]
PROJECT_DIR = BACKEND_DIR.parent
SCHEMA = (BACKEND_DIR / "schema.sql").read_text(encoding="utf-8")
BACKEND_SETTINGS = (BACKEND_DIR / "settings.py").read_text(encoding="utf-8")
SETUP_SCREEN = (
    PROJECT_DIR / "frontend" / "src" / "components" / "SetupScreen.jsx"
).read_text(encoding="utf-8")
MIGRATIONS_DIR = BACKEND_DIR / "migrations"


class SchemaTests(unittest.TestCase):
    def test_schema_migration_ledger_exists(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS schema_migrations", SCHEMA)
        self.assertIn("PRIMARY KEY (migration_name)", SCHEMA)

    def test_score_and_usage_check_constraints_exist(self):
        for constraint_name in (
            "chk_interviews_overall_score",
            "chk_interviews_technical_accuracy",
            "chk_interviews_communication_clarity",
            "chk_interviews_confidence",
            "chk_daily_usage_answered_count_nonnegative",
        ):
            with self.subTest(constraint=constraint_name):
                self.assertIn(f"CONSTRAINT {constraint_name}", SCHEMA)

    def test_interview_state_columns_are_not_nullable(self):
        self.assertRegex(
            SCHEMA,
            r"status ENUM\('in_progress', 'completed', 'exited'\)\s+"
            r"NOT NULL DEFAULT 'in_progress'",
        )
        self.assertIn("is_followup TINYINT(1) NOT NULL DEFAULT 0", SCHEMA)

    def test_schema_hardening_changes_have_separate_migrations(self):
        expected = (
            "20260803_create_schema_migrations.sql",
            "20260803_add_data_check_constraints.sql",
            "20260803_make_interview_state_columns_not_null.sql",
        )
        for migration_name in expected:
            with self.subTest(migration=migration_name):
                self.assertTrue((MIGRATIONS_DIR / migration_name).is_file())

    def test_focus_events_schema_and_dated_migration_exist(self):
        migration = MIGRATIONS_DIR / "20260804_add_interview_focus_events.sql"
        self.assertTrue(migration.is_file())
        self.assertIn("CREATE TABLE IF NOT EXISTS interview_focus_events", SCHEMA)
        self.assertIn("UNIQUE KEY uq_interview_focus_event_uuid (event_uuid)", SCHEMA)
        self.assertIn("KEY idx_focus_events_interview_left_at", SCHEMA)
        self.assertIn("CONSTRAINT focus_events_interview_fk", SCHEMA)
        self.assertIn("CONSTRAINT chk_focus_event_away_seconds", SCHEMA)
        self.assertIn(
            "'20260804_add_interview_focus_events.sql'",
            migration.read_text(encoding="utf-8"),
        )

    def test_exit_status_is_supported(self):
        self.assertIn(
            "ENUM('in_progress', 'completed', 'exited')",
            SCHEMA,
        )

    def test_daily_usage_has_one_authoritative_table(self):
        self.assertEqual(
            SCHEMA.count("CREATE TABLE IF NOT EXISTS daily_usage"),
            1,
        )

    def test_question_order_index_matches_live_schema(self):
        self.assertIn(
            "UNIQUE KEY uq_interview_question_order "
            "(interview_id, question_order)",
            SCHEMA,
        )

    def test_daily_usage_cleanup_event_matches_live_schema(self):
        self.assertIn("CREATE EVENT cleanup_old_daily_usage", SCHEMA)

    def test_processing_recovery_columns_exist(self):
        self.assertIn("processing_status", SCHEMA)
        self.assertIn("processing_error", SCHEMA)

    def test_student_avatar_url_exists(self):
        self.assertIn("avatar_url VARCHAR(255) NULL DEFAULT NULL", SCHEMA)

    def test_topic_area_column_and_migration_exist(self):
        migration = MIGRATIONS_DIR / "20260806_add_interview_topic_area.sql"
        self.assertTrue(migration.is_file())
        self.assertIn("topic_area VARCHAR(100) NULL DEFAULT NULL", SCHEMA)
        migration_sql = migration.read_text(encoding="utf-8")
        self.assertIn("ADD COLUMN topic_area VARCHAR(100)", migration_sql)
        self.assertIn("'20260806_add_interview_topic_area.sql'", migration_sql)

    def test_custom_subject_accepts_150_characters_across_all_layers(self):
        long_custom_topic = "x" * 150

        schema_limit = int(
            re.search(r"subject VARCHAR\((\d+)\)", SCHEMA).group(1)
        )
        backend_limit = int(
            re.search(
                r"MAX_SUBJECT_LENGTH\s*=\s*(\d+)",
                BACKEND_SETTINGS,
            ).group(1)
        )
        frontend_limit = int(
            re.search(r"maxLength=\{(\d+)\}", SETUP_SCREEN).group(1)
        )

        self.assertEqual(len(long_custom_topic), 150)
        self.assertEqual(
            (schema_limit, backend_limit, frontend_limit),
            (150, 150, 150),
        )
        self.assertLessEqual(len(long_custom_topic), schema_limit)


if __name__ == "__main__":
    unittest.main()

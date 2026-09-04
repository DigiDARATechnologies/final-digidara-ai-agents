DROP TABLE IF EXISTS tutor_interactions;
-- statement-breakpoint
DROP TABLE IF EXISTS student_problem_progress;
-- statement-breakpoint
DROP TABLE IF EXISTS coding_submissions;
-- statement-breakpoint
DROP TABLE IF EXISTS coding_test_cases;
-- statement-breakpoint
DROP TABLE IF EXISTS coding_problems;
-- statement-breakpoint
DROP TABLE IF EXISTS student_sessions;
-- statement-breakpoint
ALTER TABLE students DROP COLUMN password_hash;
-- statement-breakpoint
DELETE FROM schema_migrations WHERE version = '002_standalone_practice';

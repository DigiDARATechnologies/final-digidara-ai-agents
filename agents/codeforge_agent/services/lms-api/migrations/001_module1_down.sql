DROP TABLE IF EXISTS api_request_nonces;
-- statement-breakpoint
DROP TABLE IF EXISTS student_coding_activity;
-- statement-breakpoint
DROP TABLE IF EXISTS course_technologies;
-- statement-breakpoint
DROP TABLE IF EXISTS coding_topics;
-- statement-breakpoint
DROP TABLE IF EXISTS coding_technologies;
-- statement-breakpoint
DROP TABLE IF EXISTS coding_courses;
-- statement-breakpoint
DROP TABLE IF EXISTS students;
-- statement-breakpoint
DELETE FROM schema_migrations WHERE version = '001_module1';

-- Make lifecycle fields mandatory after confirming the live data contains no NULLs.
-- Preflight repeated immediately before application on 2026-08-03: both NULL counts were zero.
USE mock_interview_db;

ALTER TABLE interviews
  MODIFY COLUMN status ENUM('in_progress', 'completed', 'exited')
    NOT NULL DEFAULT 'in_progress';

ALTER TABLE interview_details
  MODIFY COLUMN is_followup TINYINT(1)
    NOT NULL DEFAULT 0;

INSERT IGNORE INTO schema_migrations (migration_name)
VALUES ('20260803_make_interview_state_columns_not_null.sql');

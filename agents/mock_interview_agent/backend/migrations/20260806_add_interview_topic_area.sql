-- Store a concise semantic area for main interview questions.
-- Existing questions and follow-ups remain NULL until classified or generated.
USE mock_interview_db;

ALTER TABLE interview_details
  ADD COLUMN topic_area VARCHAR(100)
    NULL DEFAULT NULL
    AFTER question;

INSERT IGNORE INTO schema_migrations (migration_name)
VALUES ('20260806_add_interview_topic_area.sql');

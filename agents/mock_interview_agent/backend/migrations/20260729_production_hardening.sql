-- Apply once to an existing database before deploying the hardened backend.
USE mock_interview_db;

ALTER TABLE interviews
  MODIFY COLUMN status
    ENUM('in_progress', 'completed', 'exited')
    NULL DEFAULT 'in_progress';

ALTER TABLE interview_details
  ADD COLUMN processing_status VARCHAR(32)
    NOT NULL DEFAULT 'question_ready' AFTER created_at,
  ADD COLUMN answered_at TIMESTAMP NULL DEFAULT NULL AFTER processing_status,
  ADD COLUMN processing_error TEXT NULL AFTER answered_at;

-- Normalize installations where processing_status was previously introduced
-- as an ENUM that cannot represent all recovery states.
ALTER TABLE interview_details
  MODIFY COLUMN processing_status VARCHAR(32)
    NOT NULL DEFAULT 'question_ready';

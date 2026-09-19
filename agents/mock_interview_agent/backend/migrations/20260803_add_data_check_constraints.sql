-- Reject invalid score and usage-count values at the database boundary.
-- Preflight on 2026-08-03 found no existing rows that violate these checks.
USE mock_interview_db;

ALTER TABLE interviews
  ADD CONSTRAINT chk_interviews_overall_score
    CHECK (overall_score IS NULL OR overall_score BETWEEN 0 AND 10),
  ADD CONSTRAINT chk_interviews_technical_accuracy
    CHECK (technical_accuracy IS NULL OR technical_accuracy BETWEEN 0 AND 10),
  ADD CONSTRAINT chk_interviews_communication_clarity
    CHECK (communication_clarity IS NULL OR communication_clarity BETWEEN 0 AND 10),
  ADD CONSTRAINT chk_interviews_confidence
    CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 10);

ALTER TABLE daily_usage
  ADD CONSTRAINT chk_daily_usage_answered_count_nonnegative
    CHECK (answered_count >= 0);

INSERT IGNORE INTO schema_migrations (migration_name)
VALUES ('20260803_add_data_check_constraints.sql');

-- Allow descriptive custom interview topics up to the application limit.
-- Applied to the live database on 2026-08-01 at 16:48:42 IST.
USE mock_interview_db;

ALTER TABLE interviews
  MODIFY COLUMN subject VARCHAR(150) NULL DEFAULT NULL;

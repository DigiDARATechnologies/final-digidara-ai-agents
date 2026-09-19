-- Add profile-photo support to existing installations.
USE mock_interview_db;

ALTER TABLE students
  ADD COLUMN avatar_url VARCHAR(255) NULL DEFAULT NULL AFTER avatar_color;

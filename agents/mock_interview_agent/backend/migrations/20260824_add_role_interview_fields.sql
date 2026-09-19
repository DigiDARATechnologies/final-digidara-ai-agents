ALTER TABLE interviews
  ADD COLUMN interview_mode VARCHAR(32) NOT NULL DEFAULT 'course' AFTER round_type,
  ADD COLUMN role_name VARCHAR(150) NULL AFTER subject,
  ADD COLUMN resolved_subjects JSON NULL AFTER role_name;

ALTER TABLE interview_details
  ADD COLUMN subject_tag VARCHAR(150) NULL AFTER topic_area;

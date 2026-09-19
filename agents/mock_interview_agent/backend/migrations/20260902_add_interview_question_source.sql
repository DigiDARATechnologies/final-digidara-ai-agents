ALTER TABLE interview_details
  ADD COLUMN question_source VARCHAR(20) NOT NULL DEFAULT 'ai_generated' AFTER question;

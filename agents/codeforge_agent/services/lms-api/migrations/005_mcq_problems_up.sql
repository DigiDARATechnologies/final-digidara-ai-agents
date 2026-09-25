ALTER TABLE coding_problems
  ADD COLUMN question_type ENUM('code','mcq') NOT NULL DEFAULT 'code' AFTER language_key,
  ADD COLUMN mcq_options_json JSON NULL AFTER question_type,
  ADD COLUMN mcq_correct_key VARCHAR(4) NULL AFTER mcq_options_json,
  ADD COLUMN mcq_explanation TEXT NULL AFTER mcq_correct_key,
  MODIFY COLUMN judge0_language_id INT UNSIGNED NULL,
  MODIFY COLUMN starter_code MEDIUMTEXT NULL;

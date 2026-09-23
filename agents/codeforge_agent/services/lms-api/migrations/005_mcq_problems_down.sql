-- Only safe if no row currently has question_type='mcq' (those rows have
-- NULL judge0_language_id/starter_code, which the restored NOT NULL would reject).
ALTER TABLE coding_problems
  MODIFY COLUMN judge0_language_id INT UNSIGNED NOT NULL,
  MODIFY COLUMN starter_code MEDIUMTEXT NOT NULL,
  DROP COLUMN mcq_explanation,
  DROP COLUMN mcq_correct_key,
  DROP COLUMN mcq_options_json,
  DROP COLUMN question_type;

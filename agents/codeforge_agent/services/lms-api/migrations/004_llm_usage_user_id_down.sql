ALTER TABLE llm_usage
  DROP KEY idx_llm_usage_user_id,
  DROP COLUMN user_id;

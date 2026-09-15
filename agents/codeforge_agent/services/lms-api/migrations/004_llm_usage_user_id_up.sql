ALTER TABLE llm_usage
  ADD COLUMN user_id VARCHAR(128) NULL AFTER id,
  ADD KEY idx_llm_usage_user_id (user_id);

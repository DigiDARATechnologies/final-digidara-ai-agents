USE communication_module;

ALTER TABLE speaking_sessions
  ADD COLUMN topic_description VARCHAR(500) NULL AFTER topic_title,
  ADD COLUMN daily_category VARCHAR(120) NULL AFTER topic_title,
  ADD COLUMN answered_turns INT DEFAULT 0 AFTER total_turns,
  ADD COLUMN ended_by_user BOOLEAN NOT NULL DEFAULT FALSE AFTER answered_turns;

ALTER TABLE speaking_turns
  ADD COLUMN corrected_answer TEXT NULL AFTER user_answer,
  ADD COLUMN better_natural_answer TEXT NULL AFTER corrected_answer,
  ADD COLUMN feedback_json TEXT NULL AFTER better_natural_answer,
  ADD COLUMN overall_score FLOAT NULL AFTER knowledge_score;

UPDATE speaking_sessions
SET answered_turns = (
  SELECT COUNT(*)
  FROM speaking_turns
  WHERE speaking_turns.session_id = speaking_sessions.id
    AND speaking_turns.user_answer IS NOT NULL
    AND speaking_turns.user_answer <> ''
)
WHERE answered_turns IS NULL OR answered_turns = 0;

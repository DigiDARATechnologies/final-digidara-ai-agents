USE communication_module;

ALTER TABLE speaking_turns
  ADD COLUMN submission_id VARCHAR(160) NULL AFTER answer_time_seconds,
  ADD COLUMN submission_response_json LONGTEXT NULL AFTER submission_id;

CREATE UNIQUE INDEX uq_speaking_turn_submission
  ON speaking_turns (session_id, submission_id);

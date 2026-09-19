CREATE TABLE IF NOT EXISTS user_question_history (
  id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  round_type ENUM('technical','hr') NOT NULL,
  role_or_topic VARCHAR(255) NOT NULL,
  difficulty ENUM('beginner','intermediate','advanced') NOT NULL,
  question_text TEXT NOT NULL,
  question_hash VARCHAR(64) NOT NULL,
  source VARCHAR(20) NOT NULL,
  interview_session_id INT NOT NULL,
  served_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_round_topic (user_id, round_type, role_or_topic, served_at),
  INDEX idx_history_session (interview_session_id),
  CONSTRAINT fk_history_interview FOREIGN KEY (interview_session_id) REFERENCES interviews(id)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4;

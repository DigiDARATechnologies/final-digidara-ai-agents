USE communication_module;

CREATE TABLE IF NOT EXISTS generated_topics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    public_id VARCHAR(64) NOT NULL UNIQUE,
    user_id INT NOT NULL,
    practice_type VARCHAR(20) NOT NULL,
    mode VARCHAR(30) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description VARCHAR(500) NOT NULL,
    expected_duration_seconds INT,
    minimum_word_count INT,
    maximum_word_count INT,
    source VARCHAR(20) NOT NULL DEFAULT 'groq',
    used_in_session BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_generated_topics_user_context (user_id, practice_type, mode, difficulty, created_at),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

ALTER TABLE speaking_sessions
  ADD COLUMN generated_topic_id VARCHAR(64) NULL AFTER mode;

ALTER TABLE writing_sessions
  ADD COLUMN generated_topic_id VARCHAR(64) NULL AFTER mode,
  ADD COLUMN topic_description VARCHAR(500) NULL AFTER topic_title;

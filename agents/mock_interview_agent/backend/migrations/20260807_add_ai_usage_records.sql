CREATE TABLE IF NOT EXISTS ai_usage_records (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    student_id INT NULL,
    interview_id INT NULL,
    question_id INT NULL,
    provider VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    prompt_tokens INT UNSIGNED NOT NULL DEFAULT 0,
    completion_tokens INT UNSIGNED NOT NULL DEFAULT 0,
    total_tokens INT UNSIGNED NOT NULL DEFAULT 0,
    estimated_cost DECIMAL(14, 8) NOT NULL DEFAULT 0,
    request_type VARCHAR(64) NOT NULL,
    response_time_ms INT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_ai_usage_student_created (student_id, created_at),
    KEY idx_ai_usage_interview (interview_id),
    KEY idx_ai_usage_question (question_id),
    CONSTRAINT fk_ai_usage_student FOREIGN KEY (student_id)
      REFERENCES students (id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_usage_interview FOREIGN KEY (interview_id)
      REFERENCES interviews (id) ON DELETE SET NULL,
    CONSTRAINT fk_ai_usage_question FOREIGN KEY (question_id)
      REFERENCES interview_details (id) ON DELETE SET NULL,
    CONSTRAINT chk_ai_usage_tokens_nonnegative CHECK (
      prompt_tokens >= 0 AND completion_tokens >= 0 AND total_tokens >= 0
    )
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

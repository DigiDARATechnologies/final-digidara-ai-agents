CREATE TABLE IF NOT EXISTS daily_challenge_progress (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    challenge_date DATE NOT NULL,
    activity_type VARCHAR(80) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'not_started',
    source_session_id INT NULL,
    source_result_id INT NULL,
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    xp_awarded INT NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_daily_challenge_progress_user_date_activity (user_id, challenge_date, activity_type),
    INDEX idx_daily_challenge_progress_user_date (user_id, challenge_date),
    CONSTRAINT fk_daily_challenge_progress_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS daily_challenge_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    challenge_date DATE NOT NULL,
    completed_count INT NOT NULL DEFAULT 0,
    total_count INT NOT NULL DEFAULT 3,
    all_completed BOOLEAN NOT NULL DEFAULT FALSE,
    bonus_xp_awarded INT NOT NULL DEFAULT 0,
    completed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_daily_challenge_summary_user_date (user_id, challenge_date),
    INDEX idx_daily_challenge_summary_user_date (user_id, challenge_date),
    CONSTRAINT fk_daily_challenge_summary_user FOREIGN KEY (user_id) REFERENCES users(id)
);

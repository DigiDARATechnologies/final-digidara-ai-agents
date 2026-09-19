-- Fresh-install schema matching the live MySQL 8 database structure.
-- Existing installations should use files in backend/migrations as applicable.
-- AUTO_INCREMENT counters and object DEFINER clauses are intentionally omitted
-- because they are data/environment state, not portable schema structure.

CREATE DATABASE IF NOT EXISTS mock_interview_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE mock_interview_db;

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (migration_name)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS students (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    phone VARCHAR(20) NULL DEFAULT NULL,
    course_enrolled VARCHAR(150) NULL DEFAULT NULL,
    target_role VARCHAR(100) NULL DEFAULT NULL,
    bio TEXT NULL,
    avatar_color VARCHAR(7) NULL DEFAULT '#4dd8c8',
    avatar_url VARCHAR(255) NULL DEFAULT NULL,
    updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP
      ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY email (email)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS interviews (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    round_type ENUM('technical', 'hr') NOT NULL,
    interview_mode VARCHAR(32) NOT NULL DEFAULT 'course',
    subject VARCHAR(150) NULL DEFAULT NULL,
    role_name VARCHAR(150) NULL DEFAULT NULL,
    resolved_subjects JSON NULL DEFAULT NULL,
    difficulty ENUM('beginner', 'intermediate', 'advanced') NOT NULL,
    num_questions TINYINT NOT NULL DEFAULT 5,
    status ENUM('in_progress', 'completed', 'exited')
      NOT NULL DEFAULT 'in_progress',
    overall_score DECIMAL(3,1) NULL DEFAULT NULL,
    technical_accuracy DECIMAL(3,1) NULL DEFAULT NULL,
    communication_clarity DECIMAL(3,1) NULL DEFAULT NULL,
    confidence DECIMAL(3,1) NULL DEFAULT NULL,
    avg_time_taken_sec INT NULL DEFAULT NULL,
    strengths TEXT NULL,
    weaknesses TEXT NULL,
    feedback TEXT NULL,
    started_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL DEFAULT NULL,
    PRIMARY KEY (id),
    KEY idx_interviews_student (student_id),
    CONSTRAINT chk_interviews_overall_score
      CHECK (overall_score IS NULL OR overall_score BETWEEN 0 AND 10),
    CONSTRAINT chk_interviews_technical_accuracy
      CHECK (technical_accuracy IS NULL OR technical_accuracy BETWEEN 0 AND 10),
    CONSTRAINT chk_interviews_communication_clarity
      CHECK (communication_clarity IS NULL OR communication_clarity BETWEEN 0 AND 10),
    CONSTRAINT chk_interviews_confidence
      CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 10),
    CONSTRAINT interviews_ibfk_1
      FOREIGN KEY (student_id) REFERENCES students (id)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS interview_details (
    id INT NOT NULL AUTO_INCREMENT,
    interview_id INT NOT NULL,
    question_order INT NOT NULL,
    question TEXT NOT NULL,
    question_source VARCHAR(20) NOT NULL DEFAULT 'ai_generated',
    topic_area VARCHAR(100) NULL DEFAULT NULL,
    subject_tag VARCHAR(150) NULL DEFAULT NULL,
    is_followup TINYINT(1) NOT NULL DEFAULT 0,
    answer TEXT NULL,
    verdict ENUM('correct', 'partial', 'wrong') NULL DEFAULT NULL,
    verdict_reason TEXT NULL,
    ideal_answer TEXT NULL,
    timed_out TINYINT(1) NOT NULL DEFAULT 0,
    time_taken_sec INT NULL DEFAULT NULL,
    answer_audio_path VARCHAR(255) NULL DEFAULT NULL,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    processing_status VARCHAR(32) NOT NULL DEFAULT 'question_ready',
    answered_at TIMESTAMP NULL DEFAULT NULL,
    processing_error TEXT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_interview_question_order (interview_id, question_order),
    KEY idx_details_interview (interview_id),
    CONSTRAINT interview_details_ibfk_1
      FOREIGN KEY (interview_id) REFERENCES interviews (id)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS user_question_history (
    id INT NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    round_type ENUM('technical', 'hr') NOT NULL,
    role_or_topic VARCHAR(255) NOT NULL,
    difficulty ENUM('beginner', 'intermediate', 'advanced') NOT NULL,
    question_text TEXT NOT NULL,
    question_hash VARCHAR(64) NOT NULL,
    source VARCHAR(20) NOT NULL,
    interview_session_id INT NOT NULL,
    served_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_user_round_topic (user_id, round_type, role_or_topic, served_at),
    KEY idx_history_session (interview_session_id),
    CONSTRAINT fk_history_interview FOREIGN KEY (interview_session_id) REFERENCES interviews (id)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS interview_focus_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    event_uuid CHAR(36) NOT NULL,
    interview_id INT NOT NULL,
    event_source ENUM('visibility', 'window_blur') NOT NULL,
    left_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    returned_at DATETIME(6) NULL DEFAULT NULL,
    away_seconds INT UNSIGNED NULL DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_interview_focus_event_uuid (event_uuid),
    KEY idx_focus_events_interview_left_at (interview_id, left_at),
    CONSTRAINT chk_focus_event_return_order
      CHECK (returned_at IS NULL OR returned_at >= left_at),
    CONSTRAINT chk_focus_event_away_seconds
      CHECK (away_seconds IS NULL OR away_seconds >= 0),
    CONSTRAINT focus_events_interview_fk
      FOREIGN KEY (interview_id) REFERENCES interviews (id)
      ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS daily_usage (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    usage_date DATE NOT NULL,
    answered_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY unique_student_day (student_id, usage_date),
    CONSTRAINT chk_daily_usage_answered_count_nonnegative
      CHECK (answered_count >= 0),
    CONSTRAINT daily_usage_ibfk_1
      FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Compatibility objects retained because they exist in the live database.
-- The Flask application performs quota updates transactionally and does not
-- call these routines directly.
DROP PROCEDURE IF EXISTS record_answered_question;
DELIMITER $$
CREATE PROCEDURE record_answered_question(IN p_student_id INT)
BEGIN
    INSERT INTO daily_usage (student_id, usage_date, answered_count)
    VALUES (p_student_id, CURDATE(), 1)
    ON DUPLICATE KEY UPDATE answered_count = answered_count + 1;
END$$
DELIMITER ;

DROP FUNCTION IF EXISTS get_remaining_questions;
DELIMITER $$
CREATE FUNCTION get_remaining_questions(p_student_id INT)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE v_used INT DEFAULT 0;
    DECLARE v_limit INT DEFAULT 10;

    SELECT answered_count INTO v_used
    FROM daily_usage
    WHERE student_id = p_student_id
      AND usage_date = CURDATE();

    IF v_used IS NULL THEN
        SET v_used = 0;
    END IF;

    RETURN GREATEST(v_limit - v_used, 0);
END$$
DELIMITER ;

CREATE OR REPLACE VIEW today_usage_report AS
SELECT
    s.id AS student_id,
    s.name AS student_name,
    COALESCE(d.answered_count, 0) AS answered_today,
    GREATEST(10 - COALESCE(d.answered_count, 0), 0) AS remaining_today
FROM students s
LEFT JOIN daily_usage d
  ON d.student_id = s.id
 AND d.usage_date = CURDATE();

DROP EVENT IF EXISTS cleanup_old_daily_usage;
CREATE EVENT cleanup_old_daily_usage
ON SCHEDULE EVERY 1 DAY
STARTS '2026-07-29 02:00:00'
ON COMPLETION NOT PRESERVE
ENABLE
DO
    DELETE FROM daily_usage
    WHERE usage_date < CURDATE() - INTERVAL 90 DAY;

ALTER TABLE interviews 
MODIFY COLUMN status ENUM('in_progress','completed','exited') 
DEFAULT 'in_progress';

use mock_interview_db;
ALTER TABLE interview_details
ADD COLUMN answered_at TIMESTAMP NULL DEFAULT NULL;

ALTER TABLE interview_details
ADD COLUMN processing_status ENUM('pending','processing','done') 
DEFAULT 'pending';

ALTER TABLE interview_details
ADD COLUMN answered_at TIMESTAMP NULL DEFAULT NULL;

use mock_interview_db;
ALTER TABLE interview_details
ADD COLUMN processing_error TEXT NULL DEFAULT NULL;

ALTER TABLE interview_details
MODIFY COLUMN processing_status 
ENUM('pending','processing','done','answer_received') 
DEFAULT 'pending';

-- Record auditable focus-loss episodes during active interviews.
USE mock_interview_db;

CREATE TABLE interview_focus_events (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    event_uuid CHAR(36) NOT NULL,
    interview_id INT NOT NULL,
    event_source ENUM('visibility', 'window_blur') NOT NULL,
    left_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    returned_at DATETIME(6) NULL DEFAULT NULL,
    away_seconds INT UNSIGNED NULL DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_interview_focus_event_uuid (event_uuid),
    KEY idx_focus_events_interview_left_at (interview_id, left_at),

    CONSTRAINT chk_focus_event_return_order
      CHECK (returned_at IS NULL OR returned_at >= left_at),

    CONSTRAINT chk_focus_event_away_seconds
      CHECK (away_seconds IS NULL OR away_seconds >= 0),

    CONSTRAINT focus_events_interview_fk
      FOREIGN KEY (interview_id)
      REFERENCES interviews (id)
      ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

INSERT IGNORE INTO schema_migrations (migration_name)
VALUES ('20260804_add_interview_focus_events.sql');

use mock_interview_db;
CREATE TABLE ai_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    interview_id INT,
    question_id INT,
    model_name VARCHAR(100),
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    estimated_cost DECIMAL(10,6) DEFAULT 0,
    request_type VARCHAR(50),
    response_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

RENAME TABLE ai_usage TO ai_usage_records;
SHOW TABLES;
ALTER TABLE ai_usage_records
ADD COLUMN provider VARCHAR(50) NULL AFTER student_id;
DESCRIBE ai_usage_records;

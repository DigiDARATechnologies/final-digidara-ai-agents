-- Run this in MySQL Workbench if you prefer manual setup instead of `flask init-db`.
CREATE DATABASE IF NOT EXISTS communication_module CHARACTER SET utf8mb4;
USE communication_module;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'student',
    target_level VARCHAR(30) DEFAULT 'Intermediate',
    phone VARCHAR(30),
    course_name VARCHAR(120),
    photo_url VARCHAR(300),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    total_xp INT NOT NULL DEFAULT 0,
    streak_count INT NOT NULL DEFAULT 0,
    last_completed_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS topics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description VARCHAR(400),
    difficulty VARCHAR(20) NOT NULL DEFAULT 'medium'
);

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

CREATE TABLE IF NOT EXISTS speaking_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    mode VARCHAR(20) NOT NULL,
    generated_topic_id VARCHAR(64),
    topic_title VARCHAR(200),
    topic_description VARCHAR(500),
    daily_category VARCHAR(120),
    session_date DATE,
    total_questions INT,
    current_question INT,
    daily_questions_json TEXT,
    daily_vocabulary_json TEXT,
    daily_vocab_used_json TEXT,
    difficulty VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    total_turns INT DEFAULT 0,
    answered_turns INT DEFAULT 0,
    ended_by_user BOOLEAN NOT NULL DEFAULT FALSE,
    confidence_score FLOAT,
    fluency_score FLOAT,
    grammar_score FLOAT,
    knowledge_score FLOAT,
    clarity_score FLOAT,
    overall_score FLOAT,
    summary_feedback TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS speaking_turns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    turn_number INT NOT NULL,
    ai_question TEXT NOT NULL,
    user_answer TEXT,
    corrected_answer TEXT,
    better_natural_answer TEXT,
    reaction TEXT,
    natural_version TEXT,
    explanation TEXT,
    feedback_json TEXT,
    confidence_score FLOAT,
    fluency_score FLOAT,
    grammar_score FLOAT,
    knowledge_score FLOAT,
    clarity_score FLOAT,
    overall_score FLOAT,
    feedback TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES speaking_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS writing_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    mode VARCHAR(20) NOT NULL,
    generated_topic_id VARCHAR(64),
    topic_title VARCHAR(200),
    topic_description VARCHAR(500),
    difficulty VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    total_turns INT DEFAULT 0,
    grammar_score FLOAT,
    vocabulary_score FLOAT,
    clarity_score FLOAT,
    knowledge_score FLOAT,
    overall_score FLOAT,
    summary_feedback TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS writing_turns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    turn_number INT NOT NULL,
    ai_prompt TEXT NOT NULL,
    user_response TEXT,
    grammar_score FLOAT,
    vocabulary_score FLOAT,
    clarity_score FLOAT,
    knowledge_score FLOAT,
    overall_score FLOAT,
    corrected_answer TEXT,
    better_natural_answer TEXT,
    feedback_json TEXT,
    feedback TEXT,
    draft_text TEXT,
    draft_updated_at DATETIME,
    used_ai_suggestion BOOLEAN NOT NULL DEFAULT FALSE,
    weak_area_tags TEXT,
    completed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES writing_sessions(id) ON DELETE CASCADE
);

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
    FOREIGN KEY (user_id) REFERENCES users(id)
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
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Aptitude AI Agent - MySQL 8 baseline database (revision 0004_native_auth)
-- Safe for a new local installation. Contains no user passwords or sample student data.
-- REQUIRED AFTER IMPORT: flask --app app db upgrade
-- Import with:
--   mysql -u root -p < database/aptitude_ai_mysql.sql

CREATE DATABASE IF NOT EXISTS aptitude_ai_dev
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE aptitude_ai_dev;

CREATE TABLE IF NOT EXISTS students (
  id VARCHAR(128) NOT NULL,
  name VARCHAR(160) NOT NULL,
  email VARCHAR(255) NULL,
  password_hash VARCHAR(255) NULL,
  token_version INT NOT NULL DEFAULT 0,
  phone VARCHAR(24) NULL,
  course VARCHAR(160) NULL,
  department VARCHAR(160) NULL,
  year VARCHAR(40) NULL,
  institution VARCHAR(200) NULL,
  batch VARCHAR(80) NULL,
  profile_photo MEDIUMBLOB NULL,
  profile_photo_mime VARCHAR(40) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_students_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_tests (
  id VARCHAR(36) NOT NULL,
  student_id VARCHAR(128) NOT NULL,
  status ENUM('generating','ready','in_progress','completed','abandoned','failed') NOT NULL DEFAULT 'generating',
  current_sequence INT NOT NULL DEFAULT 1,
  started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  completed_at DATETIME(6) NULL,
  last_activity_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  total_questions INT NOT NULL DEFAULT 20,
  test_mode ENUM('mixed','category_practice') NOT NULL DEFAULT 'mixed',
  selected_category VARCHAR(80) NULL,
  selected_level ENUM('Beginner','Intermediate','Advanced') NULL,
  focus_category VARCHAR(80) NULL,
  hints_used INT NOT NULL DEFAULT 0,
  hints_allowed INT NOT NULL DEFAULT 3,
  correct_count INT NOT NULL DEFAULT 0,
  wrong_count INT NOT NULL DEFAULT 0,
  timed_out_count INT NOT NULL DEFAULT 0,
  score INT NOT NULL DEFAULT 0,
  percentage DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  total_time_seconds INT NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY ix_aptitude_tests_student_id (student_id),
  KEY ix_aptitude_tests_status (status),
  KEY ix_aptitude_tests_test_mode (test_mode),
  CONSTRAINT fk_tests_student FOREIGN KEY (student_id) REFERENCES students (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_test_questions (
  id VARCHAR(36) NOT NULL,
  test_id VARCHAR(36) NOT NULL,
  sequence_no INT NOT NULL,
  category VARCHAR(80) NOT NULL,
  topic VARCHAR(100) NOT NULL,
  difficulty ENUM('Easy','Medium','Hard') NOT NULL,
  difficulty_reason VARCHAR(255) NULL,
  question_text TEXT NOT NULL,
  option_a VARCHAR(500) NOT NULL,
  option_b VARCHAR(500) NOT NULL,
  option_c VARCHAR(500) NOT NULL,
  option_d VARCHAR(500) NOT NULL,
  correct_answer ENUM('A','B','C','D') NOT NULL,
  explanation TEXT NOT NULL,
  allowed_time_seconds INT NOT NULL DEFAULT 60,
  question_started_at DATETIME(6) NULL,
  hint_text TEXT NULL,
  hint_requested BOOLEAN NOT NULL DEFAULT FALSE,
  hint_requested_at DATETIME(6) NULL,
  generation_model VARCHAR(100) NULL,
  prompt_version VARCHAR(30) NOT NULL DEFAULT 'v1',
  validation_status VARCHAR(30) NOT NULL DEFAULT 'accepted',
  regeneration_count INT NOT NULL DEFAULT 0,
  content_hash VARCHAR(64) NOT NULL,
  generated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_test_sequence (test_id, sequence_no),
  KEY ix_aptitude_test_questions_test_id (test_id),
  KEY ix_aptitude_test_questions_content_hash (content_hash),
  CONSTRAINT fk_questions_test FOREIGN KEY (test_id) REFERENCES aptitude_tests (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_answers (
  id VARCHAR(36) NOT NULL,
  test_id VARCHAR(36) NOT NULL,
  student_id VARCHAR(128) NOT NULL,
  question_id VARCHAR(36) NOT NULL,
  selected_answer ENUM('A','B','C','D') NULL,
  correct_answer ENUM('A','B','C','D') NOT NULL,
  is_correct BOOLEAN NOT NULL,
  timed_out BOOLEAN NOT NULL DEFAULT FALSE,
  confidence_rating INT NULL,
  mistake_type ENUM('careless_slip','conceptual_gap','time_pressure','not_applicable') NULL,
  mistake_explanation TEXT NULL,
  time_taken_seconds INT NOT NULL,
  evaluation_source ENUM('groq','fallback','fallback_consistency','authoritative','timeout') NOT NULL,
  reasoning_text TEXT NULL,
  reasoning_quality ENUM('strong','partial','weak','none') NULL,
  reasoning_feedback TEXT NULL,
  outcome_type ENUM('correct_sound_reasoning','correct_flawed_reasoning','incorrect_close_reasoning','incorrect_flawed_reasoning','no_reasoning_given') NULL,
  answered_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_answers_question_id (question_id),
  KEY ix_aptitude_answers_test_id (test_id),
  KEY ix_aptitude_answers_student_id (student_id),
  CONSTRAINT fk_answers_test FOREIGN KEY (test_id) REFERENCES aptitude_tests (id),
  CONSTRAINT fk_answers_student FOREIGN KEY (student_id) REFERENCES students (id),
  CONSTRAINT fk_answers_question FOREIGN KEY (question_id) REFERENCES aptitude_test_questions (id),
  CONSTRAINT ck_answer_confidence_rating CHECK (confidence_rating IS NULL OR (confidence_rating >= 1 AND confidence_rating <= 5))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_topic_performance (
  id BIGINT NOT NULL AUTO_INCREMENT,
  student_id VARCHAR(128) NOT NULL,
  category VARCHAR(80) NOT NULL,
  topic VARCHAR(100) NOT NULL,
  attempts INT NOT NULL DEFAULT 0,
  correct_count INT NOT NULL DEFAULT 0,
  accuracy DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  average_time_seconds DECIMAL(7,2) NOT NULL DEFAULT 0.00,
  last_updated DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_student_category_topic (student_id, category, topic),
  KEY ix_aptitude_topic_performance_student_id (student_id),
  CONSTRAINT fk_performance_student FOREIGN KEY (student_id) REFERENCES students (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_recent_question_hashes (
  id BIGINT NOT NULL AUTO_INCREMENT,
  student_id VARCHAR(128) NOT NULL,
  test_id VARCHAR(36) NOT NULL,
  category VARCHAR(80) NOT NULL,
  topic VARCHAR(100) NOT NULL,
  content_hash VARCHAR(64) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_recent_hash_student (student_id),
  KEY ix_recent_hash_content (content_hash),
  CONSTRAINT fk_recent_hash_student FOREIGN KEY (student_id) REFERENCES students (id),
  CONSTRAINT fk_recent_hash_test FOREIGN KEY (test_id) REFERENCES aptitude_tests (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_ai_recommendations (
  id VARCHAR(36) NOT NULL,
  test_id VARCHAR(36) NOT NULL,
  student_id VARCHAR(128) NOT NULL,
  status ENUM('pending','processing','completed','failed') NOT NULL DEFAULT 'pending',
  recommendation_text TEXT NULL,
  model_version VARCHAR(100) NULL,
  attempt_count INT NOT NULL DEFAULT 0,
  last_error VARCHAR(500) NULL,
  generated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uq_recommendations_test_id (test_id),
  KEY ix_recommendation_student (student_id),
  CONSTRAINT fk_recommendations_test FOREIGN KEY (test_id) REFERENCES aptitude_tests (id),
  CONSTRAINT fk_recommendations_student FOREIGN KEY (student_id) REFERENCES students (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_background_jobs (
  id VARCHAR(36) NOT NULL,
  job_type VARCHAR(50) NOT NULL,
  test_id VARCHAR(36) NULL,
  student_id VARCHAR(128) NULL,
  status ENUM('pending','processing','completed','failed') NOT NULL DEFAULT 'pending',
  payload_json JSON NOT NULL,
  attempt_count INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 3,
  available_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  locked_at DATETIME(6) NULL,
  locked_by VARCHAR(180) NULL,
  last_error VARCHAR(500) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  completed_at DATETIME(6) NULL,
  PRIMARY KEY (id),
  KEY ix_jobs_status_available (status, available_at),
  KEY ix_jobs_test (test_id),
  KEY ix_jobs_student (student_id),
  CONSTRAINT fk_jobs_test FOREIGN KEY (test_id) REFERENCES aptitude_tests (id),
  CONSTRAINT fk_jobs_student FOREIGN KEY (student_id) REFERENCES students (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_audit_events (
  id BIGINT NOT NULL AUTO_INCREMENT,
  student_id VARCHAR(128) NULL,
  test_id VARCHAR(36) NULL,
  event_type VARCHAR(60) NOT NULL,
  request_id VARCHAR(80) NULL,
  metadata_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_audit_student (student_id),
  KEY ix_audit_test (test_id),
  KEY ix_audit_type (event_type),
  KEY ix_audit_request (request_id),
  KEY ix_audit_created (created_at),
  CONSTRAINT fk_audit_student FOREIGN KEY (student_id) REFERENCES students (id),
  CONSTRAINT fk_audit_test FOREIGN KEY (test_id) REFERENCES aptitude_tests (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_rate_limit_events (
  id BIGINT NOT NULL AUTO_INCREMENT,
  student_id VARCHAR(128) NOT NULL,
  action VARCHAR(60) NOT NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_rate_student_action_created (student_id, action, created_at),
  CONSTRAINT fk_rate_limit_student FOREIGN KEY (student_id) REFERENCES students (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aptitude_ai_usage_events (
  id BIGINT NOT NULL AUTO_INCREMENT,
  student_id VARCHAR(128) NOT NULL,
  test_id VARCHAR(36) NULL,
  question_id VARCHAR(36) NULL,
  operation VARCHAR(40) NOT NULL,
  model VARCHAR(100) NOT NULL,
  input_tokens INT NOT NULL DEFAULT 0,
  output_tokens INT NOT NULL DEFAULT 0,
  total_tokens INT NOT NULL DEFAULT 0,
  estimated_cost_usd DECIMAL(14,8) NOT NULL DEFAULT 0.00000000,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY ix_ai_usage_student_created (student_id, created_at),
  KEY ix_ai_usage_test (test_id),
  KEY ix_ai_usage_question (question_id),
  CONSTRAINT fk_ai_usage_student FOREIGN KEY (student_id) REFERENCES students (id),
  CONSTRAINT fk_ai_usage_test FOREIGN KEY (test_id) REFERENCES aptitude_tests (id),
  CONSTRAINT fk_ai_usage_question FOREIGN KEY (question_id) REFERENCES aptitude_test_questions (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Mark this standalone schema as equivalent to the bundled initial Alembic migration.
-- VARCHAR(255), not Alembic's default VARCHAR(32): this project's migrations
-- use long descriptive revision ids (e.g. "0020_reasoning_diagnostics_status",
-- 33 chars) instead of the short hex ids the default width assumes, so 32
-- truncates and later "flask db upgrade"/"db stamp" calls fail outright.
CREATE TABLE IF NOT EXISTS alembic_version (
  version_num VARCHAR(255) NOT NULL,
  PRIMARY KEY (version_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

UPDATE alembic_version SET version_num = '0004_native_auth';
INSERT INTO alembic_version (version_num)
SELECT '0004_native_auth'
WHERE NOT EXISTS (SELECT 1 FROM alembic_version);


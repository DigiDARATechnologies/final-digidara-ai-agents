ALTER TABLE students ADD COLUMN password_hash VARCHAR(255) NULL AFTER email;
-- statement-breakpoint
CREATE TABLE student_sessions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  token_hash CHAR(64) NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_student_sessions_token_hash (token_hash),
  KEY idx_student_sessions_student_active (student_id, revoked_at, expires_at),
  CONSTRAINT fk_student_sessions_student FOREIGN KEY (student_id)
    REFERENCES students (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE coding_problems (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  topic_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(160) NOT NULL,
  slug VARCHAR(160) NOT NULL,
  description TEXT NOT NULL,
  input_format TEXT NOT NULL,
  output_format TEXT NOT NULL,
  constraints_text TEXT NOT NULL,
  examples_json JSON NOT NULL,
  starter_code MEDIUMTEXT NOT NULL,
  language_key VARCHAR(40) NOT NULL,
  judge0_language_id INT UNSIGNED NOT NULL,
  difficulty ENUM('Easy','Medium','Hard') NOT NULL DEFAULT 'Easy',
  max_score INT UNSIGNED NOT NULL DEFAULT 100,
  display_order INT UNSIGNED NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_coding_problems_topic_slug (topic_id, slug),
  KEY idx_coding_problems_topic_order (topic_id, is_active, display_order),
  CONSTRAINT fk_coding_problems_topic FOREIGN KEY (topic_id)
    REFERENCES coding_topics (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE coding_test_cases (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  problem_id BIGINT UNSIGNED NOT NULL,
  stdin_text TEXT NOT NULL,
  expected_output TEXT NOT NULL,
  is_hidden BOOLEAN NOT NULL DEFAULT TRUE,
  score_weight INT UNSIGNED NOT NULL DEFAULT 1,
  display_order INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_coding_test_cases_order (problem_id, display_order),
  KEY idx_coding_test_cases_visibility (problem_id, is_hidden),
  CONSTRAINT fk_coding_test_cases_problem FOREIGN KEY (problem_id)
    REFERENCES coding_problems (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE coding_submissions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  problem_id BIGINT UNSIGNED NOT NULL,
  source_code MEDIUMTEXT NOT NULL,
  language_key VARCHAR(40) NOT NULL,
  mode ENUM('run','submit') NOT NULL,
  status VARCHAR(40) NOT NULL,
  score INT UNSIGNED NOT NULL DEFAULT 0,
  passed_tests INT UNSIGNED NOT NULL DEFAULT 0,
  total_tests INT UNSIGNED NOT NULL DEFAULT 0,
  result_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_coding_submissions_student_recent (student_id, created_at),
  KEY idx_coding_submissions_problem_recent (problem_id, created_at),
  CONSTRAINT fk_coding_submissions_student FOREIGN KEY (student_id)
    REFERENCES students (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_coding_submissions_problem FOREIGN KEY (problem_id)
    REFERENCES coding_problems (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE student_problem_progress (
  student_id BIGINT UNSIGNED NOT NULL,
  problem_id BIGINT UNSIGNED NOT NULL,
  attempts INT UNSIGNED NOT NULL DEFAULT 0,
  best_score INT UNSIGNED NOT NULL DEFAULT 0,
  status ENUM('Not Started','Attempted','Solved') NOT NULL DEFAULT 'Not Started',
  last_submission_id BIGINT UNSIGNED NULL,
  first_solved_at TIMESTAMP NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (student_id, problem_id),
  KEY idx_student_problem_progress_status (student_id, status),
  CONSTRAINT fk_student_problem_progress_student FOREIGN KEY (student_id)
    REFERENCES students (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_student_problem_progress_problem FOREIGN KEY (problem_id)
    REFERENCES coding_problems (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_student_problem_progress_submission FOREIGN KEY (last_submission_id)
    REFERENCES coding_submissions (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE tutor_interactions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  problem_id BIGINT UNSIGNED NOT NULL,
  submission_id BIGINT UNSIGNED NULL,
  error_category VARCHAR(80) NOT NULL,
  explanation TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_tutor_interactions_student_recent (student_id, created_at),
  CONSTRAINT fk_tutor_interactions_student FOREIGN KEY (student_id)
    REFERENCES students (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_tutor_interactions_problem FOREIGN KEY (problem_id)
    REFERENCES coding_problems (id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_tutor_interactions_submission FOREIGN KEY (submission_id)
    REFERENCES coding_submissions (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

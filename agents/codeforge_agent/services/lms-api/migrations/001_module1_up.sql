CREATE TABLE IF NOT EXISTS schema_migrations (
  version VARCHAR(64) PRIMARY KEY,
  applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE students (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  external_user_id VARCHAR(191) NOT NULL,
  email VARCHAR(254) NOT NULL,
  display_name VARCHAR(120) NOT NULL,
  bio VARCHAR(500) NULL,
  timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Calcutta',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_students_external_user_id (external_user_id),
  UNIQUE KEY uq_students_email (email),
  KEY idx_students_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE coding_courses (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(120) NOT NULL,
  slug VARCHAR(120) NOT NULL,
  description VARCHAR(500) NOT NULL,
  icon_key VARCHAR(40) NOT NULL,
  display_order INT UNSIGNED NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_coding_courses_slug (slug),
  KEY idx_coding_courses_active_order (is_active, display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE coding_technologies (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(80) NOT NULL,
  slug VARCHAR(80) NOT NULL,
  description VARCHAR(500) NOT NULL,
  icon_key VARCHAR(40) NOT NULL,
  display_order INT UNSIGNED NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_coding_technologies_slug (slug),
  KEY idx_coding_technologies_active_order (is_active, display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE coding_topics (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  technology_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(120) NOT NULL,
  slug VARCHAR(120) NOT NULL,
  description VARCHAR(500) NOT NULL,
  learning_objectives JSON NOT NULL,
  suggested_concepts JSON NOT NULL,
  display_order INT UNSIGNED NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_coding_topics_technology_slug (technology_id, slug),
  KEY idx_coding_topics_active_order (technology_id, is_active, display_order),
  CONSTRAINT fk_coding_topics_technology FOREIGN KEY (technology_id)
    REFERENCES coding_technologies (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE course_technologies (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  course_id BIGINT UNSIGNED NOT NULL,
  technology_id BIGINT UNSIGNED NOT NULL,
  display_order INT UNSIGNED NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_course_technologies_pair (course_id, technology_id),
  KEY idx_course_technologies_active_order (course_id, is_active, display_order),
  CONSTRAINT fk_course_technologies_course FOREIGN KEY (course_id)
    REFERENCES coding_courses (id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_course_technologies_technology FOREIGN KEY (technology_id)
    REFERENCES coding_technologies (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE student_coding_activity (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  course_id BIGINT UNSIGNED NOT NULL,
  technology_id BIGINT UNSIGNED NULL,
  topic_id BIGINT UNSIGNED NULL,
  last_accessed_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_student_activity_recent (student_id, last_accessed_at),
  KEY idx_student_activity_course (course_id),
  KEY idx_student_activity_technology (technology_id),
  KEY idx_student_activity_topic (topic_id),
  CONSTRAINT fk_student_activity_student FOREIGN KEY (student_id)
    REFERENCES students (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_student_activity_course FOREIGN KEY (course_id)
    REFERENCES coding_courses (id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_student_activity_technology FOREIGN KEY (technology_id)
    REFERENCES coding_technologies (id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_student_activity_topic FOREIGN KEY (topic_id)
    REFERENCES coding_topics (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE api_request_nonces (
  request_id VARCHAR(64) NOT NULL,
  requested_at BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (request_id),
  KEY idx_api_request_nonces_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

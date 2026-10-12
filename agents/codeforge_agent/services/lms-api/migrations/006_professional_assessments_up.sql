ALTER TABLE coding_problems
  ADD COLUMN track ENUM('practice','professional') NOT NULL DEFAULT 'practice' AFTER difficulty,
  ADD KEY idx_coding_problems_track (track, is_active);
-- statement-breakpoint
CREATE TABLE coding_assessments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  student_id BIGINT UNSIGNED NOT NULL,
  technology_id BIGINT UNSIGNED NOT NULL,
  status ENUM('in_progress','submitted','expired') NOT NULL DEFAULT 'in_progress',
  started_at DATETIME NOT NULL,
  deadline_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  score DECIMAL(5,1) NULL,
  passed BOOLEAN NULL,
  PRIMARY KEY (id),
  KEY idx_coding_assessments_student (student_id, technology_id, status),
  CONSTRAINT fk_coding_assessments_student FOREIGN KEY (student_id)
    REFERENCES students (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_coding_assessments_technology FOREIGN KEY (technology_id)
    REFERENCES coding_technologies (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
-- statement-breakpoint
CREATE TABLE coding_assessment_items (
  assessment_id BIGINT UNSIGNED NOT NULL,
  position TINYINT UNSIGNED NOT NULL,
  problem_id BIGINT UNSIGNED NOT NULL,
  kind ENUM('hard','expert','real_world') NOT NULL,
  best_score INT UNSIGNED NOT NULL DEFAULT 0,
  attempts INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (assessment_id, position),
  CONSTRAINT fk_coding_assessment_items_assessment FOREIGN KEY (assessment_id)
    REFERENCES coding_assessments (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_coding_assessment_items_problem FOREIGN KEY (problem_id)
    REFERENCES coding_problems (id) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

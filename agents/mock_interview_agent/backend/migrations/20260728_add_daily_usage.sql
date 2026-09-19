-- Daily answered-question quota, keyed independently for every student.
-- Safe to run more than once on an existing MySQL database.
CREATE TABLE IF NOT EXISTS daily_usage (
    id INT NOT NULL AUTO_INCREMENT,
    student_id INT NOT NULL,
    usage_date DATE NOT NULL,
    answered_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY unique_student_day (student_id, usage_date),
    CONSTRAINT daily_usage_ibfk_1
        FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

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
      FOREIGN KEY (interview_id) REFERENCES interviews (id)
      ON DELETE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

INSERT IGNORE INTO schema_migrations (migration_name)
VALUES ('20260804_add_interview_focus_events.sql');

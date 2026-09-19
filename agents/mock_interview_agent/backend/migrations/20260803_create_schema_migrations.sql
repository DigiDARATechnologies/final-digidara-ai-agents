-- Create the migration ledger without modifying existing application data.
USE mock_interview_db;

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (migration_name)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

INSERT IGNORE INTO schema_migrations (migration_name)
VALUES ('20260803_create_schema_migrations.sql');

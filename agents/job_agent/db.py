import logging
import os

import mysql.connector
from mysql.connector import pooling


logger = logging.getLogger(__name__)

_pool = None
_SCHEMA_LOCK_NAME = "digidara_job_agent_schema_init"
_SCHEMA_LOCK_TIMEOUT_SECONDS = 120


MAX_POOL_SIZE = 4


def _pool_size():
    # mysql-connector opens every pooled connection eagerly, per gunicorn
    # worker (4) plus the worker container, on a MySQL server shared with the
    # other agents. Mock Interview hit "1040 Too many connections" at 10 x 4;
    # cap here too so an older .env still saying DB_POOL_SIZE=10 is safe.
    try:
        requested = int(os.getenv("DB_POOL_SIZE", str(MAX_POOL_SIZE)))
    except ValueError:
        requested = MAX_POOL_SIZE
    return max(1, min(requested, MAX_POOL_SIZE))


def _pool_config():
    return {
        "pool_name": "job_agent_pool",
        "pool_size": _pool_size(),
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "job_agent"),
    }


def get_db():
    """Return a pooled connection. Own database — never the shared platform DB."""
    global _pool
    if _pool is None:
        _pool = mysql.connector.pooling.MySQLConnectionPool(**_pool_config())
    return _pool.get_connection()


def _add_column(cursor, statement):
    try:
        cursor.execute(statement)
    except mysql.connector.Error as exc:
        if exc.errno not in (1060, 1061):  # Duplicate column / duplicate key name
            raise


def init_job_tables():
    """Create/upgrade this service's own schema.

    Deliberately has no foreign key into any other agent's database — this
    service owns its identity (`user_job_profiles.user_id`, the DigiDARA
    platform user id bridged in via `ensure_profile`) rather than depending
    on another agent's tables, so it can be deployed, migrated, and scaled
    independently of every other agent in the fleet.
    """
    db = get_db()
    cursor = db.cursor()
    lock_acquired = False
    try:
        # Gunicorn imports the app factory independently in every worker.
        # Serialize schema DDL across those processes: concurrent CREATE /
        # ALTER statements can deadlock even when they use IF NOT EXISTS.
        cursor.execute(
            "SELECT GET_LOCK(%s, %s)",
            (_SCHEMA_LOCK_NAME, _SCHEMA_LOCK_TIMEOUT_SECONDS),
        )
        if cursor.fetchone() != (1,):
            raise RuntimeError("Timed out waiting for the Job Agent schema initialization lock")
        lock_acquired = True
        statements = [
            """CREATE TABLE IF NOT EXISTS job_sources (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                source_type VARCHAR(30) NOT NULL,
                source_url TEXT NOT NULL,
                parser_config LONGTEXT,
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                scraping_authorized TINYINT(1) NOT NULL DEFAULT 0,
                last_run_at TIMESTAMP NULL,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_job_source_name (name)
            )""",
            """CREATE TABLE IF NOT EXISTS jobs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                source_id INT NULL,
                external_id VARCHAR(255) NOT NULL,
                title VARCHAR(255) NOT NULL,
                company VARCHAR(255) NOT NULL,
                location VARCHAR(255),
                work_mode VARCHAR(30),
                employment_type VARCHAR(50),
                experience_min INT NULL,
                experience_max INT NULL,
                salary_text VARCHAR(255),
                description LONGTEXT,
                skills LONGTEXT,
                apply_url TEXT NOT NULL,
                source_url TEXT,
                published_at DATETIME NULL,
                expires_at DATETIME NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                content_hash CHAR(64) NOT NULL,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_job_source_external (source_id, external_id),
                UNIQUE KEY uq_job_content_hash (content_hash),
                INDEX idx_jobs_status_date (status, published_at),
                CONSTRAINT fk_jobs_source FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE SET NULL
            )""",
            """CREATE TABLE IF NOT EXISTS job_ingestion_runs (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                source_id INT NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'queued',
                fetched_count INT NOT NULL DEFAULT 0,
                inserted_count INT NOT NULL DEFAULT 0,
                updated_count INT NOT NULL DEFAULT 0,
                rejected_count INT NOT NULL DEFAULT 0,
                error_message TEXT,
                requested_by VARCHAR(32) NULL,
                queued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                INDEX idx_job_runs_status (status, queued_at),
                CONSTRAINT fk_job_runs_source FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE CASCADE
            )""",
            # Keyed directly on the DigiDARA platform user id (a UUID hex
            # string bridged in via ensure_profile) rather than a duplicate
            # local users table — this service has no reason to own a copy
            # of identity that the orchestrator already owns.
            """CREATE TABLE IF NOT EXISTS user_job_profiles (
                user_id VARCHAR(32) PRIMARY KEY,
                full_name VARCHAR(255) NULL,
                skills LONGTEXT,
                preferred_titles LONGTEXT,
                preferred_locations LONGTEXT,
                preferred_work_mode VARCHAR(30),
                experience_years DECIMAL(4,1) NOT NULL DEFAULT 0,
                resume_url TEXT,
                profile_completed TINYINT(1) NOT NULL DEFAULT 0,
                plan_tier VARCHAR(20) NOT NULL DEFAULT 'free',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS user_job_actions (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(32) NOT NULL,
                job_id BIGINT NOT NULL,
                is_saved TINYINT(1) NOT NULL DEFAULT 0,
                is_hidden TINYINT(1) NOT NULL DEFAULT 0,
                application_status VARCHAR(30) NULL,
                applied_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_user_job_action (user_id, job_id),
                INDEX idx_user_application (user_id, application_status),
                CONSTRAINT fk_job_action_user FOREIGN KEY (user_id) REFERENCES user_job_profiles(user_id) ON DELETE CASCADE,
                CONSTRAINT fk_job_action_job FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )""",
            """CREATE TABLE IF NOT EXISTS job_automation_settings (
                id TINYINT UNSIGNED NOT NULL PRIMARY KEY,
                is_enabled TINYINT(1) NOT NULL DEFAULT 0,
                last_scheduled_date DATE NULL,
                last_started_at TIMESTAMP NULL,
                last_completed_at TIMESTAMP NULL,
                last_queued_count INT NOT NULL DEFAULT 0,
                last_error TEXT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )""",
        ]
        for statement in statements:
            cursor.execute(statement)

        # Compatibility migration for a user_job_profiles table created
        # before full_name/resume_filename existed.
        _add_column(cursor, "ALTER TABLE user_job_profiles ADD COLUMN full_name VARCHAR(255) NULL")
        # resume_filename is the on-disk relative path under config.UPLOAD_DIR
        # (`<user_id>/<uuid><ext>`); resume_original_name is only the
        # human-readable name shown back to the user — kept as two columns
        # rather than one delimited string.
        _add_column(cursor, "ALTER TABLE user_job_profiles ADD COLUMN resume_filename VARCHAR(500) NULL")
        _add_column(cursor, "ALTER TABLE user_job_profiles ADD COLUMN resume_original_name VARCHAR(255) NULL")

        _add_column(cursor, "ALTER TABLE jobs ADD COLUMN department VARCHAR(150) NULL AFTER employment_type")
        _add_column(cursor, "ALTER TABLE jobs ADD COLUMN category VARCHAR(50) NULL AFTER department")
        _add_column(cursor, "ALTER TABLE jobs ADD INDEX idx_jobs_category (category)")

        # Source lifecycle: DISCOVERED -> VALIDATING -> ACTIVE, or ->
        # TEMPORARILY_FAILED (transient, auto-retried next run) / INVALID
        # (permanent, e.g. board not found - excluded from automatic runs
        # until explicitly revalidated) / DISABLED (removed from config or
        # turned off by an admin). Stored lowercase to match this table's
        # existing status-column convention.
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'discovered'")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN error_category VARCHAR(50) NULL")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN last_attempted_at TIMESTAMP NULL")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN last_success_at TIMESTAMP NULL")
        _add_column(cursor, "ALTER TABLE job_sources ADD INDEX idx_job_sources_status (status)")

        # Registry metadata (informational) and source-health fields used by
        # the Tamil Nadu Greenhouse coverage milestone.
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN district VARCHAR(100) NULL")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN city VARCHAR(100) NULL")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN state VARCHAR(100) NULL")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN country VARCHAR(100) NULL")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN category VARCHAR(150) NULL")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN consecutive_failures INT NOT NULL DEFAULT 0")
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN last_validated_at TIMESTAMP NULL")

        # Per-job Tamil Nadu location classification (tn_location.py),
        # computed for every job regardless of provider - see
        # service._clean_job(). Not Greenhouse-specific.
        _add_column(cursor, "ALTER TABLE jobs ADD COLUMN location_district VARCHAR(50) NULL")
        _add_column(cursor, "ALTER TABLE jobs ADD COLUMN location_region VARCHAR(20) NULL")
        _add_column(cursor, "ALTER TABLE jobs ADD COLUMN location_type VARCHAR(20) NULL")
        _add_column(cursor, "ALTER TABLE jobs ADD INDEX idx_jobs_location_district (location_district)")
        _add_column(cursor, "ALTER TABLE jobs ADD INDEX idx_jobs_location_region (location_region)")

        # Raw (pre-filter) job count from the provider's last successful
        # fetch - lets EMPTY_BOARD (raw count 0) be told apart from
        # NO_MATCHING_JOBS (raw count > 0, nothing passed the filters).
        _add_column(cursor, "ALTER TABLE job_sources ADD COLUMN last_fetched_count INT NULL")
        _add_column(cursor, "ALTER TABLE job_ingestion_runs ADD INDEX idx_job_runs_source_status (source_id, status)")

        # How many previously-active jobs this run expired because the
        # source no longer had them (see service.process_run's reconciliation).
        _add_column(cursor, "ALTER TABLE job_ingestion_runs ADD COLUMN expired_count INT NOT NULL DEFAULT 0")

        default_enabled = os.getenv("JOBS_AUTOMATION_DEFAULT_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        cursor.execute(
            "INSERT IGNORE INTO job_automation_settings (id, is_enabled) VALUES (1, %s)",
            (int(default_enabled),),
        )

        db.commit()
        logger.info("[JobAgent] Database tables ready")
    finally:
        if lock_acquired:
            try:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (_SCHEMA_LOCK_NAME,))
                cursor.fetchone()
            except mysql.connector.Error:
                logger.exception("[JobAgent] Failed to release schema initialization lock")
        cursor.close()
        db.close()

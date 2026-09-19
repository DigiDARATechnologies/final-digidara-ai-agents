"""Database migration runner and compatibility upgrader for installations.

Run from backend with:
    python migrate.py
"""

import logging
from pathlib import Path
from time import perf_counter

import db
from structured_logging import configure_root_structured_logging, log_event


configure_root_structured_logging()
logger = logging.getLogger(__name__)
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"


def report(event, message, level=logging.INFO, *, exc_info=False):
    log_event(logger, level, event, message, exc_info=exc_info)


def split_sql_statements(sql):
    """Split a migration file into executable MySQL statements.

    Standard migration files use ``;``.  The small amount of delimiter-aware
    handling also supports existing procedure/function migrations that use
    MySQL's ``DELIMITER`` directive; that directive itself is a client command
    and must not be passed to mysql-connector.
    """
    statements = []
    buffer = []
    delimiter = ";"

    for line in sql.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER ") and not "".join(buffer).strip():
            delimiter = stripped.split(None, 1)[1]
            continue

        buffer.append(line)
        candidate = "".join(buffer).rstrip()
        if candidate.endswith(delimiter):
            statement = candidate[:-len(delimiter)].strip()
            if statement:
                statements.append(statement)
            buffer = []

    remaining = "".join(buffer).strip()
    if remaining:
        raise RuntimeError(
            "Migration SQL ended without its configured statement delimiter."
        )
    return statements


def ensure_migration_ledger(cursor):
    """Create the filename ledger used to make SQL migrations idempotent."""
    # ``migration_name`` matches the pre-existing schema.sql and historical
    # migration files, where the value stored is the migration filename.
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
             migration_name VARCHAR(255) NOT NULL,
             applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
             PRIMARY KEY (migration_name)
           ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4"""
    )


def applied_migration_names(cursor):
    cursor.execute("SELECT migration_name FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def run_sql_migrations():
    """Run every unapplied ``migrations/*.sql`` file in filename order."""
    migration_paths = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_paths:
        report("migration_files_none", "No SQL migration files found")
        return

    conn = db.get_conn()
    cursor = conn.cursor()
    try:
        ensure_migration_ledger(cursor)
        conn.commit()
        applied = applied_migration_names(cursor)
        # mysql-connector starts a transaction for the ledger read; close it
        # before opening the per-file transaction below.
        conn.commit()

        for path in migration_paths:
            filename = path.name
            if filename in applied:
                report("migration_file_skipped", f"{filename} already applied")
                continue

            statements = split_sql_statements(path.read_text(encoding="utf-8"))
            if not statements:
                report("migration_file_skipped", f"{filename} contains no statements")
                continue

            started = perf_counter()
            statement_number = 0
            try:
                conn.start_transaction()
                for statement_number, statement in enumerate(statements, start=1):
                    statement_started = perf_counter()
                    try:
                        cursor.execute(statement)
                    except Exception as exc:
                        # MySQL DDL may auto-commit before a prior interrupted
                        # migration run reaches the ledger insert. Treat an
                        # already-present column as an idempotent statement so
                        # legacy migrations can be recorded and later files
                        # are not permanently blocked.
                        if getattr(exc, "errno", None) in {1060, 1061}:
                            report(
                                "migration_statement_skipped",
                                f"{filename} statement {statement_number}/{len(statements)} "
                                "skipped because its schema object already exists",
                            )
                            continue
                        raise
                    report(
                        "migration_statement_completed",
                        f"{filename} statement {statement_number}/{len(statements)} completed "
                        f"in {round((perf_counter() - statement_started) * 1000, 2)} ms",
                    )

                cursor.execute(
                    "INSERT IGNORE INTO schema_migrations (migration_name) VALUES (%s)",
                    (filename,),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                report(
                    "migration_file_failed",
                    f"{filename} statement {statement_number}/{len(statements)} failed after "
                    f"{round((perf_counter() - started) * 1000, 2)} ms; rolled back and not recorded",
                    logging.ERROR,
                    exc_info=True,
                )
                raise

            applied.add(filename)
            report(
                "migration_file_applied",
                f"{filename} applied in {round((perf_counter() - started) * 1000, 2)} ms",
            )
    finally:
        cursor.close()
        conn.close()


DETAIL_COLUMNS = {
    "question_source": "VARCHAR(20) NOT NULL DEFAULT 'ai_generated' AFTER question",
    "topic_area": (
        "VARCHAR(100) NULL DEFAULT NULL AFTER question"
    ),
    "processing_status": (
        "VARCHAR(32) NOT NULL DEFAULT 'question_ready' AFTER created_at"
    ),
    "answered_at": (
        "TIMESTAMP NULL DEFAULT NULL AFTER processing_status"
    ),
    "processing_error": "TEXT NULL AFTER answered_at",
    "subject_tag": "VARCHAR(150) NULL DEFAULT NULL AFTER topic_area",
}

INTERVIEW_COLUMNS = {
    "interview_mode": "VARCHAR(32) NOT NULL DEFAULT 'course' AFTER round_type",
    "role_name": "VARCHAR(150) NULL DEFAULT NULL AFTER subject",
    "resolved_subjects": "JSON NULL DEFAULT NULL AFTER role_name",
}

STUDENT_COLUMNS = {
    "avatar_url": "VARCHAR(255) NULL DEFAULT NULL AFTER avatar_color",
}


def columns(table):
    rows, _ = db.query(
        """SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
           FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s""",
        (table,),
        fetch=True,
    )
    return {row["COLUMN_NAME"]: row for row in rows}


def ensure_detail_columns():
    existing = columns("interview_details")
    for name, definition in DETAIL_COLUMNS.items():
        if name in existing:
            report("migration_column_present", f"interview_details.{name} already exists")
            continue
        db.query(
            f"ALTER TABLE interview_details ADD COLUMN {name} {definition}"
        )
        report("migration_column_added", f"Added interview_details.{name}")

    # Earlier/local migrations may have created processing_status as an ENUM.
    # The recoverable workflow intentionally uses extensible state names, so
    # normalize the live column even when it already exists.
    refreshed = columns("interview_details")
    status_type = refreshed["processing_status"]["COLUMN_TYPE"].lower()
    if not status_type.startswith("varchar(32)"):
        db.query(
            """ALTER TABLE interview_details
               MODIFY COLUMN processing_status VARCHAR(32)
                 NOT NULL DEFAULT 'question_ready'"""
        )
        report(
            "migration_column_normalized",
            "FIX  interview_details.processing_status converted "
            f"from {status_type} to varchar(32)"
        )
    else:
        report(
            "migration_column_present",
            "interview_details.processing_status is varchar(32)",
        )


def ensure_student_columns():
    existing = columns("students")
    for name, definition in STUDENT_COLUMNS.items():
        if name in existing:
            report("migration_column_present", f"students.{name} already exists")
            continue
        db.query(f"ALTER TABLE students ADD COLUMN {name} {definition}")
        report("migration_column_added", f"Added students.{name}")


def ensure_interview_columns():
    existing = columns("interviews")
    for name, definition in INTERVIEW_COLUMNS.items():
        if name in existing:
            report("migration_column_present", f"interviews.{name} already exists")
            continue
        db.query(f"ALTER TABLE interviews ADD COLUMN {name} {definition}")
        report("migration_column_added", f"Added interviews.{name}")


def ensure_exited_status():
    row, _ = db.query(
        """SELECT COLUMN_TYPE
           FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE()
             AND TABLE_NAME = 'interviews' AND COLUMN_NAME = 'status'""",
        fetchone=True,
    )
    if not row:
        raise RuntimeError("interviews.status does not exist.")
    if "'exited'" in row["COLUMN_TYPE"]:
        report("migration_column_present", "interviews.status supports exited")
        return
    db.query(
        """ALTER TABLE interviews
           MODIFY COLUMN status
             ENUM('in_progress', 'completed', 'exited')
             NOT NULL DEFAULT 'in_progress'"""
    )
    report("migration_column_normalized", "interviews.status now supports exited")


def ensure_question_order_unique():
    row, _ = db.query(
        """SELECT INDEX_NAME
           FROM information_schema.STATISTICS
           WHERE TABLE_SCHEMA = DATABASE()
             AND TABLE_NAME = 'interview_details'
             AND INDEX_NAME = 'uq_interview_question_order'
           LIMIT 1""",
        fetchone=True,
    )
    if row:
        report("migration_constraint_present", "Unique interview question order exists")
        return

    duplicate, _ = db.query(
        """SELECT interview_id, question_order, COUNT(*) AS duplicate_count
           FROM interview_details
           GROUP BY interview_id, question_order
           HAVING COUNT(*) > 1
           LIMIT 1""",
        fetchone=True,
    )
    if duplicate:
        report(
            "migration_constraint_skipped",
            "SKIP unique question-order index: duplicate rows exist for "
            f"interview {duplicate['interview_id']}, order "
            f"{duplicate['question_order']}."
        )
        return

    db.query(
        """ALTER TABLE interview_details
           ADD CONSTRAINT uq_interview_question_order
             UNIQUE (interview_id, question_order)"""
    )
    report("migration_constraint_added", "Added unique interview question order")


def backfill_processing_status():
    db.query(
        """UPDATE interview_details
           SET processing_status = CASE
             WHEN verdict IS NOT NULL OR timed_out = TRUE THEN 'evaluated'
             WHEN answer IS NOT NULL THEN 'answer_received'
             ELSE 'question_ready'
           END
           WHERE processing_status IS NULL
              OR processing_status = 'question_ready'"""
    )
    report("migration_backfill_completed", "Processing states backfilled")


def ensure_ai_usage_records():
    existing, _ = db.query(
        """SELECT TABLE_NAME FROM information_schema.TABLES
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ai_usage_records'""",
        fetchone=True,
    )
    if existing:
        report("migration_table_present", "ai_usage_records already exists")
        return
    db.query(
        """CREATE TABLE ai_usage_records (
             id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
             student_id INT NULL, interview_id INT NULL, question_id INT NULL,
             provider VARCHAR(50) NOT NULL, model_name VARCHAR(100) NOT NULL,
             prompt_tokens INT UNSIGNED NOT NULL DEFAULT 0,
             completion_tokens INT UNSIGNED NOT NULL DEFAULT 0,
             total_tokens INT UNSIGNED NOT NULL DEFAULT 0,
             estimated_cost DECIMAL(14, 8) NOT NULL DEFAULT 0,
             request_type VARCHAR(64) NOT NULL, response_time_ms INT UNSIGNED NULL,
             created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
             PRIMARY KEY (id), KEY idx_ai_usage_student_created (student_id, created_at),
             KEY idx_ai_usage_interview (interview_id), KEY idx_ai_usage_question (question_id),
             CONSTRAINT fk_ai_usage_student FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE SET NULL,
             CONSTRAINT fk_ai_usage_interview FOREIGN KEY (interview_id) REFERENCES interviews (id) ON DELETE SET NULL,
             CONSTRAINT fk_ai_usage_question FOREIGN KEY (question_id) REFERENCES interview_details (id) ON DELETE SET NULL
           ) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"""
    )
    report("migration_table_added", "Created ai_usage_records")


def bootstrap_base_schema():
    """Apply schema.sql's ``CREATE TABLE IF NOT EXISTS`` statements.

    Existing installations already have these tables from a manual initial
    setup; run_sql_migrations() below only ever applied the incremental
    migrations/*.sql files on top of that. A fresh database (a new
    docker-compose service, a CI test database) has neither, so this makes
    the base schema itself part of the same idempotent startup path other
    DigiDARA agents already have (see app/db/database.py's init_db() in
    agents/project_AI_Agent for the equivalent).
    """
    if not SCHEMA_FILE.exists():
        report("schema_bootstrap_missing", "schema.sql not found; skipping base schema bootstrap", level=logging.WARNING)
        return
    statements = split_sql_statements(SCHEMA_FILE.read_text(encoding="utf-8"))
    conn = db.get_conn()
    cursor = conn.cursor()
    try:
        for statement in statements:
            try:
                cursor.execute(statement)
            except Exception as exc:
                # IF NOT EXISTS makes CREATE TABLE/DATABASE idempotent already;
                # 1050 (table exists) only shows up for the rare statement
                # that lacks it (e.g. a stray ALTER), and 1060/1061 mirror the
                # already-exists tolerance run_sql_migrations() uses below.
                if getattr(exc, "errno", None) in {1050, 1060, 1061}:
                    continue
                raise
        conn.commit()
        report("schema_bootstrap_completed", "Base schema bootstrap complete")
    finally:
        cursor.close()
        conn.close()


def main():
    bootstrap_base_schema()
    run_sql_migrations()
    ensure_exited_status()
    ensure_student_columns()
    ensure_interview_columns()
    ensure_detail_columns()
    ensure_question_order_unique()
    backfill_processing_status()
    ensure_ai_usage_records()
    report("migration_completed", "Migration complete")


if __name__ == "__main__":
    main()

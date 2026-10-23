import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config

# pool_pre_ping guards against MySQL's default 8-hour idle-connection
# timeout killing a connection the pool still thinks is good.
# Sized for 300+ learners at once: the gateway and its worker threads each
# hold a connection only for a short query.
_POOL = {} if config.DATABASE_URL.startswith("sqlite") else {"pool_size": 20, "max_overflow": 20, "pool_timeout": 30}
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, pool_recycle=280, **_POOL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Session:
    return SessionLocal()


def init_db() -> None:
    from app import models  # noqa: F401 — import registers the table with Base.metadata

    # Every gunicorn worker runs this at startup. When a release adds a table,
    # two workers can both find it missing and race to create it; the loser
    # gets "already exists" (MySQL 1050), or, while the other is still creating
    # it, "being modified by concurrent DDL" (1684), and simply checks again.
    for attempt in range(5):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except Exception as exc:
            if not any(code in str(exc) for code in ("1050", "1684")) or attempt == 4:
                raise
            time.sleep(0.5 * (attempt + 1))
    # create_all does not alter existing tables. Keep this small
    # compatibility migration (added for Google sign-in) until the project
    # adopts Alembic.
    user_columns = {column["name"]: column for column in inspect(engine).get_columns("users")}
    with engine.begin() as connection:
        if "google_id" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN google_id VARCHAR(64) UNIQUE"))
        if not user_columns.get("password_hash", {}).get("nullable", True):
            connection.execute(text("ALTER TABLE users MODIFY COLUMN password_hash VARCHAR(255) NULL"))
        if "token_balance" not in user_columns:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN token_balance INT NOT NULL DEFAULT 50000"))
            except Exception as exc:
                # Tolerate a prior partial run already having added this
                # column -- MySQL error 1060 is "Duplicate column name".
                if "1060" not in str(exc):
                    raise
        if "consent_accepted_at" not in user_columns:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN consent_accepted_at DATETIME NULL"))
            except Exception as exc:
                if "1060" not in str(exc):
                    raise
        if "consent_policy_version" not in user_columns:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN consent_policy_version VARCHAR(32) NULL"))
            except Exception as exc:
                if "1060" not in str(exc):
                    raise
        if "is_admin" not in user_columns:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0"))
            except Exception as exc:
                if "1060" not in str(exc):
                    raise
        if "email_verified" not in user_columns:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0"))
                # Existing Google-linked accounts and operators already proved
                # their address; everyone else stays unverified.
                connection.execute(text("UPDATE users SET email_verified = 1 WHERE google_id IS NOT NULL OR is_admin = 1"))
            except Exception as exc:
                if "1060" not in str(exc):
                    raise
        if "tokens_per_point" not in user_columns:
            try:
                # Every existing balance counts at the free rate, so nobody's
                # shown points jump or shrink when points are introduced.
                connection.execute(text("ALTER TABLE users ADD COLUMN tokens_per_point DOUBLE NOT NULL DEFAULT 3000"))
            except Exception as exc:
                if "1060" not in str(exc):
                    raise
        for column, ddl in (
            ("email_code_hash", "VARCHAR(64) NULL"),
            ("email_code_expires_at", "DATETIME NULL"),
            ("email_code_sent_at", "DATETIME NULL"),
            ("email_code_attempts", "INT NOT NULL DEFAULT 0"),
        ):
            if column not in user_columns:
                try:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {column} {ddl}"))
                except Exception as exc:
                    if "1060" not in str(exc):
                        raise
        if "session_version" not in user_columns:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN session_version INT NOT NULL DEFAULT 0"))
            except Exception as exc:
                if "1060" not in str(exc):
                    raise
        snapshot_columns = {column["name"] for column in inspect(engine).get_columns("readiness_snapshots")}
        if "role_key" not in snapshot_columns:
            try:
                connection.execute(text("ALTER TABLE readiness_snapshots ADD COLUMN role_key VARCHAR(200) NOT NULL DEFAULT ''"))
                connection.execute(text("CREATE INDEX ix_readiness_snapshots_role_key ON readiness_snapshots (role_key)"))
            except Exception as exc:
                if "1060" not in str(exc) and "1061" not in str(exc):
                    raise
        track_columns = {column["name"] for column in inspect(engine).get_columns("role_tracks")}
        if "skills" not in track_columns:
            try:
                connection.execute(text("ALTER TABLE role_tracks ADD COLUMN skills JSON NULL"))
            except Exception as exc:
                if "1060" not in str(exc):
                    raise
        org_columns = {column["name"] for column in inspect(engine).get_columns("organizations")}
        member_columns = {column["name"] for column in inspect(engine).get_columns("organization_members")}
        for table, existing, column, ddl in (
            ("organizations", org_columns, "status", "VARCHAR(16) NOT NULL DEFAULT 'active'"),
            ("organization_members", member_columns, "department", "VARCHAR(120) NULL"),
            ("organization_members", member_columns, "year", "VARCHAR(40) NULL"),
            ("organization_members", member_columns, "section", "VARCHAR(40) NULL"),
            ("organization_members", member_columns, "join_code_id", "VARCHAR(32) NULL"),
        ):
            if column not in existing:
                try:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                except Exception as exc:
                    if "1060" not in str(exc):
                        raise
        payment_columns = {column["name"] for column in inspect(engine).get_columns("payments")}
        for column, ddl in (("credited_tokens", "INT NULL"), ("credited_points", "DOUBLE NULL"),
                            ("customer_gstin", "VARCHAR(15) NULL")):
            if column not in payment_columns:
                try:
                    connection.execute(text(f"ALTER TABLE payments ADD COLUMN {column} {ddl}"))
                except Exception as exc:
                    if "1060" not in str(exc):
                        raise
        # Widen last_heartbeat to microsecond precision -- a plain DATETIME
        # (fsp=0) truncates every value to the whole second, so two agent
        # versions that register or heartbeat within the same second could
        # tie (or invert) once resolve_healthy() orders by this column to
        # pick the freshest one during a rollout. Always safe to re-run --
        # MySQL accepts an identical MODIFY COLUMN with no error.
        connection.execute(text("ALTER TABLE agent_registry MODIFY COLUMN last_heartbeat DATETIME(6) NOT NULL"))

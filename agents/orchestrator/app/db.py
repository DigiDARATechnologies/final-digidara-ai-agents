from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config

# pool_pre_ping guards against MySQL's default 8-hour idle-connection
# timeout killing a connection the pool still thinks is good.
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, pool_recycle=280)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Session:
    return SessionLocal()


def init_db() -> None:
    from app import models  # noqa: F401 — import registers the table with Base.metadata

    Base.metadata.create_all(bind=engine)
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
        if "is_admin" not in user_columns:
            try:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_admin TINYINT(1) NOT NULL DEFAULT 0"))
            except Exception as exc:
                if "1060" not in str(exc):
                    raise

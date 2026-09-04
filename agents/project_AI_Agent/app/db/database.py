from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app import config

# pool_pre_ping guards against MySQL's default 8-hour idle-connection
# timeout killing a connection the pool still thinks is good.
engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, pool_recycle=280)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from app.db import models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    # create_all does not add columns to existing tables, or alter existing
    # ones. Keep this small compatibility migration until the project
    # adopts Alembic.
    student_columns = {column["name"]: column for column in inspect(engine).get_columns("students")}
    if "email" not in student_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE students ADD COLUMN email VARCHAR(255)"))
    if "phone" in student_columns and not student_columns["phone"]["nullable"]:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE students MODIFY COLUMN phone VARCHAR(32) NULL"))


def get_session() -> Session:
    return SessionLocal()

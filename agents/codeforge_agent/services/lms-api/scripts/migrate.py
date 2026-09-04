import argparse
import os
from pathlib import Path

import pymysql


ROOT = Path(__file__).resolve().parents[1]


def load_local_env():
    path = ROOT / ".env.local"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def connect():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.getenv("MYSQL_DATABASE", "leetcode"),
        charset="utf8mb4",
        autocommit=False,
    )


def statements(filename):
    sql = (ROOT / "migrations" / filename).read_text(encoding="utf-8")
    return [part.strip() for part in sql.split("-- statement-breakpoint") if part.strip()]


def migrations():
    return sorted(path.name.removesuffix("_up.sql") for path in (ROOT / "migrations").glob("*_up.sql"))


def migrate_one(cursor, version, direction):
    filename = f"{version}_{'up' if direction == 'up' else 'down'}.sql"
    cursor.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
    applied = cursor.fetchone() is not None
    if direction == "up" and applied:
        print(f"{version} already applied")
        return
    if direction == "down" and not applied:
        print(f"{version} is not applied")
        return
    for statement in statements(filename):
        cursor.execute(statement)
    if direction == "up":
        cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
    print(f"{version} {direction} complete")


def migrate(direction):
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version VARCHAR(64) PRIMARY KEY, "
                "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP) "
                "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci"
            )
            versions = migrations()
            for version in versions if direction == "up" else reversed(versions):
                migrate_one(cursor, version, direction)
        conn.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("direction", choices=("up", "down"))
    args = parser.parse_args()
    load_local_env()
    migrate(args.direction)

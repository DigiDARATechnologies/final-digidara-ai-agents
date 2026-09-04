import os
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]


def load_local_env():
    path = ROOT / ".env.local"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def verify():
    connection = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.getenv("MYSQL_DATABASE", "leetcode"),
        charset="utf8mb4",
    )
    with connection, connection.cursor() as cursor:
        expected = {"coding_courses": 5, "coding_technologies": 7, "course_technologies": 17, "coding_topics": 108, "coding_problems": 6, "coding_test_cases": 24}
        # Table names are interpolated into the query below (MySQL has no
        # placeholder syntax for identifiers) — this allow-list is what makes
        # that safe rather than trusting the dict keys are never contaminated.
        known_tables = {
            "coding_courses", "coding_technologies", "course_technologies",
            "coding_topics", "coding_problems", "coding_test_cases",
        }
        actual = {}
        for table in expected:
            if table not in known_tables:
                raise ValueError(f"Refusing to query unknown table: {table!r}")
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            actual[table] = cursor.fetchone()[0]
        if actual != expected:
            raise RuntimeError(f"Unexpected catalog counts: {actual}; expected {expected}")
        cursor.execute("SELECT COUNT(*) FROM schema_migrations WHERE version IN ('001_module1','002_standalone_practice')")
        if cursor.fetchone()[0] != 2:
            raise RuntimeError("Required migrations are not registered exactly once")
        cursor.execute("SELECT t.display_order FROM coding_topics t JOIN coding_technologies x ON x.id=t.technology_id WHERE x.slug='python' ORDER BY t.display_order")
        orders = [row[0] for row in cursor.fetchall()]
        if orders != list(range(1, 21)):
            raise RuntimeError("Python topics are not stored in the expected order")
    print(f"Module 1 database verified: {actual}")


if __name__ == "__main__":
    load_local_env()
    verify()

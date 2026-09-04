"""Create/repair a local MySQL database account from the configured URL.

Run from the project root with the virtual environment active:
    python scripts/setup_mysql.py
    python scripts/setup_mysql.py --test

The script prompts for a MySQL administrator login and never prints passwords.
"""
from getpass import getpass
from pathlib import Path
import argparse
import sys
from urllib.parse import unquote, urlparse

import pymysql
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def quoted_identifier(value: str) -> str:
    if not value.replace("_", "").isalnum():
        raise ValueError("Database name may contain only letters, numbers and underscores")
    return f"`{value}`"


def main() -> int:
    parser=argparse.ArgumentParser(description="Create or repair an AptiDARA MySQL database and account")
    parser.add_argument("--test",action="store_true",help="use TEST_DATABASE_URL instead of DATABASE_URL")
    args=parser.parse_args()
    values = dotenv_values(PROJECT_ROOT / ".env")
    url_key="TEST_DATABASE_URL" if args.test else "DATABASE_URL"
    raw_url = values.get(url_key) or ""
    parsed = urlparse(raw_url)
    if parsed.scheme != "mysql+pymysql" or not parsed.username or parsed.password is None:
        print(f"ERROR: {url_key} in .env must use mysql+pymysql://user:password@host:port/database")
        return 1

    app_user = unquote(parsed.username)
    app_password = unquote(parsed.password)
    database = parsed.path.lstrip("/")
    host = parsed.hostname or "localhost"
    port = parsed.port or 3306
    quoted_db = quoted_identifier(database)

    admin_user = input("MySQL administrator user [root]: ").strip() or "root"
    if admin_user.lower() in {"localhost", "@localhost", "127.0.0.1", "@127.0.0.1"}:
        print("ERROR: Enter a MySQL administrator username here, normally 'root'. Do not enter the host name.")
        print("Run the command again and press Enter to accept [root].")
        return 1
    admin_password = getpass(f"Password for MySQL administrator '{admin_user}': ")

    try:
        connection = pymysql.connect(host=host, port=port, user=admin_user, password=admin_password, autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {quoted_db} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            for account_host in ("localhost", "127.0.0.1"):
                cursor.execute("CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s", (app_user, account_host, app_password))
                cursor.execute("ALTER USER %s@%s IDENTIFIED BY %s", (app_user, account_host, app_password))
                cursor.execute(f"GRANT ALL PRIVILEGES ON {quoted_db}.* TO %s@%s", (app_user, account_host))
            cursor.execute("FLUSH PRIVILEGES")
        connection.close()
    except pymysql.MySQLError as error:
        print(f"ERROR: MySQL administrator connection/setup failed ({error.args[0]}): {error.args[1]}")
        return 1

    try:
        check = pymysql.connect(host=host, port=port, user=app_user, password=app_password, database=database)
        with check.cursor() as cursor:
            cursor.execute("SELECT DATABASE(), CURRENT_USER()")
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("MySQL verification returned no result")
            active_database, active_user = row
        check.close()
    except pymysql.MySQLError as error:
        print(f"ERROR: Account was updated but verification failed ({error.args[0]}): {error.args[1]}")
        return 1

    print(f"SUCCESS: Connected to '{active_database}' as '{active_user}'.")
    if args.test:
        print(r"Next: .\.venv\Scripts\python.exe -m pytest -v")
    else:
        print("Next: flask --app app db upgrade")
    return 0


if __name__ == "__main__":
    sys.exit(main())

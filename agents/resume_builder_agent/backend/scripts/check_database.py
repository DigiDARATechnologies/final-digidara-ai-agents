from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import inspect
from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
load_dotenv(BACKEND_ROOT / ".env")

from app import create_app
from app.extensions import db

EXPECTED_TABLES = {
    "users",
    "resumes",
    "personal_info",
    "education",
    "experience",
    "skills",
    "certifications",
    "projects",
    "languages",
}
EXPECTED_RESUME_COLUMNS = {
    "target_role",
    "status",
    "declaration",
    "ats_score",
    "job_match_score",
    "download_count",
    "last_downloaded_at",
    "last_analyzed_at",
}


def main():
    app = create_app()
    with app.app_context():
        with db.engine.connect() as conn:
            print("SELECT 1:", conn.execute(text("SELECT 1")).scalar())
            print("DATABASE:", db.engine.url.database or db.engine.url.drivername)
            tables = set(inspect(conn).get_table_names())
            print("TABLES:", ", ".join(sorted(tables)))
            missing = sorted(EXPECTED_TABLES - tables)
            print("MISSING_TABLES:", ", ".join(missing) if missing else "none")
            if "resumes" in tables:
                columns = {column["name"] for column in inspect(conn).get_columns("resumes")}
                missing_columns = sorted(EXPECTED_RESUME_COLUMNS - columns)
                print(
                    "MISSING_RESUME_COLUMNS:",
                    ", ".join(missing_columns) if missing_columns else "none",
                )
                count = conn.execute(
                    text("SELECT COUNT(*) FROM resumes WHERE id = 1")
                ).scalar()
                print("RESUME_ID_1_EXISTS:", bool(count))


if __name__ == "__main__":
    main()

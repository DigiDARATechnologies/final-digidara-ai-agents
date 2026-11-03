"""Today's and yesterday's job fetching, for Boss's report. Only reads. Prints one
line per day for scripts/server/monitor-cycle.sh:

    @jobs <day> <runs> <failed runs> <fetched> <new> <updated> <rejected>

A day runs midnight to midnight in India.
"""
from datetime import datetime, timedelta

from .db import get_db

IST = timedelta(hours=5, minutes=30)


def day_totals(cursor, day):
    """Totals for one India day. Timestamps are compared in UTC."""
    start = datetime(day.year, day.month, day.day) - IST
    cursor.execute(
        """SELECT COUNT(*) AS runs, COALESCE(SUM(status='failed'), 0) AS failed,
                  COALESCE(SUM(fetched_count), 0) AS fetched, COALESCE(SUM(inserted_count), 0) AS inserted,
                  COALESCE(SUM(updated_count), 0) AS updated, COALESCE(SUM(rejected_count), 0) AS rejected
           FROM job_ingestion_runs
           WHERE started_at >= %s AND started_at < %s""",
        (start, start + timedelta(days=1)),
    )
    return cursor.fetchone()


def main(now=None):
    today = ((now or datetime.utcnow()) + IST).date()
    db = get_db()
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SET time_zone='+00:00'")
        for day in (today - timedelta(days=1), today):
            row = day_totals(cursor, day)
            print("@jobs", day.isoformat(), *(int(row[key]) for key in ("runs", "failed", "fetched", "inserted", "updated", "rejected")))
        cursor.close()
    finally:
        db.close()


if __name__ == "__main__":
    main()

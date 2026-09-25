"""Durable daily Greenhouse scheduling for the ingestion worker.

This module only queues work through the established queue pipeline. It never
scrapes inside the scheduler or an HTTP request, and it intentionally excludes
Apify because those providers remain administrator-triggered only.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import JOBS_AUTOMATION_TIME, JOBS_AUTOMATION_TIMEZONE
from .db import get_db
from .providers.sync import queue_adzuna_collection, queue_greenhouse_collection, queue_jsearch_collection
from .service import prune_expired_jobs


def get_automation_settings():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM job_automation_settings WHERE id=1")
        row = cursor.fetchone() or {"is_enabled": 0}
        return {
            "enabled": bool(row.get("is_enabled")),
            "schedule_time": JOBS_AUTOMATION_TIME,
            "timezone": JOBS_AUTOMATION_TIMEZONE,
            "last_scheduled_date": row.get("last_scheduled_date"),
            "last_started_at": row.get("last_started_at"),
            "last_completed_at": row.get("last_completed_at"),
            "last_queued_count": row.get("last_queued_count") or 0,
            "last_error": row.get("last_error"),
        }
    finally:
        cursor.close()
        db.close()


def set_automation_enabled(enabled):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE job_automation_settings SET is_enabled=%s WHERE id=1", (int(enabled),))
        if cursor.rowcount != 1:
            raise RuntimeError("Job automation settings have not been initialized")
        db.commit()
    finally:
        cursor.close()
        db.close()
    return get_automation_settings()


def _claim_today(local_date):
    """Atomically reserve today's pass, even if two workers are running."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        db.start_transaction()
        cursor.execute("SELECT is_enabled, last_scheduled_date FROM job_automation_settings WHERE id=1 FOR UPDATE")
        row = cursor.fetchone()
        if not row or not row["is_enabled"] or row.get("last_scheduled_date") == local_date:
            db.rollback()
            return False
        cursor.execute(
            """UPDATE job_automation_settings
               SET last_scheduled_date=%s, last_started_at=NOW(), last_completed_at=NULL,
                   last_queued_count=0, last_error=NULL WHERE id=1""",
            (local_date,),
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()


def _record_outcome(queued_count=0, error=None):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """UPDATE job_automation_settings
               SET last_completed_at=NOW(), last_queued_count=%s, last_error=%s WHERE id=1""",
            (queued_count, error),
        )
        db.commit()
    finally:
        cursor.close()
        db.close()


def queue_due_automation(now=None):
    """Queue today's automatic job collection and 30-day retention pruning pass.

    Runs daily at configured local time:
    1. Prunes and purges jobs older than 30 days.
    2. Queues daily fresher job collection across Adzuna & RapidAPI JSearch.
    3. Queues Greenhouse verified corporate boards.
    """
    timezone = ZoneInfo(JOBS_AUTOMATION_TIMEZONE)
    local_now = now.astimezone(timezone) if now else datetime.now(timezone)
    scheduled_hour, scheduled_minute = (int(part) for part in JOBS_AUTOMATION_TIME.split(":", 1))
    if (local_now.hour, local_now.minute) < (scheduled_hour, scheduled_minute):
        return {"due": False, "reason": "not_due"}
    if not _claim_today(local_now.date()):
        return {"due": False, "reason": "disabled_or_already_run"}
    try:
        # 1. 30-Day Automated Retention Pruning
        prune_outcome = prune_expired_jobs(max_age_days=30)

        # 2. Daily Automated Ingestion from Adzuna & JSearch
        total_queued = 0
        adzuna_res = queue_adzuna_collection(admin_id=None)
        if adzuna_res.get("ready"):
            total_queued += adzuna_res.get("queued_count", 0)

        jsearch_res = queue_jsearch_collection(admin_id=None)
        if jsearch_res.get("ready"):
            total_queued += jsearch_res.get("queued_count", 0)

        # 3. Greenhouse collection if active
        try:
            gh_res = queue_greenhouse_collection(admin_id=None)
            total_queued += gh_res.get("queued_count", 0)
        except Exception:
            pass

        _record_outcome(queued_count=total_queued)
        return {
            "due": True,
            "queued_count": total_queued,
            "pruned": prune_outcome,
            "adzuna": adzuna_res,
            "jsearch": jsearch_res,
        }
    except Exception as exc:
        _record_outcome(error=str(exc))
        raise

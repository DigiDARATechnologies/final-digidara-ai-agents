import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import mysql.connector

from .categories import categorize_job
from .db import get_db
from .scraper import scrape_source
from .skills import extract_skills_from_job
from .tn_location import classify_job_location


logger = logging.getLogger(__name__)


def _content_hash(job):
    identity = "|".join([
        (job.get("title") or "").strip().lower(),
        (job.get("company") or "").strip().lower(),
        (job.get("location") or "").strip().lower(),
        (job.get("apply_url") or "").strip().lower(),
    ])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _clean_job(job):
    required = ("external_id", "title", "company", "apply_url")
    if not all(str(job.get(field) or "").strip() for field in required):
        return None
    job = dict(job)
    apply_url = urlparse(str(job["apply_url"]).strip())
    if apply_url.scheme not in {"http", "https"} or not apply_url.netloc:
        return None
    job["apply_url"] = apply_url.geturl()
    extracted_skills = extract_skills_from_job(job)
    job["skills"] = json.dumps(extracted_skills)
    job["content_hash"] = _content_hash(job)
    job["category"] = job.get("category") or categorize_job(
        job.get("title") or "", job.get("department") or "", job.get("description") or ""
    )
    # Provider-independent: classifies every job from its own location
    # text, regardless of which company or provider posted it. Never
    # derived from the source's registry metadata (a Tamil Nadu company
    # can post a Bangalore or Remote job) — see tn_location.py.
    district, region, location_type = classify_job_location(job.get("location") or "")
    job["location_district"] = district
    job["location_region"] = region
    job["location_type"] = location_type

    # Extract experience requirements from title and description if not provided
    if job.get("experience_min") is None:
        from .experience import extract_experience_from_text
        e_min, e_max = extract_experience_from_text(job.get("title") or "", job.get("description") or "")
        if e_min is not None:
            job["experience_min"] = int(e_min) if isinstance(e_min, float) and e_min.is_integer() else e_min
        if e_max is not None and job.get("experience_max") is None:
            job["experience_max"] = int(e_max) if isinstance(e_max, float) and e_max.is_integer() else e_max

    return job


def queue_source_run(source_id, admin_id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO job_ingestion_runs (source_id, requested_by) VALUES (%s,%s)",
            (source_id, admin_id),
        )
        db.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        db.close()


def queue_source_run_once(source_id, admin_id):
    """Queue a source unless it already has queued/running work.

    Locking the source row makes the check-and-insert atomic across API
    workers. This is used by admin-triggered async runs so double-clicks,
    retries, and two administrators cannot launch duplicate scrapes.
    Returns ``(run_id, created)``.
    """
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        db.start_transaction()
        cursor.execute("SELECT id FROM job_sources WHERE id=%s FOR UPDATE", (source_id,))
        if cursor.fetchone() is None:
            db.rollback()
            return None, False
        cursor.execute(
            """SELECT id FROM job_ingestion_runs
               WHERE source_id=%s AND status IN ('queued','running')
               ORDER BY queued_at LIMIT 1""",
            (source_id,),
        )
        existing = cursor.fetchone()
        if existing:
            db.commit()
            return existing["id"], False
        cursor.execute(
            "INSERT INTO job_ingestion_runs (source_id, requested_by) VALUES (%s,%s)",
            (source_id, admin_id),
        )
        run_id = cursor.lastrowid
        db.commit()
        return run_id, True
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()


def recover_stale_runs(stale_seconds):
    """Requeue work abandoned by a terminated worker process.

    Called once when a worker starts. A generous threshold prevents a
    second worker from stealing a legitimately slow source while ensuring
    container restarts do not leave runs stuck as ``running`` forever.
    """
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            """UPDATE job_ingestion_runs
               SET status='queued', started_at=NULL,
                   error_message='Recovered after worker interruption'
               WHERE status='running' AND started_at IS NOT NULL
                 AND TIMESTAMPDIFF(SECOND, started_at, NOW()) >= %s""",
            (stale_seconds,),
        )
        recovered = cursor.rowcount
        db.commit()
        return recovered
    finally:
        cursor.close()
        db.close()


def claim_next_run():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        db.start_transaction()
        cursor.execute(
            "SELECT * FROM job_ingestion_runs WHERE status='queued' ORDER BY queued_at LIMIT 1 FOR UPDATE SKIP LOCKED"
        )
        run = cursor.fetchone()
        if not run:
            db.rollback()
            return None
        cursor.execute(
            "UPDATE job_ingestion_runs SET status='running', started_at=NOW() WHERE id=%s AND status='queued'",
            (run["id"],),
        )
        db.commit()
        return run
    finally:
        cursor.close()
        db.close()


def process_run(run_id):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT r.id AS run_id, s.* FROM job_ingestion_runs r
               JOIN job_sources s ON s.id=r.source_id WHERE r.id=%s""",
            (run_id,),
        )
        source = cursor.fetchone()
        if not source:
            raise RuntimeError("Ingestion run or source no longer exists")

        # DB time, not app-server time, so a clock-skewed container can never
        # misjudge which jobs this run actually touched (see the expiry
        # reconciliation below).
        cursor.execute("SELECT NOW() AS now")
        run_started_at = cursor.fetchone()["now"]

        cursor.execute("UPDATE job_sources SET status='validating' WHERE id=%s", (source["id"],))
        db.commit()

        scraped_jobs = scrape_source(source)
        inserted = updated = rejected = 0
        for raw_job in scraped_jobs:
            job = _clean_job(raw_job)
            if not job:
                rejected += 1
                continue
            expires_at = job.get("expires_at")
            if not expires_at:
                pub = job.get("published_at")
                if pub and isinstance(pub, (datetime, date)):
                    expires_at = pub + timedelta(days=30)
                else:
                    expires_at = datetime.utcnow() + timedelta(days=30)

            values = (
                source["id"], job["external_id"], job["title"], job["company"], job.get("location"),
                job.get("work_mode"), job.get("employment_type"), job.get("department"), job.get("category"),
                job.get("location_district"), job.get("location_region"), job.get("location_type"),
                job.get("experience_min"), job.get("experience_max"), job.get("salary_text"),
                job.get("description"), job["skills"], job["apply_url"], job.get("source_url"),
                job.get("published_at"), expires_at, job["content_hash"],
            )
            try:
                cursor.execute(
                    """INSERT INTO jobs (
                        source_id, external_id, title, company, location, work_mode,
                        employment_type, department, category, location_district, location_region,
                        location_type, experience_min, experience_max, salary_text,
                        description, skills, apply_url, source_url, published_at,
                        expires_at, content_hash, status
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')""",
                    values,
                )
                inserted += 1
            except mysql.connector.IntegrityError:
                cursor.execute(
                    """UPDATE jobs SET title=%s, company=%s, location=%s, work_mode=%s,
                       employment_type=%s, department=%s, category=%s, location_district=%s,
                       location_region=%s, location_type=%s, salary_text=%s, description=%s, skills=%s,
                       apply_url=%s, source_url=%s, published_at=%s, expires_at=%s,
                       status=IF(status='rejected', 'rejected', 'active'),
                       last_seen_at=NOW() WHERE content_hash=%s OR (source_id=%s AND external_id=%s)""",
                    (
                        job["title"], job["company"], job.get("location"), job.get("work_mode"),
                        job.get("employment_type"), job.get("department"), job.get("category"),
                        job.get("location_district"), job.get("location_region"), job.get("location_type"),
                        job.get("salary_text"), job.get("description"), job["skills"], job["apply_url"],
                        job.get("source_url"), job.get("published_at"), expires_at,
                        job["content_hash"], source["id"], job["external_id"],
                    ),
                )
                updated += cursor.rowcount

        raw_count = getattr(scraped_jobs, "raw_count", len(scraped_jobs))

        # Reconciliation: a job previously stored for this source that this
        # run did NOT see (its last_seen_at is still from before this run
        # started — every job actually re-seen above got last_seen_at=NOW()
        # via the insert default or the update branch) has disappeared from
        # the source, e.g. the posting was closed or pulled down. Expire it
        # rather than leaving a dead apply_url active in the feed forever.
        expired = 0
        if raw_count > 0:
            cursor.execute(
                """UPDATE jobs SET status='expired' WHERE source_id=%s AND status='active'
                   AND last_seen_at < %s""",
                (source["id"], run_started_at),
            )
            expired = cursor.rowcount


        cursor.execute(
            """UPDATE job_ingestion_runs SET status='completed', fetched_count=%s,
               inserted_count=%s, updated_count=%s, rejected_count=%s, expired_count=%s,
               error_message=NULL, completed_at=NOW()
               WHERE id=%s""",
            (len(scraped_jobs), inserted, updated, rejected, expired, run_id),
        )
        # Status must reflect what this source actually HAS on file, not
        # just what this one run happened to fetch — a source that has
        # stored jobs from an earlier run is still ACTIVE even if this
        # run's fetch came back empty (a board can go temporarily quiet
        # without the previously-collected postings becoming invalid).
        #
        # `raw_count` (only meaningful for providers that pre-filter, e.g.
        # Greenhouse's location/seniority filters inside fetch_and_normalize)
        # is how many jobs the provider itself published, before any of
        # that filtering — see providers/greenhouse.py's NormalizedJobs.
        # Providers that return a plain list (no such distinction) fall
        # back to treating their fetch count as the raw count.
        #
        #   stored_count > 0            -> ACTIVE (has jobs on file, even if
        #                                   tn_jobs == 0 or this run found none)
        #   stored_count == 0, raw == 0 -> EMPTY_BOARD (provider genuinely
        #                                   has zero published jobs)
        #   stored_count == 0, raw > 0  -> NO_MATCHING_JOBS (provider has
        #                                   jobs, but none ever passed our
        #                                   filters)
        # Excludes 'expired' only — every other pre-existing status (pending
        # moderation, active, even rejected) still counts as "this source has
        # real content on file" exactly as before introducing expiry above;
        # only the jobs this run just expired should stop counting.
        cursor.execute("SELECT COUNT(*) AS n FROM jobs WHERE source_id=%s AND status != 'expired'", (source["id"],))
        stored_count = cursor.fetchone()["n"]
        if stored_count > 0:
            success_status = "active"
        elif raw_count == 0:
            success_status = "empty_board"
        else:
            success_status = "no_matching_jobs"
        cursor.execute(
            """UPDATE job_sources SET last_run_at=NOW(), last_attempted_at=NOW(), last_validated_at=NOW(),
               last_success_at=NOW(), status=%s, error_category=NULL, last_error=NULL,
               consecutive_failures=0, last_fetched_count=%s WHERE id=%s""",
            (success_status, raw_count, source["id"]),
        )
        db.commit()
        return {"fetched": len(scraped_jobs), "inserted": inserted, "updated": updated, "rejected": rejected, "expired": expired}
    except Exception as exc:
        db.rollback()
        logger.exception("[Jobs] Ingestion run %s failed", run_id)
        # Duck-typed rather than importing any specific provider's error
        # class here: GreenhouseAPIError (and any future provider error)
        # exposes `.category` and `.permanent` for source-lifecycle
        # tracking; anything else (e.g. a bare RuntimeError) degrades to a
        # generic, transient classification rather than failing this
        # bookkeeping update.
        error_category = getattr(exc, "category", "unknown")
        permanent = bool(getattr(exc, "permanent", False))
        new_status = "invalid" if permanent else "temporarily_failed"
        error_db = get_db()
        error_cursor = error_db.cursor()
        try:
            error_cursor.execute(
                "UPDATE job_ingestion_runs SET status='failed', error_message=%s, completed_at=NOW() WHERE id=%s",
                (str(exc)[:4000], run_id),
            )
            error_cursor.execute(
                """UPDATE job_sources s JOIN job_ingestion_runs r ON r.source_id=s.id
                   SET s.last_error=%s, s.error_category=%s, s.status=%s, s.last_attempted_at=NOW(),
                       s.last_validated_at=NOW(), s.consecutive_failures = s.consecutive_failures + 1
                   WHERE r.id=%s""",
                (str(exc)[:4000], error_category, new_status, run_id),
            )
            error_db.commit()
        finally:
            error_cursor.close()
            error_db.close()
        raise
    finally:
        cursor.close()
        db.close()


def prune_expired_jobs_in_session(cursor, max_age_days: int = 30) -> dict:
    """Marks past-due jobs as expired and permanently removes jobs exceeding the 30-day retention window."""
    # 1. Mark active jobs whose 30-day lifecycle has ended as expired
    cursor.execute(
        """UPDATE jobs 
           SET status='expired' 
           WHERE status='active' AND (
               (expires_at IS NOT NULL AND expires_at < NOW())
               OR (published_at IS NOT NULL AND published_at < DATE_SUB(NOW(), INTERVAL %s DAY))
               OR (published_at IS NULL AND created_at < DATE_SUB(NOW(), INTERVAL %s DAY))
           )""",
        (max_age_days, max_age_days),
    )
    expired_count = cursor.rowcount

    # 2. Automatically delete/purge expired and rejected jobs that exceed 30 days retention
    cursor.execute(
        """DELETE FROM jobs 
           WHERE status IN ('expired', 'rejected') AND (
               (published_at IS NOT NULL AND published_at < DATE_SUB(NOW(), INTERVAL %s DAY))
               OR (created_at < DATE_SUB(NOW(), INTERVAL %s DAY))
           )""",
        (max_age_days, max_age_days),
    )
    deleted_count = cursor.rowcount
    if expired_count > 0 or deleted_count > 0:
        logger.info(
            "[Jobs][Retention] Pruned: %d marked expired, %d permanently removed (>%d days old)",
            expired_count, deleted_count, max_age_days,
        )
    return {"expired_count": expired_count, "deleted_count": deleted_count}


def prune_expired_jobs(max_age_days: int = 30) -> dict:
    """Standalone worker/API method to execute 30-day job lifecycle cleanup."""
    db = get_db()
    cursor = db.cursor()
    try:
        outcome = prune_expired_jobs_in_session(cursor, max_age_days=max_age_days)
        db.commit()
        return {"success": True, **outcome}
    except Exception as exc:
        logger.error("[Jobs][Retention] Error in prune_expired_jobs: %s", exc)
        return {"success": False, "error": str(exc)}
    finally:
        cursor.close()
        db.close()


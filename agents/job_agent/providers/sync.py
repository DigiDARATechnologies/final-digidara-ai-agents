import json
import logging

from ..db import get_db
from ..service import process_run, queue_source_run, queue_source_run_once
from .apify import get_apify_status
from .config_loader import (
    get_adzuna_config,
    get_apify_config,
    get_greenhouse_companies,
    get_jsearch_config,
    load_providers_config,
)


logger = logging.getLogger(__name__)


def _greenhouse_source_name(board_id):
    return f"greenhouse:{board_id}"


def sync_greenhouse_sources(config=None):
    """Reconcile `job_sources` rows with the companies configured in providers.yaml.

    Each enabled company becomes (or updates) one `source_type='greenhouse'`
    row keyed by a stable `greenhouse:<board_id>` name, reusing the existing
    job_sources table and its unique-name constraint for idempotent upserts.
    Companies removed or disabled in config are marked DISABLED (not
    deleted), so their previously collected jobs and run history are
    preserved and they can be re-enabled just by adding them back to config.

    A brand-new company row starts at status='discovered' (the table
    default). An already-known company's health status is deliberately
    left untouched here - re-running sync must not silently reset an
    INVALID or TEMPORARILY_FAILED source back to healthy; only an actual
    fetch attempt (process_run) or an explicit revalidate does that.

    Greenhouse's public Job Board API is a documented, no-auth endpoint
    meant for exactly this kind of third-party consumption, so these
    sources are marked pre-authorized rather than requiring a manual
    per-source admin approval step.
    """
    companies = get_greenhouse_companies(config)
    db = get_db()
    cursor = db.cursor()
    try:
        active_names = []
        for company in companies:
            name = _greenhouse_source_name(company["board_id"])
            active_names.append(name)
            source_url = (
                f"https://boards-api.greenhouse.io/v1/boards/{company['board_id']}/jobs?content=true"
            )
            parser_config = json.dumps({"board_id": company["board_id"], "company_name": company["name"]})
            cursor.execute(
                """INSERT INTO job_sources (
                       name, source_type, source_url, parser_config, is_active, scraping_authorized,
                       district, city, state, country, category
                   ) VALUES (%s, 'greenhouse', %s, %s, 1, 1, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE
                       source_url = VALUES(source_url),
                       parser_config = VALUES(parser_config),
                       is_active = 1,
                       status = IF(status = 'disabled', 'discovered', status),
                       district = VALUES(district),
                       city = VALUES(city),
                       state = VALUES(state),
                       country = VALUES(country),
                       category = VALUES(category)""",
                (
                    name, source_url, parser_config,
                    company.get("district"), company.get("city"), company.get("state"),
                    company.get("country"), company.get("category"),
                ),
            )

        if active_names:
            placeholders = ",".join(["%s"] * len(active_names))
            cursor.execute(
                f"""UPDATE job_sources SET is_active = 0, status = 'disabled'
                    WHERE source_type = 'greenhouse' AND status != 'disabled' AND name NOT IN ({placeholders})""",
                tuple(active_names),
            )
        else:
            cursor.execute(
                "UPDATE job_sources SET is_active = 0, status = 'disabled' "
                "WHERE source_type = 'greenhouse' AND status != 'disabled'"
            )

        db.commit()
        logger.info("[Jobs][Greenhouse] Synced %d configured company source(s)", len(companies))
        return len(companies)
    finally:
        cursor.close()
        db.close()


def _active_greenhouse_sources():
    """Sources due for an automatic collection attempt this run.

    Excludes INVALID sources (e.g. a 404 board-not-found) on purpose: a
    permanent failure will not fix itself by being retried every run, so
    it is skipped here and only re-attempted via explicit revalidation
    (see revalidate_greenhouse_source). DISABLED sources are already
    filtered out by is_active=1; the status check is kept too as a
    defensive belt-and-braces measure in case the two ever drift.
    TEMPORARILY_FAILED sources ARE included, since a transient failure
    (timeout, rate limit, server error) may well succeed on retry.
    """
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT * FROM job_sources
               WHERE source_type = 'greenhouse' AND is_active = 1
                 AND status NOT IN ('invalid', 'disabled')
               ORDER BY name"""
        )
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def _queue_sources(sources, admin_id):
    queued = []
    already_queued = []
    for source in sources:
        run_id, created = queue_source_run_once(source["id"], admin_id)
        item = {"source_id": source["id"], "source_name": source["name"], "run_id": run_id}
        (queued if created else already_queued).append(item)
    return {
        "queued_count": len(queued),
        "already_queued_count": len(already_queued),
        "queued": queued,
        "already_queued": already_queued,
    }


def queue_greenhouse_collection(admin_id=None):
    """Synchronize configuration and enqueue every eligible board.

    This performs no provider network I/O. The continuous worker claims and
    processes each returned run independently, outside the HTTP lifecycle.
    """
    sync_greenhouse_sources()
    sources = _active_greenhouse_sources()
    return {"ready": True, "source_count": len(sources), **_queue_sources(sources, admin_id)}


def revalidate_greenhouse_source(source_id, admin_id=None):
    """Force one Greenhouse source to be re-attempted right now, regardless of its current status.

    This is the escape hatch GOAL 3 asks for: an INVALID source (board not
    found) is deliberately excluded from automatic runs so it isn't
    retried forever, but an admin who has since fixed the board id in
    providers.yaml (or believes Greenhouse's outage has resolved) can
    force one real attempt here. Reuses the exact same
    queue_source_run/process_run pipeline as a normal run - no parallel
    execution path - so success/failure updates the source's status,
    error_category, and timestamps exactly the same way.
    """
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM job_sources WHERE id=%s AND source_type='greenhouse'", (source_id,))
        source = cursor.fetchone()
        if not source:
            return None
        cursor.execute(
            "UPDATE job_sources SET is_active=1, status='validating' WHERE id=%s",
            (source_id,),
        )
        db.commit()
    finally:
        cursor.close()
        db.close()

    run_id = queue_source_run(source_id, admin_id)
    try:
        result = process_run(run_id)
        outcome = {"status": "success", **result}
    except Exception as exc:  # noqa: BLE001 - report the failure, don't crash the request
        outcome = {"status": "failed", "error": str(exc)}

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM job_sources WHERE id=%s", (source_id,))
        updated_source = cursor.fetchone()
    finally:
        cursor.close()
        db.close()

    return {"source": updated_source, "run": outcome}


def run_greenhouse_collection(admin_id=None):
    """Run one full Greenhouse collection pass across every configured company.

    Each company is collected independently through the existing
    queue_source_run/process_run pipeline (identical dedup/upsert logic
    used by every other job source), and a failure on one company is
    logged and skipped rather than aborting the remaining companies.
    Returns an aggregate summary plus a per-company breakdown.
    """
    sync_greenhouse_sources()
    sources = _active_greenhouse_sources()

    logger.info("[Jobs][Greenhouse] Collection started (%d compan%s)", len(sources), "y" if len(sources) == 1 else "ies")
    totals = {"fetched": 0, "inserted": 0, "updated": 0, "rejected": 0, "expired": 0, "failed_companies": 0}
    companies_report = []

    for source in sources:
        parser_config = json.loads(source.get("parser_config") or "{}")
        company_name = parser_config.get("company_name") or source["name"]
        board_id = parser_config.get("board_id") or ""
        run_id = queue_source_run(source["id"], admin_id)
        try:
            result = process_run(run_id)
        except Exception as exc:  # noqa: BLE001 - one company's failure must not stop the others
            totals["failed_companies"] += 1
            logger.error(
                "[Jobs][Greenhouse] Company: %s | Board: %s | Failed: %s",
                company_name, board_id, exc,
            )
            companies_report.append(
                {"company": company_name, "board_id": board_id, "status": "failed", "error": str(exc)}
            )
            continue

        totals["fetched"] += result["fetched"]
        totals["inserted"] += result["inserted"]
        totals["updated"] += result["updated"]
        totals["rejected"] += result["rejected"]
        totals["expired"] += result["expired"]
        logger.info(
            "[Jobs][Greenhouse] Company: %s | Board: %s | Fetched: %d | Inserted: %d | Updated: %d | Skipped: %d | Expired: %d",
            company_name, board_id, result["fetched"], result["inserted"], result["updated"], result["rejected"], result["expired"],
        )
        companies_report.append({"company": company_name, "board_id": board_id, "status": "success", **result})

    logger.info(
        "[Jobs][Greenhouse] Collection completed | Total fetched: %d | Inserted: %d | Updated: %d | Failed companies: %d",
        totals["fetched"], totals["inserted"], totals["updated"], totals["failed_companies"],
    )
    return {"totals": totals, "companies": companies_report}


def _apify_source_name(actor_id):
    return f"apify:{actor_id}"


def sync_apify_sources(config=None):
    """Reconcile `job_sources` rows with the actors configured in providers.yaml.

    Mirrors sync_greenhouse_sources(): each *enabled* configured actor
    becomes one `source_type='apify'` row keyed by `apify:<actor_id>`,
    upserted idempotently via the existing unique-name constraint. A
    disabled actor (e.g. LinkedIn, pending its actor id) is deliberately
    never synced as a live source — same treatment as a disabled
    Greenhouse company.
    """
    apify_config = get_apify_config(config)
    actors = [actor for actor in apify_config["actors"] if actor["enabled"]]
    db = get_db()
    cursor = db.cursor()
    try:
        active_names = []
        for actor in actors:
            actor_id = actor["actor_id"]
            name = _apify_source_name(actor_id)
            active_names.append(name)
            source_url = f"https://console.apify.com/actors/{actor_id}"
            parser_config = json.dumps({
                "actor_id": actor_id,
                "platform": actor["platform"],
                "run_input": actor.get("run_input") or {},
            })
            cursor.execute(
                """INSERT INTO job_sources (name, source_type, source_url, parser_config, is_active, scraping_authorized)
                   VALUES (%s, 'apify', %s, %s, 1, 1)
                   ON DUPLICATE KEY UPDATE
                       source_url = VALUES(source_url),
                       parser_config = VALUES(parser_config),
                       is_active = 1,
                       scraping_authorized = 1""",
                (name, source_url, parser_config),
            )

        if active_names:
            placeholders = ",".join(["%s"] * len(active_names))
            cursor.execute(
                f"""UPDATE job_sources SET is_active = 0
                    WHERE source_type = 'apify' AND name NOT IN ({placeholders})""",
                tuple(active_names),
            )
        else:
            cursor.execute("UPDATE job_sources SET is_active = 0 WHERE source_type = 'apify'")

        db.commit()
        logger.info("[Jobs][Apify] Synced %d enabled actor source(s)", len(actors))
        return len(actors)
    finally:
        cursor.close()
        db.close()


def _active_apify_sources():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM job_sources WHERE source_type = 'apify' AND is_active = 1 ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def queue_apify_collection(admin_id=None, platform=None):
    """Validate Apify configuration, synchronize actors, and enqueue work.

    No actor is invoked in this request. When ``platform`` is provided only
    that configured actor is queued, preserving the manual per-platform UI.
    """
    config = load_providers_config()
    apify_config = get_apify_config(config)
    status = get_apify_status(apify_config)
    if not status["ready"]:
        return {"ready": False, "reason": status["reason"]}

    sync_apify_sources(config)
    sources = _active_apify_sources()
    if platform:
        sources = [
            source for source in sources
            if json.loads(source.get("parser_config") or "{}").get("platform") == platform
        ]
        if not sources:
            return {"ready": False, "reason": f"No enabled actor configured for platform '{platform}'"}

    return {
        "ready": True,
        "reason": "",
        "source_count": len(sources),
        "platform": platform,
        **_queue_sources(sources, admin_id),
    }


def run_apify_collection(admin_id=None, platform=None):
    """Run one Apify collection pass, across every enabled actor or just
    one when `platform` is given (e.g. the admin panel's per-platform
    "Run Naukri" / "Run LinkedIn" buttons — never a scheduled/automatic
    run, unlike Greenhouse).

    Fast-fails with a clear reason and touches neither the network nor the
    database when Apify isn't configured yet (no token, disabled, or no
    enabled actors) — see providers/apify.py. Once configured, this mirrors
    run_greenhouse_collection(): each actor goes through the existing
    queue_source_run/process_run pipeline, and a failure on one actor
    (including "no field mapping yet" for a platform not in
    apify.py's _NORMALIZERS) is recorded and skipped rather than aborting
    the rest.
    """
    config = load_providers_config()
    apify_config = get_apify_config(config)
    status = get_apify_status(apify_config)
    if not status["ready"]:
        logger.info("[Jobs][Apify] Skipped: %s", status["reason"])
        return {
            "ready": False,
            "reason": status["reason"],
            "totals": {"fetched": 0, "inserted": 0, "updated": 0, "rejected": 0, "failed_actors": 0},
            "actors": [],
        }

    sync_apify_sources(config)
    sources = _active_apify_sources()
    if platform:
        sources = [s for s in sources if json.loads(s.get("parser_config") or "{}").get("platform") == platform]
        if not sources:
            return {
                "ready": False,
                "reason": f"No enabled actor configured for platform '{platform}'",
                "totals": {"fetched": 0, "inserted": 0, "updated": 0, "rejected": 0, "failed_actors": 0},
                "actors": [],
            }

    logger.info("[Jobs][Apify] Collection started (%d actor(s))", len(sources))
    totals = {"fetched": 0, "inserted": 0, "updated": 0, "rejected": 0, "expired": 0, "failed_actors": 0}
    actors_report = []

    for source in sources:
        parser_config = json.loads(source.get("parser_config") or "{}")
        actor_id = parser_config.get("actor_id") or source["name"]
        run_id = queue_source_run(source["id"], admin_id)
        try:
            result = process_run(run_id)
        except Exception as exc:  # noqa: BLE001 - one actor's failure must not stop the others
            totals["failed_actors"] += 1
            logger.error("[Jobs][Apify] Actor: %s | Failed: %s", actor_id, exc)
            actors_report.append({"actor_id": actor_id, "status": "failed", "error": str(exc)})
            continue

        totals["fetched"] += result["fetched"]
        totals["inserted"] += result["inserted"]
        totals["updated"] += result["updated"]
        totals["rejected"] += result["rejected"]
        totals["expired"] += result["expired"]
        logger.info(
            "[Jobs][Apify] Actor: %s | Fetched: %d | Inserted: %d | Updated: %d | Skipped: %d | Expired: %d",
            actor_id, result["fetched"], result["inserted"], result["updated"], result["rejected"], result["expired"],
        )
        actors_report.append({"actor_id": actor_id, "status": "success", **result})

    logger.info(
        "[Jobs][Apify] Collection completed | Total fetched: %d | Inserted: %d | Updated: %d | Failed actors: %d",
        totals["fetched"], totals["inserted"], totals["updated"], totals["failed_actors"],
    )
    return {"ready": True, "reason": "", "totals": totals, "actors": actors_report}


def _adzuna_source_name(what, where):
    clean_what = what.strip().lower().replace(" ", "_")
    clean_where = where.strip().lower().replace(" ", "_")
    return f"adzuna:{clean_what}@{clean_where}"


def sync_adzuna_sources(config=None):
    """Reconcile `job_sources` rows with the Adzuna queries configured in providers.yaml."""
    adzuna_config = get_adzuna_config(config)
    queries = adzuna_config["queries"] if adzuna_config["enabled"] else []
    db = get_db()
    cursor = db.cursor()
    try:
        active_names = []
        for q in queries:
            what = q.get("what", "")
            where = q.get("where", "")
            name = _adzuna_source_name(what, where)
            active_names.append(name)
            source_url = f"https://api.adzuna.com/v1/api/jobs/in/search?what={what}&where={where}"
            parser_config = json.dumps({"what": what, "where": where, "page": 1, "results_per_page": 20})
            cursor.execute(
                """INSERT INTO job_sources (name, source_type, source_url, parser_config, is_active, scraping_authorized)
                   VALUES (%s, 'adzuna', %s, %s, 1, 1)
                   ON DUPLICATE KEY UPDATE
                       source_url = VALUES(source_url),
                       parser_config = VALUES(parser_config),
                       is_active = 1,
                       scraping_authorized = 1""",
                (name, source_url, parser_config),
            )

        if active_names:
            placeholders = ",".join(["%s"] * len(active_names))
            cursor.execute(
                f"""UPDATE job_sources SET is_active = 0
                    WHERE source_type = 'adzuna' AND name NOT IN ({placeholders})""",
                tuple(active_names),
            )
        else:
            cursor.execute("UPDATE job_sources SET is_active = 0 WHERE source_type = 'adzuna'")

        db.commit()
        logger.info("[Jobs][Adzuna] Synced %d query source(s)", len(queries))
        return len(queries)
    finally:
        cursor.close()
        db.close()


def _active_adzuna_sources():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM job_sources WHERE source_type = 'adzuna' AND is_active = 1 ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def queue_adzuna_collection(admin_id=None):
    from .adzuna import is_configured as is_adzuna_configured
    if not is_adzuna_configured():
        return {"ready": False, "reason": "ADZUNA_APP_ID or ADZUNA_APP_KEY is not configured"}
    sync_adzuna_sources()
    sources = _active_adzuna_sources()
    return {"ready": True, "source_count": len(sources), **_queue_sources(sources, admin_id)}


def _jsearch_source_name(query):
    clean_q = query.strip().lower().replace(" ", "_")
    return f"jsearch:{clean_q}"


def sync_jsearch_sources(config=None):
    """Reconcile `job_sources` rows with the JSearch queries configured in providers.yaml."""
    jsearch_config = get_jsearch_config(config)
    queries = jsearch_config["queries"] if jsearch_config["enabled"] else []
    db = get_db()
    cursor = db.cursor()
    try:
        active_names = []
        for q in queries:
            query_str = q.get("query", "")
            name = _jsearch_source_name(query_str)
            active_names.append(name)
            source_url = f"https://jsearch.p.rapidapi.com/search?query={query_str}"
            parser_config = json.dumps({"query": query_str, "page": 1, "num_pages": 1})
            cursor.execute(
                """INSERT INTO job_sources (name, source_type, source_url, parser_config, is_active, scraping_authorized)
                   VALUES (%s, 'jsearch', %s, %s, 1, 1)
                   ON DUPLICATE KEY UPDATE
                       source_url = VALUES(source_url),
                       parser_config = VALUES(parser_config),
                       is_active = 1,
                       scraping_authorized = 1""",
                (name, source_url, parser_config),
            )

        if active_names:
            placeholders = ",".join(["%s"] * len(active_names))
            cursor.execute(
                f"""UPDATE job_sources SET is_active = 0
                    WHERE source_type = 'jsearch' AND name NOT IN ({placeholders})""",
                tuple(active_names),
            )
        else:
            cursor.execute("UPDATE job_sources SET is_active = 0 WHERE source_type = 'jsearch'")

        db.commit()
        logger.info("[Jobs][JSearch] Synced %d query source(s)", len(queries))
        return len(queries)
    finally:
        cursor.close()
        db.close()


def _active_jsearch_sources():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM job_sources WHERE source_type = 'jsearch' AND is_active = 1 ORDER BY name")
        return cursor.fetchall()
    finally:
        cursor.close()
        db.close()


def queue_jsearch_collection(admin_id=None):
    from .jsearch import is_configured as is_jsearch_configured
    if not is_jsearch_configured():
        return {"ready": False, "reason": "RAPIDAPI_KEY is not configured"}
    sync_jsearch_sources()
    sources = _active_jsearch_sources()
    return {"ready": True, "source_count": len(sources), **_queue_sources(sources, admin_id)}


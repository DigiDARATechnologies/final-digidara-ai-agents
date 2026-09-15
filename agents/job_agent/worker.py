import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from .config import RUN_STALE_SECONDS, WORKER_HEARTBEAT_FILE, WORKER_HEARTBEAT_STALE_SECONDS, WORKER_POLL_SECONDS
from .automation import queue_due_automation
from .db import init_job_tables
from .providers.sync import run_apify_collection, run_greenhouse_collection, sync_greenhouse_sources
from .service import claim_next_run, process_run, recover_stale_runs


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _touch_heartbeat():
    """Record that the main loop is still alive. Best-effort: a failure to
    write must never crash the worker — it would just make the next
    `--healthcheck` call report unhealthy instead, which is the correct
    outcome anyway."""
    try:
        with open(WORKER_HEARTBEAT_FILE, "w", encoding="utf-8") as handle:
            handle.write(str(time.time()))
    except OSError:
        logger.warning("Could not write worker heartbeat file at %s", WORKER_HEARTBEAT_FILE, exc_info=True)


def _heartbeat_is_fresh():
    try:
        age_seconds = time.time() - os.path.getmtime(WORKER_HEARTBEAT_FILE)
    except OSError:
        return False
    return age_seconds < WORKER_HEARTBEAT_STALE_SECONDS


def run_once():
    run = claim_next_run()
    if not run:
        return False
    try:
        process_run(run["id"])
    except Exception:
        logger.exception("Ingestion run %s failed", run["id"])
    return True


def main():
    parser = argparse.ArgumentParser(description="DigiDARA jobs ingestion worker")
    parser.add_argument("--once", action="store_true", help="Process one queued run and exit")
    parser.add_argument(
        "--sync-providers",
        action="store_true",
        help="Reconcile job_sources with providers.yaml (e.g. Greenhouse companies) and exit",
    )
    parser.add_argument(
        "--run-greenhouse",
        action="store_true",
        help="Sync and collect every configured Greenhouse company once, then exit",
    )
    parser.add_argument(
        "--run-apify",
        action="store_true",
        help="Attempt an Apify collection pass (no-op until APIFY_API_TOKEN and an actor are configured), then exit",
    )
    parser.add_argument(
        "--healthcheck",
        action="store_true",
        help="Exit 0 if the running worker's heartbeat is fresh, else 1 — used by Docker's HEALTHCHECK. "
             "Does not touch the database, so it stays fast and cheap on every check.",
    )
    args = parser.parse_args()

    if args.healthcheck:
        sys.exit(0 if _heartbeat_is_fresh() else 1)

    init_job_tables()
    recovered = recover_stale_runs(RUN_STALE_SECONDS)
    if recovered:
        logger.warning("Recovered %s stale ingestion run(s)", recovered)

    if args.sync_providers:
        sync_greenhouse_sources()
        return
    if args.run_greenhouse:
        run_greenhouse_collection()
        return
    if args.run_apify:
        run_apify_collection()
        return
    if args.once:
        run_once()
        return

    logger.info("Jobs worker started; polling every %s seconds", WORKER_POLL_SECONDS)
    while True:
        _touch_heartbeat()
        try:
            scheduled = queue_due_automation()
            if scheduled["due"]:
                logger.info("Queued scheduled Greenhouse collection: %s source(s)", scheduled["queued_count"])
        except Exception:
            # An automation failure must never stop manual/admin queued runs.
            logger.exception("Scheduled Greenhouse collection could not be queued")
        if not run_once():
            time.sleep(WORKER_POLL_SECONDS)


if __name__ == "__main__":
    main()

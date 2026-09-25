"""Entrypoint: `python run.py` from inside agents/job_agent, same convention
as every other Flask agent in this repo (codeforge_agent, resume_builder_agent,
communication-ai-agent all start with `python run.py` from their own directory
— see README.md).

`app.py` uses package-relative imports (`.db`, `.routes`, ...), so this file
puts this folder's *parent* on sys.path before importing, letting
`job_agent` be imported as a real package regardless of the current working
directory the script was launched from.
"""
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if __name__ == "__main__":
    # waitress.serve() logs its own "Serving on ..." line at INFO level, which
    # is invisible under Python's default WARNING root log level — this made
    # a successfully-running server look like it printed nothing at all.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    from waitress import serve

    from job_agent.app import create_app

    port = int(os.getenv("PORT", "5020"))
    app = create_app()

    # Automatically start the background ingestion queue worker thread unless disabled
    enable_embedded_worker = os.getenv("JOBS_EMBEDDED_WORKER", "true").strip().lower() in {"1", "true", "yes"}
    if enable_embedded_worker:
        import threading
        import time
        from job_agent.config import RUN_STALE_SECONDS, WORKER_POLL_SECONDS
        from job_agent.automation import queue_due_automation
        from job_agent.service import recover_stale_runs
        from job_agent.worker import run_once

        def _worker_daemon_loop():
            worker_log = logging.getLogger("job_agent.worker")
            worker_log.info("Job Agent embedded ingestion worker started (polling every %ss)", WORKER_POLL_SECONDS)
            try:
                recovered = recover_stale_runs(RUN_STALE_SECONDS)
                if recovered:
                    worker_log.warning("Recovered %s stale ingestion run(s)", recovered)
            except Exception as exc:
                worker_log.warning("Stale run recovery check skipped: %s", exc)

            while True:
                try:
                    queue_due_automation()
                except Exception:
                    pass

                try:
                    had_work = run_once()
                except Exception as exc:
                    worker_log.error("Ingestion pass error: %s", exc)
                    had_work = False

                if not had_work:
                    time.sleep(WORKER_POLL_SECONDS)

        worker_thread = threading.Thread(target=_worker_daemon_loop, daemon=True, name="JobAgentEmbeddedWorker")
        worker_thread.start()

    logging.getLogger("job_agent.run").info("job_agent starting on http://0.0.0.0:%s (health: /health)", port)
    serve(app, host="0.0.0.0", port=port, threads=8)

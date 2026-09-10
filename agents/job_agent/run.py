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
    logging.getLogger("job_agent.run").info("job_agent starting on http://0.0.0.0:%s (health: /health)", port)
    serve(app, host="0.0.0.0", port=port, threads=8)

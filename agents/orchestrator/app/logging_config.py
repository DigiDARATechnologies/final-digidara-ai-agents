import logging
import sys

from app import config

# Third-party libraries are extremely chatty at DEBUG (every TLS handshake,
# every socket event). Pin these to WARNING regardless of LOG_LEVEL so they
# don't drown out the orchestrator's own routing decisions.
_NOISY_LOGGERS = ("httpx", "httpcore", "LiteLLM", "litellm", "urllib3", "sqlalchemy.engine")


def setup_logging() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )

    for name in ("orchestrator.api", "orchestrator.graph", "orchestrator.llm", "orchestrator.registry"):
        logging.getLogger(name).setLevel(config.LOG_LEVEL)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

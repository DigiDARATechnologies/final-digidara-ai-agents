import logging
import sys

from app import config

# Third-party libraries are extremely chatty at DEBUG (every TLS handshake,
# every socket event). "Detailed debugs" means the app's own decisions, not
# httpx/httpcore/LiteLLM internals — pin these to WARNING regardless of
# LOG_LEVEL so they don't drown out anything useful.
_NOISY_LOGGERS = ("httpx", "httpcore", "LiteLLM", "litellm", "urllib3")


def setup_logging() -> None:
    """Configures logging so every `capstone.*` logger (LLM calls, graph node
    execution, API requests) prints to the terminal alongside uvicorn's own
    request access log. Call this once, before anything else, at the top of
    the app entrypoint."""
    # Windows consoles often default to a non-UTF-8 codepage, which turns any
    # em-dash / non-ASCII character in our log messages into "?" or mojibake.
    # Force UTF-8 on the streams the logging handlers below write to.
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

    for name in ("capstone.api", "capstone.graph", "capstone.llm"):
        logging.getLogger(name).setLevel(config.LOG_LEVEL)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

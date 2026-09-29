"""Long-term memory for the Resume Builder chat, backed by mem0.

Every chat turn is added to the candidate's memory (keyed by their verified
platform user id), and the memories most relevant to a new message are
recalled into the chat prompt -- so "change my college" or "use the same
education as last time" can be answered from what the candidate told us
earlier, in this chat or a previous one.

Memory is optional and never on the critical path:
- It is off unless MEM0_ENABLED is true and OPENAI_API_KEY is set (mem0 uses
  OpenAI for fact extraction and embeddings).
- Memories live in a Qdrant server (MEM0_QDRANT_HOST/PORT, the `qdrant`
  service in docker-compose.yml): the agent runs several gunicorn workers,
  and mem0's embedded on-disk store can only be opened by one process.
- Any failure (mem0 not installed, Qdrant or OpenAI unreachable) is logged
  and the chat carries on without memory.
- Adding a turn happens on a background thread, so it never slows a reply.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client: Any = None
_failed = False


def memory_enabled() -> bool:
    return (
        os.getenv("MEM0_ENABLED", "").strip().lower() in {"1", "true", "yes"}
        and bool(os.getenv("OPENAI_API_KEY"))
    )


def _config() -> dict[str, Any]:
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": os.getenv("MEM0_COLLECTION", "resume_builder_memory"),
                "host": os.getenv("MEM0_QDRANT_HOST", "qdrant"),
                "port": int(os.getenv("MEM0_QDRANT_PORT", "6333")),
                "embedding_model_dims": 1536,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {"model": os.getenv("MEM0_LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini", "temperature": 0},
        },
        "embedder": {
            "provider": "openai",
            "config": {"model": os.getenv("MEM0_EMBEDDING_MODEL", "text-embedding-3-small")},
        },
        "history_db_path": os.path.join(os.getenv("MEM0_DIR", "/tmp/mem0"), "history.db"),
        "custom_instructions": (
            "Remember facts a candidate states about themselves for their resume: name, contact details, "
            "target role, education (degree, college, years, marks), work experience (company, role, dates), "
            "projects, skills, certifications, achievements, links, and corrections to any of these. "
            "A correction replaces the earlier fact."
        ),
    }


def _memory():
    global _client, _failed
    if not memory_enabled() or _failed:
        return None
    if _client is not None:
        return _client
    with _lock:
        if _client is None and not _failed:
            try:
                # Read by mem0 at import time: no usage data leaves the server.
                os.environ.setdefault("MEM0_TELEMETRY", "False")
                os.environ.setdefault("MEM0_DIR", "/tmp/mem0")
                os.makedirs(os.environ["MEM0_DIR"], exist_ok=True)
                from mem0 import Memory

                _client = Memory.from_config(_config())
            except Exception:
                _failed = True
                logger.warning("mem0 memory is unavailable; the chat continues without it.", exc_info=True)
    return _client


def recall(user_id: str | None, query: str, limit: int = 8) -> list[str]:
    """The candidate's memories most relevant to `query` (empty when memory
    is off, unavailable, or the user is unknown)."""
    memory = _memory() if user_id else None
    if memory is None or not query.strip():
        return []
    try:
        found = memory.search(query, top_k=limit, filters={"user_id": user_id})
    except Exception:
        logger.warning("mem0 search failed", exc_info=True)
        return []
    results = found.get("results", []) if isinstance(found, dict) else found or []
    return [str(item.get("memory")) for item in results if isinstance(item, dict) and item.get("memory")]


def remember(user_id: str | None, messages: list[dict[str, str]]) -> None:
    """Adds a chat turn to the candidate's memory in the background."""
    memory = _memory() if user_id else None
    turns = [m for m in messages if m.get("content")]
    if memory is None or not turns:
        return

    def add():
        try:
            memory.add(turns, user_id=user_id, metadata={"source": "resume_builder_chat"})
        except Exception:
            logger.warning("mem0 add failed", exc_info=True)

    threading.Thread(target=add, name="mem0-add", daemon=True).start()


def forget(user_id: str | None) -> None:
    """Deletes every memory for the candidate (their data-erasure request)."""
    memory = _memory() if user_id else None
    if memory is None:
        return
    try:
        memory.delete_all(user_id=user_id)
    except Exception:
        logger.warning("mem0 delete_all failed", exc_info=True)

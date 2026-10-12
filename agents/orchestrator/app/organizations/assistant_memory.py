"""Long-term memory for the organization assistant, backed by mem0.

Each organization admin has their own memory per organization (keyed
"org:<org_id>:<user_id>"), so the assistant remembers what they care about
-- "I look after the CSE final years", "flag anyone under 30" -- across
sessions, and never mixes two organizations.

Memory is optional and never on the critical path:
- It is off unless MEM0_ENABLED is true and OPENAI_API_KEY is set (mem0 uses
  OpenAI for fact extraction and embeddings).
- Memories live in the Qdrant server (MEM0_QDRANT_HOST/PORT, the `qdrant`
  service in docker-compose.yml) in their own collection: the orchestrator
  runs several gunicorn workers, which mem0's embedded store cannot share.
- Any failure is logged and the assistant carries on without memory.
- Adding a turn happens on a background thread, so it never slows a reply.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger("orchestrator.org_assistant.memory")

_lock = threading.Lock()
_client: Any = None
_failed = False


def memory_key(org_id: str, user_id: str) -> str:
    return f"org:{org_id}:{user_id}"


def memory_enabled() -> bool:
    return os.getenv("MEM0_ENABLED", "").strip().lower() in {"1", "true", "yes"} and bool(os.getenv("OPENAI_API_KEY"))


def _config() -> dict[str, Any]:
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": os.getenv("MEM0_COLLECTION", "org_assistant_memory"),
                "host": os.getenv("MEM0_QDRANT_HOST", "qdrant"),
                "port": int(os.getenv("MEM0_QDRANT_PORT", "6333")),
                "embedding_model_dims": 1536,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {"model": os.getenv("MEM0_LLM_MODEL") or "gpt-4o-mini", "temperature": 0},
        },
        "embedder": {
            "provider": "openai",
            "config": {"model": os.getenv("MEM0_EMBEDDING_MODEL", "text-embedding-3-small")},
        },
        "history_db_path": os.path.join(os.getenv("MEM0_DIR", "/tmp/mem0"), "org_history.db"),
        "custom_instructions": (
            "Remember what an organization admin tells you about how they work: the departments, years, "
            "sections and learners they look after, the thresholds and goals they set, recurring questions, "
            "and preferences for how answers are given. Do not store learners' personal details or scores; "
            "those are always read fresh. A correction replaces the earlier fact."
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
                os.environ.setdefault("MEM0_TELEMETRY", "False")
                os.environ.setdefault("MEM0_DIR", "/tmp/mem0")
                os.makedirs(os.environ["MEM0_DIR"], exist_ok=True)
                from mem0 import Memory

                _client = Memory.from_config(_config())
            except Exception:
                _failed = True
                logger.warning("mem0 memory is unavailable; the assistant continues without it.", exc_info=True)
    return _client


def recall(key: str, query: str, limit: int = 5) -> list[str]:
    memory = _memory()
    if memory is None or not query.strip():
        return []
    try:
        found = memory.search(query, top_k=limit, filters={"user_id": key})
    except Exception:
        logger.warning("mem0 search failed", exc_info=True)
        return []
    results = found.get("results", []) if isinstance(found, dict) else found or []
    return [str(item.get("memory"))[:300] for item in results if isinstance(item, dict) and item.get("memory")]


def remember(key: str, messages: list[dict[str, str]]) -> None:
    memory = _memory()
    turns = [m for m in messages if m.get("content")]
    if memory is None or not turns:
        return

    def add():
        try:
            memory.add(turns, user_id=key, metadata={"source": "org_assistant"})
        except Exception:
            logger.warning("mem0 add failed", exc_info=True)

    threading.Thread(target=add, name="mem0-org-add", daemon=True).start()


def forget(key: str) -> None:
    memory = _memory()
    if memory is None:
        return
    try:
        memory.delete_all(user_id=key)
    except Exception:
        logger.warning("mem0 delete_all failed", exc_info=True)

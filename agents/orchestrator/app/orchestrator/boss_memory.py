"""Boss's long-term memory (mem0): what each learner asked and was told in
the general chat, across chats and sessions, so Boss can answer "the
question I asked last time" and pick up where they left off.

Stored per learner ("boss:<user_id>") in its own Qdrant collection, beside
the organization assistant's (app/organizations/assistant_memory.py). Like
it, memory is optional: a slow or failing recall is skipped rather than
delaying the reply, and remembering runs in the background. A learner's
memories are part of their data export and are erased with their account.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from app.organizations.assistant_memory import Mem0Store

logger = logging.getLogger("orchestrator.boss.memory")

# Recall has to be quick: Boss's reply waits for it.
RECALL_SECONDS = 1.0
# mem0 keeps a learner's conversations as a few short facts, so Boss reads
# the newest of them all (a plain read, milliseconds) rather than searching
# by the question, which needs an OpenAI embedding first (0.5-6 s measured).
RECALL_LATEST = 20

_store = Mem0Store(
    os.getenv("MEM0_BOSS_COLLECTION", "boss_memory"),
    "boss_history.db",
    (
        "Remember what a learner tells Boss, DigiDARA's assistant, and what they ask: their goals, target "
        "role, interests and plans, the questions they asked and the gist of each answer, which agents they "
        "were interested in, and how they like answers (for example short, in English). A correction "
        "replaces the earlier fact. Never store passwords, OTPs, phone numbers, payment or card details."
    ),
    "boss",
)
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="boss-recall")


def warm_up() -> None:
    """Load mem0 now, in the background, so this worker's first learner does
    not wait for it (loading takes a second or more; recall would time out)."""
    _pool.submit(_store._memory)


def _key(user_id: str) -> str:
    return f"boss:{user_id}"


def recall(user_id: str, question: str = "") -> list[str]:
    """What Boss remembers about this learner, newest last ([] when off, slow or failing)."""
    future = _pool.submit(_store.all, _key(user_id), RECALL_LATEST)
    try:
        return future.result(timeout=RECALL_SECONDS)
    except FutureTimeout:
        logger.info("boss memory recall took longer than %.1fs; answering without it", RECALL_SECONDS)
        return []
    except Exception:
        logger.warning("boss memory recall failed", exc_info=True)
        return []


def remember(user_id: str, question: str, reply: str | None) -> None:
    _store.remember(_key(user_id), [{"role": "user", "content": question}, {"role": "assistant", "content": reply or ""}])


def export(user_id: str) -> list[str]:
    return _store.all(_key(user_id))


def forget(user_id: str) -> None:
    _store.forget(_key(user_id))

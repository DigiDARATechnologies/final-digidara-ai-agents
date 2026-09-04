"""Process-local, attempt-scoped caches for live OpenAI output.

Nothing in this module writes a generated question or hint to MySQL.  The
cache is deliberately ephemeral: a process restart, TTL expiry, completion,
or abandonment discards it.
"""

from concurrent.futures import ThreadPoolExecutor
import threading
import time
import uuid

from flask import current_app


_lock = threading.RLock()
_question_entries = {}
_hint_entries = {}
_executor = None
_executor_workers = None


def _get_executor(workers):
    global _executor, _executor_workers
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="question-prefetch")
            _executor_workers = workers
        return _executor


def _slot_signature(slot):
    return (slot.get("category"), slot.get("topic"), slot.get("difficulty"))


def _purge_expired(now=None):
    now = now or time.monotonic()
    for test_id, entry in list(_question_entries.items()):
        if entry["expires_at"] <= now:
            _question_entries.pop(test_id, None)
    for key, entry in list(_hint_entries.items()):
        if entry["expires_at"] <= now:
            _hint_entries.pop(key, None)


def schedule_question_prefetch(test_id, sequence, slot, excluded_questions):
    """Start one non-blocking OpenAI generation for an attempt's next slot."""
    if not current_app.config.get("QUESTION_PREFETCH_ENABLED", True):
        return False
    app = current_app._get_current_object()
    ttl = app.config["QUESTION_PREFETCH_TTL_SECONDS"]
    token = str(uuid.uuid4())
    signature = _slot_signature(slot)
    now = time.monotonic()
    with _lock:
        _purge_expired(now)
        existing = _question_entries.get(test_id)
        if (
            existing
            and existing["sequence"] == sequence
            and existing["signature"] == signature
            and existing["status"] in {"generating", "ready"}
        ):
            return False
        _question_entries[test_id] = {
            "token": token,
            "sequence": sequence,
            "signature": signature,
            "status": "generating",
            "created_at": now,
            "expires_at": now + ttl,
        }

    def generate():
        started = time.perf_counter()
        try:
            with app.app_context():
                from .test_generation import generate_questions

                timeout = app.config["QUESTION_PREFETCH_TIMEOUT_SECONDS"]
                generated, model, usage = generate_questions(
                    [dict(slot)],
                    avoid_questions=list(excluded_questions),
                    allow_demo_fallback=False,
                    deadline=time.monotonic() + timeout,
                    max_validation_attempts=3,
                    background=True,
                )
                elapsed_ms = (time.perf_counter() - started) * 1000
                with _lock:
                    entry = _question_entries.get(test_id)
                    if not entry or entry["token"] != token:
                        app.logger.info(
                            "Question prefetch discarded test=%s sequence=%s reason=stale duration_ms=%.2f",
                            test_id, sequence, elapsed_ms,
                        )
                        return
                    entry.update({
                        "status": "ready",
                        "item": generated[0],
                        "model": model,
                        "usage": usage,
                        "generation_ms": round(elapsed_ms, 2),
                        "expires_at": time.monotonic() + ttl,
                    })
                app.logger.info(
                    "Question prefetch completed test=%s sequence=%s category=%s difficulty=%s "
                    "duration_ms=%.2f model=%s provider_wait_ms=%s validation_attempts=%s",
                    test_id, sequence, slot.get("category"), slot.get("difficulty"), elapsed_ms,
                    model, usage.get("provider_wait_ms", 0), usage.get("validation_attempt_count", 1),
                )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            with _lock:
                entry = _question_entries.get(test_id)
                if entry and entry["token"] == token:
                    _question_entries.pop(test_id, None)
            with app.app_context():
                app.logger.warning(
                    "Question prefetch failed test=%s sequence=%s duration_ms=%.2f "
                    "error_type=%s error=%s",
                    test_id, sequence, elapsed_ms, type(exc).__name__, str(exc)[:300],
                )

    _get_executor(app.config["QUESTION_PREFETCH_WORKERS"]).submit(generate)
    app.logger.info(
        "Question prefetch scheduled test=%s sequence=%s category=%s topic=%s difficulty=%s",
        test_id, sequence, slot.get("category"), slot.get("topic"), slot.get("difficulty"),
    )
    return True


def consume_question_prefetch(test_id, sequence, slot):
    """Atomically consume a matching ready question; never wait for a future."""
    with _lock:
        _purge_expired()
        entry = _question_entries.get(test_id)
        if not entry:
            return None
        if entry["sequence"] != sequence or entry["signature"] != _slot_signature(slot):
            _question_entries.pop(test_id, None)
            return None
        if entry["status"] != "ready":
            # The request must not wait for the background future. Removing the
            # token also prevents its eventual result from being published.
            _question_entries.pop(test_id, None)
            return None
        _question_entries.pop(test_id, None)
        return {
            "item": entry["item"],
            "model": entry["model"],
            "usage": entry["usage"],
            "generation_ms": entry.get("generation_ms", 0),
        }


def cache_hint(test_id, question_id, hint):
    ttl = current_app.config["QUESTION_PREFETCH_TTL_SECONDS"]
    with _lock:
        _purge_expired()
        _hint_entries[(test_id, question_id)] = {
            "hint": hint,
            "expires_at": time.monotonic() + ttl,
        }


def get_cached_hint(test_id, question_id):
    with _lock:
        _purge_expired()
        entry = _hint_entries.get((test_id, question_id))
        return entry["hint"] if entry else None


def clear_hint(test_id, question_id):
    with _lock:
        _hint_entries.pop((test_id, question_id), None)


def clear_test_cache(test_id):
    with _lock:
        _question_entries.pop(test_id, None)
        for key in [key for key in _hint_entries if key[0] == test_id]:
            _hint_entries.pop(key, None)

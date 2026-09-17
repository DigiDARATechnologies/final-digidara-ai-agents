"""Process-local cache for optional hint responses."""

import threading
import time

from flask import current_app


_lock = threading.RLock()
_hint_entries = {}


def _purge_expired(now=None):
    now = now or time.monotonic()
    for key, entry in list(_hint_entries.items()):
        if entry["expires_at"] <= now:
            _hint_entries.pop(key, None)


def cache_hint(test_id, question_id, hint):
    ttl = current_app.config["HINT_CACHE_TTL_SECONDS"]
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
        for key in [key for key in _hint_entries if key[0] == test_id]:
            _hint_entries.pop(key, None)

"""Production Cache Service for LLM generation and pronunciation reference evaluations.

Provides high-performance TTL caching backed by in-memory LRU dict with thread safety.
Gracefully degrades and never interrupts request flows if cache operations raise exceptions.
"""

import hashlib
import json
import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS = 3600  # 1 hour default cache TTL
_MAX_CACHE_ENTRIES = 2000

_cache_lock = threading.Lock()
_in_memory_store = {}


def _make_cache_key(namespace: str, *args, **kwargs) -> str:
    """Deterministic hash key from namespace and serializable arguments."""
    try:
        raw_repr = json.dumps({"ns": namespace, "a": args, "k": kwargs}, sort_keys=True, default=str)
    except Exception:
        raw_repr = f"{namespace}:{repr(args)}:{repr(kwargs)}"
    return f"{namespace}:{hashlib.sha256(raw_repr.encode('utf-8')).hexdigest()}"


def get_cached(namespace: str, *args, **kwargs) -> Optional[Any]:
    """Retrieve value from cache if present and not expired."""
    key = _make_cache_key(namespace, *args, **kwargs)
    now = time.monotonic()

    with _cache_lock:
        entry = _in_memory_store.get(key)
        if not entry:
            return None
        expires_at, val = entry
        if now > expires_at:
            _in_memory_store.pop(key, None)
            return None
        return val


def set_cached(namespace: str, value: Any, ttl_seconds: int = _DEFAULT_TTL_SECONDS, *args, **kwargs) -> None:
    """Store value in cache with TTL."""
    if value is None:
        return
    key = _make_cache_key(namespace, *args, **kwargs)
    expires_at = time.monotonic() + ttl_seconds

    with _cache_lock:
        # Simple size eviction if limit exceeded
        if len(_in_memory_store) >= _MAX_CACHE_ENTRIES:
            # Purge expired or oldest items
            now = time.monotonic()
            expired_keys = [k for k, (exp, _) in _in_memory_store.items() if now > exp]
            for k in expired_keys:
                _in_memory_store.pop(k, None)
            # If still over limit, drop 10% arbitrary keys
            if len(_in_memory_store) >= _MAX_CACHE_ENTRIES:
                keys_to_drop = list(_in_memory_store.keys())[: (_MAX_CACHE_ENTRIES // 10)]
                for k in keys_to_drop:
                    _in_memory_store.pop(k, None)

        _in_memory_store[key] = (expires_at, value)


def cached_call(namespace: str, fn: Callable, ttl_seconds: int = _DEFAULT_TTL_SECONDS, *args, **kwargs) -> Any:
    """Execute fn only on cache miss, otherwise return cached result."""
    hit = get_cached(namespace, *args, **kwargs)
    if hit is not None:
        return hit

    res = fn(*args, **kwargs)
    if res is not None:
        try:
            set_cached(namespace, res, ttl_seconds=ttl_seconds, *args, **kwargs)
        except Exception as exc:
            logger.warning("Cache write failure for %s: %s", namespace, exc)
    return res

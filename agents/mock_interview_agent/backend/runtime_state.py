"""Bounded process-local coordination primitives shared by routes."""

from keyed_locks import KeyedLockPool
from ttl_cache import BoundedTTLCache


submission_locks = KeyedLockPool()
dashboard_cache = BoundedTTLCache(ttl_seconds=60, max_entries=1000)

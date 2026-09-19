"""Small thread-safe bounded TTL cache for process-local API payloads."""

from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic


class BoundedTTLCache:
    """Store copied values for a fixed time while enforcing a hard size limit."""

    def __init__(self, ttl_seconds, max_entries, clock=monotonic):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl_seconds = float(ttl_seconds)
        self._max_entries = int(max_entries)
        self._clock = clock
        self._entries = OrderedDict()
        self._generation = 0
        self._guard = Lock()

    def get_with_generation(self, key):
        """Return (copied value or None, generation token) atomically."""
        now = self._clock()
        with self._guard:
            self._purge_expired(now)
            entry = self._entries.get(key)
            if entry is None:
                return None, self._generation
            _, value = entry
            self._entries.move_to_end(key)
            return deepcopy(value), self._generation

    def get(self, key):
        value, _ = self.get_with_generation(key)
        return value

    def set_if_generation(self, key, value, generation):
        """Avoid repopulating stale data if invalidation happened mid-query."""
        now = self._clock()
        with self._guard:
            if generation != self._generation:
                return False
            self._purge_expired(now)
            self._entries[key] = (now + self._ttl_seconds, deepcopy(value))
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
            return True

    def invalidate(self, key):
        with self._guard:
            self._entries.pop(key, None)
            # A global token avoids an unbounded per-student generation map.
            self._generation += 1

    def size(self):
        now = self._clock()
        with self._guard:
            self._purge_expired(now)
            return len(self._entries)

    def _purge_expired(self, now):
        expired = [
            key
            for key, (expires_at, _) in self._entries.items()
            if expires_at <= now
        ]
        for key in expired:
            self._entries.pop(key, None)

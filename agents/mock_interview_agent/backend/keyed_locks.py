"""Reference-counted keyed locks for serializing duplicate operations."""

from contextlib import contextmanager
from threading import Lock


class _LockEntry:
    def __init__(self):
        self.lock = Lock()
        self.users = 0


class KeyedLockPool:
    """Keep one lock per active key and evict it after its final user leaves."""

    def __init__(self):
        self._entries = {}
        self._guard = Lock()

    @contextmanager
    def acquire(self, key):
        # Increment before waiting so an owner cannot evict an entry that still
        # has queued users. Different keys receive independent lock objects.
        with self._guard:
            entry = self._entries.setdefault(key, _LockEntry())
            entry.users += 1

        entry.lock.acquire()
        try:
            yield
        finally:
            entry.lock.release()
            with self._guard:
                entry.users -= 1
                if entry.users == 0 and self._entries.get(key) is entry:
                    del self._entries[key]

    def active_key_count(self):
        """Expose a safe diagnostic count without leaking the underlying map."""
        with self._guard:
            return len(self._entries)

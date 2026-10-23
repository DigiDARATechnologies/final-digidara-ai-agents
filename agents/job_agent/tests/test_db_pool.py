"""Under load every pooled connection can be busy for a moment: a request
waits for one instead of failing at once with "pool exhausted"."""
from unittest.mock import MagicMock, patch

import pytest

from job_agent import db


def test_a_full_pool_waits_for_a_free_connection():
    connection = object()
    pool = MagicMock()
    pool.get_connection.side_effect = [db.PoolError("pool exhausted"), connection]
    with patch.object(db, "_pool", pool), patch.object(db.time, "sleep"):
        assert db.get_db() is connection


def test_a_pool_that_stays_full_still_fails_after_the_wait():
    pool = MagicMock()
    pool.get_connection.side_effect = db.PoolError("pool exhausted")
    with patch.object(db, "_pool", pool), patch.object(db.time, "sleep"), patch.object(db, "POOL_WAIT_SECONDS", 0):
        with pytest.raises(db.PoolError):
            db.get_db()


def test_pool_size_default_and_cap(monkeypatch):
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    assert db._pool_size() == db.DEFAULT_POOL_SIZE == 8
    monkeypatch.setenv("DB_POOL_SIZE", "500")
    assert db._pool_size() == db.MAX_POOL_SIZE <= 32

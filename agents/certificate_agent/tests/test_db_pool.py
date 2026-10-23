"""Under load all pooled connections can be busy for a moment: a request waits
for one instead of failing at once with "pool exhausted"."""
from unittest.mock import MagicMock, patch

import pytest

from cert_app.db import database as db


def test_a_full_pool_waits_for_a_free_connection():
    connection = object()
    pool = MagicMock()
    pool.get_connection.side_effect = [db.PoolError("pool exhausted"), db.PoolError("pool exhausted"), connection]
    with patch.object(db, "_pool", pool), patch.object(db.time, "sleep"):
        assert db.get_connection() is connection


def test_a_pool_that_stays_full_still_fails_after_the_wait():
    pool = MagicMock()
    pool.get_connection.side_effect = db.PoolError("pool exhausted")
    with patch.object(db, "_pool", pool), patch.object(db.time, "sleep"), patch.object(db, "POOL_WAIT_SECONDS", 0):
        with pytest.raises(db.PoolError):
            db.get_connection()


def test_the_pool_is_created_once_and_sized_for_the_request_threads():
    with patch.object(db, "_pool", None), patch.object(db, "_new_pool", return_value=MagicMock()) as new_pool:
        assert db.get_pool() is db.get_pool()
    assert new_pool.call_count == 1
    assert 16 <= db.POOL_SIZE <= 32

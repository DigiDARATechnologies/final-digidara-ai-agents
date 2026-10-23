"""A transaction MySQL kills as a deadlock victim is simply run again."""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from backend.app.utils import database_errors


class DriverError(Exception):
    pass


def mysql(errno):
    return OperationalError("INSERT ...", {}, DriverError(errno, "message"))


@pytest.fixture(autouse=True)
def session():
    fake = MagicMock()
    with patch("backend.app.extensions.db", MagicMock(session=fake)):
        yield fake


def test_a_deadlock_victim_is_retried(session):
    outcomes = [mysql(1213), "done"]

    def work():
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    assert database_errors.retry_on_deadlock(work, sleep=lambda _s: None) == "done"
    assert session.rollback.call_count == 1


def test_other_database_errors_are_not_retried():
    calls = []

    def work():
        calls.append(1)
        raise mysql(1054)

    with pytest.raises(OperationalError):
        database_errors.retry_on_deadlock(work, sleep=lambda _s: None)
    assert len(calls) == 1


def test_a_persistent_deadlock_is_raised_after_three_attempts():
    calls = []

    def work():
        calls.append(1)
        raise mysql(1213)

    with pytest.raises(OperationalError):
        database_errors.retry_on_deadlock(work, sleep=lambda _s: None)
    assert len(calls) == 3

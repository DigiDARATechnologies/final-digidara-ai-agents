import pytest

from job_agent import db as db_module


class FakeCursor:
    def __init__(self, lock_result=(1,), fail_on_schema=False):
        self.calls = []
        self.results = [lock_result, (1,)]
        self.fail_on_schema = fail_on_schema
        self.closed = False

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        if self.fail_on_schema and statement.lstrip().startswith("CREATE TABLE"):
            raise RuntimeError("schema failure")

    def fetchone(self):
        return self.results.pop(0)

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.commits = 0
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def install_fake_connection(monkeypatch, *, lock_result=(1,), fail_on_schema=False):
    cursor = FakeCursor(lock_result=lock_result, fail_on_schema=fail_on_schema)
    connection = FakeConnection(cursor)
    monkeypatch.setattr(db_module, "get_db", lambda: connection)
    return connection, cursor


def test_schema_initialization_uses_and_releases_advisory_lock(monkeypatch):
    connection, cursor = install_fake_connection(monkeypatch)

    db_module.init_job_tables()

    assert cursor.calls[0] == (
        "SELECT GET_LOCK(%s, %s)",
        (db_module._SCHEMA_LOCK_NAME, db_module._SCHEMA_LOCK_TIMEOUT_SECONDS),
    )
    assert cursor.calls[-1] == (
        "SELECT RELEASE_LOCK(%s)",
        (db_module._SCHEMA_LOCK_NAME,),
    )
    assert connection.commits == 1
    assert cursor.closed
    assert connection.closed


def test_schema_initialization_releases_lock_after_failure(monkeypatch):
    connection, cursor = install_fake_connection(monkeypatch, fail_on_schema=True)

    with pytest.raises(RuntimeError, match="schema failure"):
        db_module.init_job_tables()

    assert cursor.calls[-1] == (
        "SELECT RELEASE_LOCK(%s)",
        (db_module._SCHEMA_LOCK_NAME,),
    )
    assert connection.commits == 0
    assert cursor.closed
    assert connection.closed


def test_schema_initialization_fails_when_lock_times_out(monkeypatch):
    connection, cursor = install_fake_connection(monkeypatch, lock_result=(0,))

    with pytest.raises(RuntimeError, match="Timed out"):
        db_module.init_job_tables()

    assert len(cursor.calls) == 1
    assert connection.commits == 0
    assert cursor.closed
    assert connection.closed

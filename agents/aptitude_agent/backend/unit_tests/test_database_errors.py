"""Database failures give an accurate response and a log line that says why."""
import logging
from unittest.mock import MagicMock

import pymysql
import pytest
from flask import Flask
from sqlalchemy.exc import OperationalError

from backend.app.utils.database_errors import classify, mysql_error, register_database_error_handler


def failure(errno, message):
    return OperationalError("SELECT secret FROM students WHERE email = %s", ("learner@example.com",), pymysql.err.OperationalError(errno, message))


@pytest.fixture
def client_and_rollback():
    app = Flask(__name__)
    rollback = MagicMock()
    register_database_error_handler(app, rollback)
    raised = {}

    @app.get("/boom")
    def boom():
        raise raised["error"]

    with app.test_client() as client:
        yield client, raised, rollback


@pytest.mark.parametrize("errno,code", [
    (1040, "database_busy"), (1205, "database_busy"), (1213, "database_busy"), (2003, "database_busy"), (2006, "database_busy"), (2013, "database_busy"),
    (1054, "database_schema_mismatch"), (1146, "database_schema_mismatch"),
    (1045, "database_unavailable"), (1049, "database_unavailable"), (9999, "database_unavailable"),
])
def test_each_cause_gets_its_own_code_and_a_503(client_and_rollback, errno, code):
    client, raised, rollback = client_and_rollback
    raised["error"] = failure(errno, "boom")
    response = client.get("/boom")
    assert response.status_code == 503
    assert response.get_json()["code"] == code
    rollback.assert_called_once()


def test_a_busy_database_tells_the_client_when_to_retry(client_and_rollback):
    client, raised, _ = client_and_rollback
    raised["error"] = failure(1040, "Too many connections")
    response = client.get("/boom")
    assert response.headers["Retry-After"] == "5"
    assert "busy" in response.get_json()["error"].lower()


def test_a_schema_mismatch_is_not_blamed_on_the_database_password(client_and_rollback):
    client, raised, _ = client_and_rollback
    raised["error"] = failure(1054, "Unknown column 'students.data_consent_at' in 'field list'")
    message = client.get("/boom").get_json()["error"]
    assert "grants" not in message and "DATABASE_URL" not in message


def test_the_log_names_the_mysql_error_but_never_the_sql_or_its_parameters(client_and_rollback, caplog):
    client, raised, _ = client_and_rollback
    raised["error"] = failure(1040, "Too many connections")
    with caplog.at_level(logging.ERROR):
        client.get("/boom")
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "errno=1040" in logged and "Too many connections" in logged
    assert "learner@example.com" not in logged and "SELECT secret" not in logged


def test_the_response_never_contains_the_sql_or_the_mysql_message(client_and_rollback):
    client, raised, _ = client_and_rollback
    raised["error"] = failure(1054, "Unknown column 'students.password_hash'")
    body = client.get("/boom").get_data(as_text=True)
    assert "SELECT" not in body and "password_hash" not in body and "learner@example.com" not in body


def test_errors_without_a_mysql_number_still_fall_back_safely():
    assert mysql_error(OperationalError("x", (), Exception("plain"))) == (None, "")
    assert classify(None)[1] == "database_unavailable"

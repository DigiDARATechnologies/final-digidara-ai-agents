"""Turn database failures into an accurate response and a log line that says why.

PyMySQL raises OperationalError for very different problems: a wrong password,
a saturated server ("too many connections"), a dropped connection, and even a
column the code expects but the schema does not have yet. They all used to
produce one message ("check DATABASE_URL and MySQL grants") and one log line
with only the exception class, so an operator could not tell them apart.

This logs the MySQL error number and message (never the SQL statement or its
parameters, which can contain learner data) and picks a message that matches
the cause.
"""
from flask import jsonify, request

# The server is reachable but overloaded or the connection dropped: a retry helps.
BUSY_ERRNOS = {1040, 1205, 1213, 2002, 2003, 2006, 2013}
# The code and the database schema disagree: usually a migration has not run yet.
SCHEMA_ERRNOS = {1054, 1146, 1364}

BUSY = ("The database is busy right now. Please try again in a moment.", "database_busy")
SCHEMA = ("The service is being updated. Please try again in a few minutes.", "database_schema_mismatch")
UNAVAILABLE = ("MySQL is unavailable or rejected the configured account. Check DATABASE_URL and MySQL grants.", "database_unavailable")


def mysql_error(error) -> tuple[int | None, str]:
    """The (errno, message) of the driver error wrapped by a SQLAlchemy exception."""
    original = getattr(error, "orig", error)
    args = getattr(original, "args", ())
    errno = args[0] if args and isinstance(args[0], int) else None
    message = str(args[1]) if len(args) > 1 else ""
    return errno, message[:200]


def classify(errno: int | None) -> tuple[str, str]:
    if errno in BUSY_ERRNOS:
        return BUSY
    if errno in SCHEMA_ERRNOS:
        return SCHEMA
    return UNAVAILABLE


def register_database_error_handler(app, rollback):
    from sqlalchemy.exc import OperationalError

    @app.errorhandler(OperationalError)
    def database_unavailable(error):
        rollback()
        errno, detail = mysql_error(error)
        request_id = request.environ.get("aptitude.request_id")
        app.logger.error(
            "Database error errno=%s type=%s detail=%s request_id=%s",
            errno, type(getattr(error, "orig", error)).__name__, detail, request_id,
        )
        message, code = classify(errno)
        response = jsonify(error=message, code=code, request_id=request_id)
        if code == BUSY[1]:
            response.headers["Retry-After"] = "5"
        return response, 503

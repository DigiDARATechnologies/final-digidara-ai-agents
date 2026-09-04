from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError


def describe_database_error(exc):
    detail = str(getattr(exc, "orig", exc))
    lowered = detail.lower()

    if isinstance(exc, OperationalError):
        if "access denied" in lowered:
            return "database authentication failed", detail
        if "unknown database" in lowered:
            return "database does not exist", detail
        if "can't connect" in lowered or "connection refused" in lowered:
            return "database connection failed", detail
        return "database operation failed", detail

    if isinstance(exc, IntegrityError):
        if "foreign key constraint" in lowered or "constraint fails" in lowered:
            return "referenced record does not exist", detail
        if "duplicate" in lowered:
            return "duplicate record", detail
        if "cannot be null" in lowered or "not null" in lowered:
            return "required database field is missing", detail
        return "database integrity error", detail

    return "database error", detail


def database_error_payload(exc):
    error, detail = describe_database_error(exc)
    return {
        "success": False,
        "message": error,
        "error": error,
        "detail": detail,
    }


def database_error_response(exc, status_code=500):
    from flask import jsonify

    return jsonify(database_error_payload(exc)), status_code

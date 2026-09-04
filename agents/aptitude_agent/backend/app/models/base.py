from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


def as_utc(value):
    """Normalize MySQL DATETIME values before comparing them in Python.

    MySQL does not preserve timezone metadata for DATETIME columns, so even
    columns declared with ``timezone=True`` can be returned by PyMySQL as
    offset-naive values. Stored application timestamps are UTC.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_isoformat(value):
    """Serialize database datetimes as an explicit UTC ISO-8601 timestamp."""
    if value is None:
        return None
    return as_utc(value).isoformat().replace("+00:00","Z")

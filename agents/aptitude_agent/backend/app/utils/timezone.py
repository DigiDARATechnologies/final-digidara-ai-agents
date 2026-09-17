"""Timezone validation and formatting helpers for learner-facing dates."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .security import clean_text


def valid_timezone(value):
    """Return a valid IANA timezone name, or None for missing/invalid input."""
    name = clean_text(value, 80)
    if not name:
        return None
    if name == "Asia/Calcutta":
        name = "Asia/Kolkata"
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return name


def format_local_datetime(value, timezone_name=None):
    """Format a UTC database datetime in the requested timezone, safely."""
    if value is None:
        return ""
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    name = valid_timezone(timezone_name) or "UTC"
    try:
        local = value.astimezone(ZoneInfo(name))
    except (ZoneInfoNotFoundError, ValueError):
        local = value
    return local.strftime("%d %b %Y, %I:%M %p %Z")

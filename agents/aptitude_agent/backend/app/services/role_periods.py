"""Role periods: when the learner's current target role was their goal.

The orchestrator's readiness service sends `periods` with get_student_summary
after the learner has changed their target role: a list of
{"start": ISO or null, "end": ISO or null} in naive UTC, a null bound being
open. Only activity inside a period counts towards the current role, so a new
role starts from zero and switching back brings its progress back. Without
periods every activity counts.
"""
from datetime import datetime, timezone


def _moment(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return moment.astimezone(timezone.utc).replace(tzinfo=None) if moment.tzinfo else moment


def clean_periods(value):
    """The periods from a payload, validated; None when every activity counts."""
    if not isinstance(value, list) or not value:
        return None
    periods = []
    for item in value[:50]:
        if isinstance(item, dict):
            periods.append((_moment(item.get("start")), _moment(item.get("end"))))
    return periods or None


def in_periods(when, periods):
    """True when `when` is inside one of the periods (or there are none)."""
    if not periods:
        return True
    moment = _moment(when)
    if moment is None:
        return False
    return any((start is None or moment >= start) and (end is None or moment < end) for start, end in periods)

"""Keeps job collection inside the providers' free plans, whoever triggers it.

Every real Adzuna / JSearch HTTP call is recorded here *before* it is made,
and refused once a free-plan window is full -- the daily automation, an
admin's "Queue run" and JSearch's fallback request all count. Windows are
rolling (a month is the last 31 days), so the cap holds whatever day the
provider's own counter resets on.

Free plans (checked 1 Oct 2026):
- Adzuna: 25 calls a minute, 250 a day, 1,000 a week, 2,500 a month
  (developer.adzuna.com/docs/terms_of_service).
- RapidAPI JSearch Basic: 200 requests a month, 1,000 an hour.
- PR Labs Jobs API: credit-based; capped here at JOBS_PRLABS_DAILY_QUERIES
  a day and JOBS_PRLABS_MONTHLY_CALLS a month (set them to the plan bought).
"""
from __future__ import annotations

import logging
import time

from .config import JOBS_PRLABS_DAILY_QUERIES, JOBS_PRLABS_MONTHLY_CALLS
from .db import get_db

logger = logging.getLogger(__name__)

# provider -> [(window name, seconds, calls allowed)]
FREE_PLAN_LIMITS = {
    "adzuna": [("minute", 60, 25), ("day", 86400, 250), ("week", 7 * 86400, 1000), ("month", 31 * 86400, 2500)],
    "jsearch": [("hour", 3600, 1000), ("month", 31 * 86400, 200)],
    "prlabs": [("day", 86400, JOBS_PRLABS_DAILY_QUERIES), ("month", 31 * 86400, JOBS_PRLABS_MONTHLY_CALLS)],
}
# Windows this short are waited out rather than refused.
WAIT_WINDOW_SECONDS = 3600
MAX_WAIT_SECONDS = 75


class FreePlanLimitReached(Exception):
    """A provider's free-plan window is full; no API call was made."""

    # Read by service.process_run: the source shows this category and stays
    # retryable (it runs again once the window frees up).
    category = "free_plan_limit"
    permanent = False


def _used(cursor, provider, seconds):
    cursor.execute(
        "SELECT COUNT(*) FROM provider_api_calls WHERE provider=%s AND called_at > NOW() - INTERVAL %s SECOND",
        (provider, seconds),
    )
    row = cursor.fetchone()
    return int(row[0] if row else 0)


def reserve_call(provider, sleep=time.sleep):
    """Record one API call for `provider`, or raise FreePlanLimitReached.

    A full per-minute window is waited out (up to MAX_WAIT_SECONDS); a full
    day / week / month window refuses the call outright."""
    limits = FREE_PLAN_LIMITS.get(provider)
    if not limits:
        return
    waited = 0
    db = get_db()
    cursor = db.cursor()
    try:
        while True:
            blocked = None
            for name, seconds, allowed in limits:
                if _used(cursor, provider, seconds) >= allowed:
                    blocked = (name, seconds, allowed)
                    break
            if blocked is None:
                cursor.execute("INSERT INTO provider_api_calls (provider) VALUES (%s)", (provider,))
                db.commit()
                return
            name, seconds, allowed = blocked
            if seconds > WAIT_WINDOW_SECONDS or waited >= MAX_WAIT_SECONDS:
                raise FreePlanLimitReached(
                    f"Free plan limit reached for {provider}: {allowed} calls per {name}. "
                    "No API call was made; it will run again once the window frees up."
                )
            sleep(5)
            waited += 5
    finally:
        cursor.close()
        db.close()


def remaining_calls(provider):
    """Calls still allowed today by the tightest day / week / month window."""
    limits = [limit for limit in FREE_PLAN_LIMITS.get(provider, []) if limit[1] > WAIT_WINDOW_SECONDS]
    if not limits:
        return 0
    db = get_db()
    cursor = db.cursor()
    try:
        return max(0, min(allowed - _used(cursor, provider, seconds) for _, seconds, allowed in limits))
    finally:
        cursor.close()
        db.close()


def usage_summary():
    """{provider: [{window, used, limit}]} for the admin page."""
    db = get_db()
    cursor = db.cursor()
    try:
        return {
            provider: [{"window": name, "used": _used(cursor, provider, seconds), "limit": allowed}
                       for name, seconds, allowed in limits]
            for provider, limits in FREE_PLAN_LIMITS.items()
        }
    finally:
        cursor.close()
        db.close()

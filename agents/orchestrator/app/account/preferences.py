"""Settings that follow the account to every device (Settings > General,
Notifications, Usage, Billing and pinned agents). Appearance and
accessibility stay on the device, like before.

Every value is checked here: unknown keys are dropped and bad values fall
back to the default, so the stored document is always the full, valid shape.
"""
from __future__ import annotations

import copy
import re
from datetime import datetime

from app import db
from app.models import UserPreference

DATE_FORMATS = ("auto", "dmy", "mdy", "ymd")
WARN_PERCENTS = (0, 50, 75, 80, 90)
MAX_PINNED = 30
_AGENT_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_TIME_ZONE = re.compile(r"^[A-Za-z_]+(?:/[A-Za-z0-9_+-]+){0,2}$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")

DEFAULTS: dict = {
    "notifications": {
        # Master switch for every email below.
        "email": True,
        # The bell in the top bar.
        "in_app": True,
        "assessment_reminders": True,
        "low_coin_warning": True,
        "weekly_progress": False,
    },
    "general": {
        # A LIVE_AGENTS id opened after signing in; "" opens Home.
        "default_agent": "",
        # An IANA zone such as "Asia/Kolkata"; "" follows the device.
        "time_zone": "",
        "date_format": "auto",
    },
    # Warn once a month when this share of the month's coins is used; 0 is off.
    "usage": {"warn_percent": 80},
    "billing": {"billing_email": "", "renewal_reminder": True},
    "pinned_agents": [],
}


def _clean(raw: dict | None) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    out = copy.deepcopy(DEFAULTS)

    notifications = raw.get("notifications") if isinstance(raw.get("notifications"), dict) else {}
    for key in out["notifications"]:
        if isinstance(notifications.get(key), bool):
            out["notifications"][key] = notifications[key]

    general = raw.get("general") if isinstance(raw.get("general"), dict) else {}
    agent = general.get("default_agent")
    if isinstance(agent, str) and (agent == "" or _AGENT_ID.match(agent)):
        out["general"]["default_agent"] = agent
    zone = general.get("time_zone")
    if isinstance(zone, str) and (zone == "" or (len(zone) <= 64 and _TIME_ZONE.match(zone))):
        out["general"]["time_zone"] = zone
    if general.get("date_format") in DATE_FORMATS:
        out["general"]["date_format"] = general["date_format"]

    usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
    if usage.get("warn_percent") in WARN_PERCENTS and not isinstance(usage.get("warn_percent"), bool):
        out["usage"]["warn_percent"] = int(usage["warn_percent"])

    billing = raw.get("billing") if isinstance(raw.get("billing"), dict) else {}
    email = billing.get("billing_email")
    if isinstance(email, str):
        email = email.strip().lower()
        if email == "" or (len(email) <= 255 and _EMAIL.match(email)):
            out["billing"]["billing_email"] = email
    if isinstance(billing.get("renewal_reminder"), bool):
        out["billing"]["renewal_reminder"] = billing["renewal_reminder"]

    pinned = raw.get("pinned_agents")
    if isinstance(pinned, list):
        seen: list[str] = []
        for item in pinned:
            if isinstance(item, str) and _AGENT_ID.match(item) and item not in seen:
                seen.append(item)
        out["pinned_agents"] = seen[:MAX_PINNED]
    return out


def _merge(base: dict, patch: dict) -> dict:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def get(user_id: str) -> dict:
    session = db.get_session()
    try:
        row = session.get(UserPreference, user_id)
        return _clean(row.prefs if row else None)
    finally:
        session.close()


def update(user_id: str, patch: dict) -> dict:
    """Merge `patch` (any part of the document) into the saved choices."""
    session = db.get_session()
    try:
        row = session.get(UserPreference, user_id, with_for_update=True)
        current = _clean(row.prefs if row else None)
        cleaned = _clean(_merge(current, patch if isinstance(patch, dict) else {}))
        if row is None:
            session.add(UserPreference(user_id=user_id, prefs=cleaned, sent={}))
        else:
            row.prefs = cleaned
            row.updated_at = datetime.utcnow()
        session.commit()
        return cleaned
    finally:
        session.close()


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(UserPreference).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()

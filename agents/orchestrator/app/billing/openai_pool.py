"""Does the OpenAI account hold enough credit for the tokens SkillDARA has
given its users? For the admin page only; learners never see any of this.

Every account holds a token balance (free tokens at signup, more with each
plan), and every one of those tokens is paid for out of the one OpenAI account.
OpenAI has no API that returns the prepaid credit left, so an admin types the
balance from https://platform.openai.com/settings/organization/billing after
each top-up (OpenAICreditEntry). What was spent since then is taken off:

* exactly, from OpenAI's Costs API, when OPENAI_ADMIN_KEY (an sk-admin-... key,
  created under Organization > Admin keys) is set;
* otherwise estimated from the tokens agents reported using
  (token_usage_events) at the gpt-4o-mini price in billing/plans.py. That
  includes the agents that run on Groq, so it errs towards less credit left.

What is left is turned into tokens at the same price and compared with the sum
of every user's balance. When it does not cover them, support is emailed
(ISSUE_EMAIL, support@digidaratechnologies.com): the moment it falls short, and
again every REMIND_EVERY while it stays short. A new user joining runs this
check straight away; the ten-minute monitoring cycle runs it too.
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import event, func
from sqlalchemy.orm import Session

from app import db
from app.billing.plans import (
    OPENAI_INPUT_SHARE, OPENAI_INPUT_USD_PER_MILLION, OPENAI_OUTPUT_USD_PER_MILLION, free_signup_tokens,
)
from app.models import MonitorState, OpenAICreditEntry, TokenUsageEvent, User

logger = logging.getLogger(__name__)

COSTS_URL = "https://api.openai.com/v1/organization/costs"
COSTS_CACHE_SECONDS = 600
REMIND_EVERY = timedelta(hours=12)
ENOUGH, SHORT, NOT_SET = "enough", "short", "not_set"

_STATE_STATUS = "openai_pool_status"
_STATE_ALERTED = "openai_pool_alerted_at"
_STATE_NEW_USERS = "openai_pool_new_users_short"

_costs_cache: dict = {}
_costs_lock = threading.Lock()


def usd_per_million_tokens() -> float:
    return OPENAI_INPUT_SHARE * OPENAI_INPUT_USD_PER_MILLION + (1 - OPENAI_INPUT_SHARE) * OPENAI_OUTPUT_USD_PER_MILLION


def tokens_for_usd(usd: float) -> int:
    return int(max(0.0, usd) / usd_per_million_tokens() * 1_000_000)


def support_email() -> str:
    return os.environ.get("ISSUE_EMAIL", "support@digidaratechnologies.com").strip()


ADMIN_KEY_SECRET = "openai_admin_key"


def _admin_key() -> str:
    """The key an admin saved on the admin page wins; OPENAI_ADMIN_KEY in the
    server's .env is the fallback."""
    from app import secret_store

    return (secret_store.get(ADMIN_KEY_SECRET) or os.environ.get("OPENAI_ADMIN_KEY", "")).strip()


def admin_key_status() -> dict:
    """Whether an admin key is set and where it came from; never the key itself."""
    from app import secret_store

    saved = secret_store.info(ADMIN_KEY_SECRET)
    if saved and secret_store.get(ADMIN_KEY_SECRET):
        return {"set": True, "source": "page", **saved}
    env = os.environ.get("OPENAI_ADMIN_KEY", "").strip()
    if env:
        return {"set": True, "source": "env", "hint": secret_store.hint_for(env), "updated_by": "", "updated_at": None}
    return {"set": False, "source": None, "hint": "", "updated_by": "", "updated_at": None}


def check_admin_key(key: str) -> str:
    """Asks OpenAI whether `key` can read the organization's costs:
    "ok", "rejected" (OpenAI refused it) or "unavailable" (no answer)."""
    start = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(COSTS_URL, params={"start_time": start, "bucket_width": "1d", "limit": 1},
                                  headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        return "unavailable"
    if response.status_code in (401, 403):
        return "rejected"
    return "ok" if response.is_success else "unavailable"


def clear_caches() -> None:
    with _costs_lock:
        _costs_cache.clear()
        _live_cache.clear()


def _openai_costs_since(since: datetime) -> float | None:
    """USD the organization spent from the day of `since` (UTC), from the Costs
    API; None when there is no admin key or OpenAI did not answer. Whole days:
    costs come in daily buckets, so the morning before an entry counts too and
    the figure leans to less credit left, never more."""
    key = _admin_key()
    if not key:
        return None
    start = int(datetime(since.year, since.month, since.day, tzinfo=timezone.utc).timestamp())
    with _costs_lock:
        cached = _costs_cache.get(start)
        if cached and time.monotonic() - cached[1] < COSTS_CACHE_SECONDS:
            return cached[0]
    total, page = 0.0, None
    try:
        with httpx.Client(timeout=10) as client:
            for _ in range(20):
                params = {"start_time": start, "bucket_width": "1d", "limit": 180}
                if page:
                    params["page"] = page
                response = client.get(COSTS_URL, params=params, headers={"Authorization": f"Bearer {key}"})
                response.raise_for_status()
                body = response.json()
                for bucket in body.get("data", []):
                    for result in bucket.get("results", []):
                        total += float((result.get("amount") or {}).get("value") or 0)
                page = body.get("next_page")
                if not body.get("has_more") or not page:
                    break
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("OpenAI costs could not be read: %s", type(exc).__name__)
        return None
    with _costs_lock:
        _costs_cache[start] = (total, time.monotonic())
    return total


USAGE_URL = "https://api.openai.com/v1/organization/usage/completions"
LIVE_DAYS = 30
_live_cache: dict = {}


def _pages(client: httpx.Client, url: str, params: dict, key: str) -> list[dict]:
    """Every bucket of a paged organization endpoint (Costs or Usage)."""
    buckets, page = [], None
    for _ in range(20):
        response = client.get(url, params={**params, **({"page": page} if page else {})},
                              headers={"Authorization": f"Bearer {key}"})
        response.raise_for_status()
        body = response.json()
        buckets += body.get("data", [])
        page = body.get("next_page")
        if not body.get("has_more") or not page:
            break
    return buckets


def live_from_openai(now: datetime | None = None, *, refresh: bool = False) -> dict:
    """What the OpenAI platform itself reports for the last LIVE_DAYS days:
    spending (Costs API) and tokens (Usage API), per day and per model. Needs
    OPENAI_ADMIN_KEY; read at most every COSTS_CACHE_SECONDS. OpenAI has no API
    for the prepaid credit balance, so that is still entered by an admin."""
    key = _admin_key()
    if not key:
        return {"connected": False, "error": "no_key"}
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start = today - timedelta(days=LIVE_DAYS - 1)
    with _costs_lock:
        cached = _live_cache.get("live")
        if not refresh and cached and time.monotonic() - cached[1] < COSTS_CACHE_SECONDS:
            return cached[0]
    window = {"start_time": int(start.timestamp()), "bucket_width": "1d"}
    try:
        with httpx.Client(timeout=15) as client:
            costs = _pages(client, COSTS_URL, {**window, "limit": LIVE_DAYS, "group_by": "line_item"}, key)
            usage = _pages(client, USAGE_URL, {**window, "limit": LIVE_DAYS, "group_by": "model"}, key)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        logger.warning("OpenAI usage could not be read: HTTP %s", code)
        return {"connected": False, "error": "rejected" if code in (401, 403) else "unavailable"}
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("OpenAI usage could not be read: %s", type(exc).__name__)
        return {"connected": False, "error": "unavailable"}

    def day_of(bucket: dict) -> str:
        return datetime.fromtimestamp(int(bucket.get("start_time") or 0), timezone.utc).date().isoformat()

    days = {(start + timedelta(days=i)).date().isoformat(): {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "requests": 0}
            for i in range(LIVE_DAYS)}
    line_items: dict[str, float] = {}
    for bucket in costs:
        day = days.setdefault(day_of(bucket), {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "requests": 0})
        for result in bucket.get("results", []):
            value = float((result.get("amount") or {}).get("value") or 0)
            day["usd"] += value
            item = result.get("line_item") or "other"
            line_items[item] = line_items.get(item, 0.0) + value
    models: dict[str, dict] = {}
    for bucket in usage:
        day = days.setdefault(day_of(bucket), {"usd": 0.0, "input_tokens": 0, "output_tokens": 0, "requests": 0})
        for result in bucket.get("results", []):
            inp, out, req = (int(result.get(k) or 0) for k in ("input_tokens", "output_tokens", "num_model_requests"))
            day["input_tokens"] += inp
            day["output_tokens"] += out
            day["requests"] += req
            row = models.setdefault(result.get("model") or "other", {"input_tokens": 0, "output_tokens": 0, "requests": 0})
            row["input_tokens"] += inp
            row["output_tokens"] += out
            row["requests"] += req
    month = today.date().isoformat()[:7]
    daily = [{"date": d, **{k: (round(v, 4) if k == "usd" else v) for k, v in vals.items()}} for d, vals in sorted(days.items())]
    result = {
        "connected": True, "error": None, "fetched_at": datetime.utcnow().replace(microsecond=0).isoformat(), "days": LIVE_DAYS,
        "today_usd": round(days.get(today.date().isoformat(), {}).get("usd", 0.0), 4),
        "month_usd": round(sum(v["usd"] for d, v in days.items() if d.startswith(month)), 4),
        "period_usd": round(sum(v["usd"] for v in days.values()), 4),
        "period_tokens": sum(v["input_tokens"] + v["output_tokens"] for v in days.values()),
        "period_requests": sum(v["requests"] for v in days.values()),
        "daily": daily[::-1],   # newest first
        "by_model": sorted(({"model": m, **v} for m, v in models.items()),
                           key=lambda r: r["input_tokens"] + r["output_tokens"], reverse=True),
        "by_line_item": sorted(({"line_item": k, "usd": round(v, 4)} for k, v in line_items.items()), key=lambda r: -r["usd"]),
    }
    with _costs_lock:
        _live_cache["live"] = (result, time.monotonic())
    return result


def _estimated_spend_since(session, since: datetime) -> tuple[float, int]:
    tokens = int(session.query(func.sum(TokenUsageEvent.tokens)).filter(TokenUsageEvent.created_at >= since).scalar() or 0)
    return tokens / 1_000_000 * usd_per_million_tokens(), tokens


def latest_entry(session) -> OpenAICreditEntry | None:
    return session.query(OpenAICreditEntry).order_by(OpenAICreditEntry.created_at.desc()).first()


def allocated_tokens(session) -> int:
    """Every token users still hold. A balance below zero (the last charge
    overshot) owes nothing more, so it counts as zero."""
    return int(session.query(func.sum(User.token_balance)).filter(User.token_balance > 0).scalar() or 0)


def summary(session) -> dict:
    """The figures the admin page and the alert email show."""
    allocated = allocated_tokens(session)
    users_holding = session.query(func.count(User.id)).filter(User.token_balance > 0).scalar() or 0
    per_new_user = free_signup_tokens()
    entry = latest_entry(session)
    base = {
        "allocated_tokens": allocated, "users_holding_tokens": int(users_holding), "users_total": session.query(func.count(User.id)).scalar() or 0,
        "new_user_tokens": per_new_user, "usd_per_million_tokens": round(usd_per_million_tokens(), 4),
        "support_email": support_email(), "exact_costs": bool(_admin_key()),
    }
    if entry is None:
        return {**base, "status": NOT_SET, "balance_entry": None, "spent_usd": 0.0, "spend_source": None,
                "remaining_usd": None, "available_tokens": None, "spare_tokens": None, "shortfall_tokens": None,
                "new_users_room": None}
    spent = _openai_costs_since(entry.created_at)
    source = "openai"
    if spent is None:
        spent, _ = _estimated_spend_since(session, entry.created_at)
        source = "estimate"
    remaining = max(0.0, entry.balance_usd - spent)
    available = tokens_for_usd(remaining)
    spare = available - allocated
    return {
        **base,
        "status": ENOUGH if spare >= 0 else SHORT,
        "balance_entry": {"id": entry.id, "balance_usd": round(entry.balance_usd, 2), "note": entry.note,
                          "created_at": entry.created_at.isoformat()},
        "spent_usd": round(spent, 4), "spend_source": source,
        "remaining_usd": round(remaining, 4), "available_tokens": available,
        "spare_tokens": max(0, spare), "shortfall_tokens": max(0, -spare),
        "new_users_room": max(0, spare) // per_new_user if per_new_user > 0 else None,
    }


def _read(session, key: str) -> str | None:
    row = session.get(MonitorState, key)
    return row.value if row else None


def _write(session, key: str, value: str) -> None:
    row = session.get(MonitorState, key)
    if row:
        row.value = value
    else:
        session.add(MonitorState(key=key, value=value))


def alert_state(session) -> dict:
    return {"last_alert_at": _read(session, _STATE_ALERTED), "new_users_while_short": int(_read(session, _STATE_NEW_USERS) or 0)}


def _email_body(figures: dict, new_users: int) -> str:
    entry = figures["balance_entry"]
    spent_how = "from OpenAI's Costs API" if figures["spend_source"] == "openai" else "estimated from the tokens agents reported"
    lines = [
        "The OpenAI account does not hold enough credit for the tokens SkillDARA has given its users.",
        "",
        f"OpenAI credit entered:   ${entry['balance_usd']:,.2f} on {entry['created_at'][:16].replace('T', ' ')} UTC",
        f"Spent since then:        ${figures['spent_usd']:,.2f} ({spent_how})",
        f"Credit left:             ${figures['remaining_usd']:,.2f} = {figures['available_tokens']:,} tokens",
        f"Held by users:           {figures['allocated_tokens']:,} tokens across {figures['users_holding_tokens']:,} users",
        f"Short by:                {figures['shortfall_tokens']:,} tokens "
        f"(about ${figures['shortfall_tokens'] / 1_000_000 * figures['usd_per_million_tokens']:,.2f})",
    ]
    if new_users:
        lines.append(f"New users who joined while short: {new_users} (each was given {figures['new_user_tokens']:,} tokens)")
    lines += [
        "",
        "Top up at https://platform.openai.com/settings/organization/billing, then enter the new balance",
        "on the SkillDARA admin page (Admin > OpenAI tokens).",
    ]
    return "\n".join(lines) + "\n"


def check_and_alert(*, new_user: bool = False, now: datetime | None = None) -> dict:
    """Works the figures out and emails support when they fall short: at once
    when the status turns short, then every REMIND_EVERY while it stays so.
    Returns the figures, with `"emailed"` saying whether mail went out."""
    from app.monitoring.service import _send_email

    now = (now or datetime.utcnow()).replace(microsecond=0)
    session = db.get_session()
    try:
        figures = summary(session)
        previous = _read(session, _STATE_STATUS)
        new_users = int(_read(session, _STATE_NEW_USERS) or 0)
        emailed = False
        if figures["status"] == SHORT:
            if new_user:
                new_users += 1
                _write(session, _STATE_NEW_USERS, str(new_users))
            last = _read(session, _STATE_ALERTED)
            due = previous != SHORT or not last or now - datetime.fromisoformat(last) >= REMIND_EVERY
            if due:
                subject = "[SkillDARA] OpenAI credit is not enough for users' tokens"
                if _send_email([support_email()], subject, _email_body(figures, new_users)):
                    emailed = True
                    _write(session, _STATE_ALERTED, now.isoformat())
        elif figures["status"] == ENOUGH and previous == SHORT:
            _write(session, _STATE_NEW_USERS, "0")
        _write(session, _STATE_STATUS, figures["status"])
        session.commit()
        return {**figures, "emailed": emailed}
    finally:
        session.close()


def check_on_signup_enabled() -> bool:
    return os.environ.get("OPENAI_POOL_CHECK_ON_SIGNUP", "1").strip() not in ("0", "false", "no")


def check_in_background(*, new_user: bool = False) -> None:
    def run() -> None:
        try:
            check_and_alert(new_user=new_user)
        except Exception as exc:  # noqa: BLE001 - a signup must never fail because of this check
            logger.warning("OpenAI credit check failed: %s", type(exc).__name__)
    threading.Thread(target=run, daemon=True, name="openai-pool-check").start()


# Every way an account is made (signup, Google, organizations adding learners)
# goes through a session that inserts a User; once it is committed, check.
@event.listens_for(Session, "after_flush")
def _note_new_users(session, _flush_context) -> None:
    if any(isinstance(obj, User) for obj in session.new):
        session.info["openai_pool_new_user"] = True


@event.listens_for(Session, "after_commit")
def _check_after_new_user(session) -> None:
    if session.info.pop("openai_pool_new_user", False) and check_on_signup_enabled():
        check_in_background(new_user=True)


@event.listens_for(Session, "after_rollback")
def _forget_new_user(session) -> None:
    session.info.pop("openai_pool_new_user", None)

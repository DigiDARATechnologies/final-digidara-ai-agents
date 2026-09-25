"""SaaS Token Economy & Daily Usage Manager for DigiDARA Job Agent.

Features:
- Dynamic token settings loaded from database (job_token_settings table)
  with fallback to environment variables and defaults in config.py.
- Accurate daily usage tracking in user_daily_job_usage table.
- Hybrid billing: Free daily quota (e.g. 20 jobs/day, 10 chats/day)
  followed by platform token charges (e.g. 2,000 tokens for extra jobs, 500 tokens for chat).
- Fully decoupled from Git: teammates cloning code cannot overwrite production rates.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from .config import (
    DEFAULT_FREE_DAILY_CHAT_TURNS,
    DEFAULT_FREE_DAILY_FEED_LIMIT,
    DEFAULT_TOKENS_PER_CHAT_TURN,
    DEFAULT_TOKENS_PER_EXTRA_FEED,
    JOBS_AUTOMATION_TIMEZONE,
)

logger = logging.getLogger(__name__)


def _current_usage_date() -> date:
    """Returns today's date in the configured business timezone (default: Asia/Kolkata)."""
    try:
        tz = ZoneInfo(JOBS_AUTOMATION_TIMEZONE)
        return datetime.now(tz).date()
    except Exception:
        return datetime.utcnow().date()


def get_token_settings(cursor=None) -> Dict[str, int]:
    """Retrieves live token settings from database row id=1 with fallback to config defaults."""
    defaults = {
        "free_daily_feed_limit": DEFAULT_FREE_DAILY_FEED_LIMIT,
        "free_daily_chat_turns": DEFAULT_FREE_DAILY_CHAT_TURNS,
        "tokens_per_extra_feed": DEFAULT_TOKENS_PER_EXTRA_FEED,
        "tokens_per_chat_turn": DEFAULT_TOKENS_PER_CHAT_TURN,
    }
    if cursor is None:
        return defaults

    try:
        cursor.execute(
            """SELECT free_daily_feed_limit, free_daily_chat_turns, 
                      tokens_per_extra_feed, tokens_per_chat_turn 
               FROM job_token_settings WHERE id=1"""
        )
        row = cursor.fetchone()
        if not row:
            return defaults

        if isinstance(row, dict):
            return {
                "free_daily_feed_limit": int(row.get("free_daily_feed_limit") or defaults["free_daily_feed_limit"]),
                "free_daily_chat_turns": int(row.get("free_daily_chat_turns") or defaults["free_daily_chat_turns"]),
                "tokens_per_extra_feed": int(row.get("tokens_per_extra_feed") or defaults["tokens_per_extra_feed"]),
                "tokens_per_chat_turn": int(row.get("tokens_per_chat_turn") or defaults["tokens_per_chat_turn"]),
            }
        else:
            return {
                "free_daily_feed_limit": int(row[0] or defaults["free_daily_feed_limit"]),
                "free_daily_chat_turns": int(row[1] or defaults["free_daily_chat_turns"]),
                "tokens_per_extra_feed": int(row[2] or defaults["tokens_per_extra_feed"]),
                "tokens_per_chat_turn": int(row[3] or defaults["tokens_per_chat_turn"]),
            }
    except Exception as exc:
        logger.warning("Could not read job_token_settings table, falling back to config defaults: %s", exc)
        return defaults


def update_token_settings(
    cursor,
    free_daily_feed_limit: Optional[int] = None,
    free_daily_chat_turns: Optional[int] = None,
    tokens_per_extra_feed: Optional[int] = None,
    tokens_per_chat_turn: Optional[int] = None,
) -> Dict[str, int]:
    """Updates live token settings in the database for instant runtime effect."""
    current = get_token_settings(cursor)
    new_feed = free_daily_feed_limit if free_daily_feed_limit is not None else current["free_daily_feed_limit"]
    new_chat = free_daily_chat_turns if free_daily_chat_turns is not None else current["free_daily_chat_turns"]
    new_extra_feed = tokens_per_extra_feed if tokens_per_extra_feed is not None else current["tokens_per_extra_feed"]
    new_extra_chat = tokens_per_chat_turn if tokens_per_chat_turn is not None else current["tokens_per_chat_turn"]

    cursor.execute(
        """INSERT INTO job_token_settings 
           (id, free_daily_feed_limit, free_daily_chat_turns, tokens_per_extra_feed, tokens_per_chat_turn)
           VALUES (1, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
           free_daily_feed_limit=VALUES(free_daily_feed_limit),
           free_daily_chat_turns=VALUES(free_daily_chat_turns),
           tokens_per_extra_feed=VALUES(tokens_per_extra_feed),
           tokens_per_chat_turn=VALUES(tokens_per_chat_turn)""",
        (new_feed, new_chat, new_extra_feed, new_extra_chat),
    )
    return {
        "free_daily_feed_limit": new_feed,
        "free_daily_chat_turns": new_chat,
        "tokens_per_extra_feed": new_extra_feed,
        "tokens_per_chat_turn": new_extra_chat,
    }


def get_user_daily_usage(cursor, user_id: str, today: Optional[date] = None) -> Dict[str, int]:
    """Returns today's recorded usage for this user."""
    today = today or _current_usage_date()
    try:
        cursor.execute(
            """SELECT jobs_viewed, chat_turns, tokens_spent 
               FROM user_daily_job_usage 
               WHERE user_id=%s AND usage_date=%s""",
            (user_id, today),
        )
        row = cursor.fetchone()
        if not row:
            return {"jobs_viewed": 0, "chat_turns": 0, "tokens_spent": 0}
        if isinstance(row, dict):
            return {
                "jobs_viewed": int(row.get("jobs_viewed") or 0),
                "chat_turns": int(row.get("chat_turns") or 0),
                "tokens_spent": int(row.get("tokens_spent") or 0),
            }
        else:
            return {
                "jobs_viewed": int(row[0] or 0),
                "chat_turns": int(row[1] or 0),
                "tokens_spent": int(row[2] or 0),
            }
    except Exception as exc:
        logger.warning("Error fetching daily usage for user %s: %s", user_id, exc)
        return {"jobs_viewed": 0, "chat_turns": 0, "tokens_spent": 0}


def check_and_record_feed_usage(
    cursor,
    user_id: str,
    requested_count: int,
    user_token_balance: Optional[int] = None,
) -> Dict[str, Any]:
    """Checks feed usage quota, records new views, and calculates required token spend.
    
    Returns:
        dict with:
        - is_free (bool)
        - tokens_charged (int)
        - jobs_served (int)
        - free_quota_remaining (int)
        - total_viewed_today (int)
        - free_daily_limit (int)
        - insufficient_tokens (bool)
    """
    settings = get_token_settings(cursor)
    free_limit = settings["free_daily_feed_limit"]
    extra_feed_cost = settings["tokens_per_extra_feed"]

    today = _current_usage_date()
    usage = get_user_daily_usage(cursor, user_id, today)
    viewed_before = usage["jobs_viewed"]

    if viewed_before < free_limit:
        # Free quota still available
        free_available = free_limit - viewed_before
        jobs_served = min(requested_count, free_available)
        tokens_charged = 0
        is_free = True
        new_viewed = viewed_before + jobs_served

        _upsert_daily_usage(cursor, user_id, today, jobs_viewed=new_viewed, chat_turns=usage["chat_turns"], tokens_spent=usage["tokens_spent"])
        return {
            "is_free": True,
            "tokens_charged": 0,
            "jobs_served": jobs_served,
            "free_quota_remaining": max(0, free_limit - new_viewed),
            "total_viewed_today": new_viewed,
            "free_daily_limit": free_limit,
            "insufficient_tokens": False,
        }

    # Free quota already exhausted: this batch requires tokens
    tokens_charged = extra_feed_cost
    jobs_served = requested_count

    # Check if user has enough tokens (if balance known)
    if user_token_balance is not None and user_token_balance < tokens_charged:
        return {
            "is_free": False,
            "tokens_charged": tokens_charged,
            "jobs_served": 0,
            "free_quota_remaining": 0,
            "total_viewed_today": viewed_before,
            "free_daily_limit": free_limit,
            "insufficient_tokens": True,
            "required_tokens": tokens_charged,
            "current_balance": user_token_balance,
        }

    new_viewed = viewed_before + jobs_served
    new_spent = usage["tokens_spent"] + tokens_charged
    _upsert_daily_usage(cursor, user_id, today, jobs_viewed=new_viewed, chat_turns=usage["chat_turns"], tokens_spent=new_spent)

    return {
        "is_free": False,
        "tokens_charged": tokens_charged,
        "jobs_served": jobs_served,
        "free_quota_remaining": 0,
        "total_viewed_today": new_viewed,
        "free_daily_limit": free_limit,
        "insufficient_tokens": False,
    }


def check_and_record_chat_usage(
    cursor,
    user_id: str,
    user_token_balance: Optional[int] = None,
) -> Dict[str, Any]:
    """Checks chat turns quota and determines if chat query is free or charged tokens.
    
    Returns:
        dict with:
        - is_free (bool)
        - tokens_charged (int)
        - free_turns_remaining (int)
        - total_turns_today (int)
        - free_daily_turns (int)
        - insufficient_tokens (bool)
    """
    settings = get_token_settings(cursor)
    free_turns_limit = settings["free_daily_chat_turns"]
    chat_turn_cost = settings["tokens_per_chat_turn"]

    today = _current_usage_date()
    usage = get_user_daily_usage(cursor, user_id, today)
    turns_before = usage["chat_turns"]

    if turns_before < free_turns_limit:
        # Free turn
        new_turns = turns_before + 1
        _upsert_daily_usage(cursor, user_id, today, jobs_viewed=usage["jobs_viewed"], chat_turns=new_turns, tokens_spent=usage["tokens_spent"])
        return {
            "is_free": True,
            "tokens_charged": 0,
            "free_turns_remaining": max(0, free_turns_limit - new_turns),
            "total_turns_today": new_turns,
            "free_daily_turns": free_turns_limit,
            "insufficient_tokens": False,
        }

    # Free quota exhausted -> requires tokens
    tokens_charged = chat_turn_cost
    if user_token_balance is not None and user_token_balance < tokens_charged:
        return {
            "is_free": False,
            "tokens_charged": tokens_charged,
            "free_turns_remaining": 0,
            "total_turns_today": turns_before,
            "free_daily_turns": free_turns_limit,
            "insufficient_tokens": True,
            "required_tokens": tokens_charged,
            "current_balance": user_token_balance,
        }

    new_turns = turns_before + 1
    new_spent = usage["tokens_spent"] + tokens_charged
    _upsert_daily_usage(cursor, user_id, today, jobs_viewed=usage["jobs_viewed"], chat_turns=new_turns, tokens_spent=new_spent)

    return {
        "is_free": False,
        "tokens_charged": tokens_charged,
        "free_turns_remaining": 0,
        "total_turns_today": new_turns,
        "free_daily_turns": free_turns_limit,
        "insufficient_tokens": False,
    }


def _upsert_daily_usage(
    cursor,
    user_id: str,
    usage_date: date,
    jobs_viewed: int,
    chat_turns: int,
    tokens_spent: int,
) -> None:
    """Inserts or updates the daily usage record for user on date."""
    cursor.execute(
        """INSERT INTO user_daily_job_usage 
           (user_id, usage_date, jobs_viewed, chat_turns, tokens_spent)
           VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE
           jobs_viewed=VALUES(jobs_viewed),
           chat_turns=VALUES(chat_turns),
           tokens_spent=VALUES(tokens_spent)""",
        (user_id, usage_date, jobs_viewed, chat_turns, tokens_spent),
    )

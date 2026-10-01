"""Persistent, provider-reported usage ledger for the certificate agent."""
from __future__ import annotations

import contextvars
import logging
from typing import Callable, Dict, Optional

from cert_app.db.database import get_connection

logger = logging.getLogger(__name__)

# The gateway-verified DigiDARA user behind the current request. Set once per
# /api/invoke call so every usage event -- including the LLM calls made deep
# inside the exam and chat services -- is recorded against that user.
_usage_user: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("certificate_usage_user", default=None)


def set_usage_user(user_id: Optional[str]):
    """Attribute usage recorded from here on to ``user_id``; returns a reset token."""
    return _usage_user.set(str(user_id or "").strip() or None)


def reset_usage_user(token) -> None:
    _usage_user.reset(token)


def carry_usage_user(fn: Callable) -> Callable:
    """Wrap ``fn`` so usage it records in another thread still belongs to the
    current user (threads do not inherit the request's context on their own)."""
    user_id = _usage_user.get()

    def run(*args, **kwargs):
        token = _usage_user.set(user_id)
        try:
            return fn(*args, **kwargs)
        finally:
            _usage_user.reset(token)

    return run


def _value(source, *names: str) -> int:
    """Read a usage field from either an SDK object or a mapping."""
    for name in names:
        value = source.get(name) if isinstance(source, dict) else getattr(source, name, None)
        if value is not None:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                pass
    return 0


def record_request(action_name: str) -> None:
    """Record one user-facing API action without inventing a token total."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO certificate_usage_events (action_name, event_type, digidara_user_id) VALUES (%s, 'request', %s)",
            (action_name[:100], _usage_user.get()),
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def record_llm_usage(operation: str, response) -> None:
    """Persist the exact token counts returned by OpenAI/LangChain.

    OpenAI's Chat Completions and Responses APIs expose usage under slightly
    different field names; both are normalized here.  If a provider does not
    return usage, we still preserve no made-up token estimate.
    """
    usage = getattr(response, "usage_metadata", None) or getattr(response, "usage", None) or {}
    input_tokens = _value(usage, "input_tokens", "prompt_tokens")
    output_tokens = _value(usage, "output_tokens", "completion_tokens")
    total_tokens = _value(usage, "total_tokens") or input_tokens + output_tokens
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO certificate_usage_events
                   (action_name, event_type, input_tokens, output_tokens, total_tokens, digidara_user_id)
                   VALUES (%s, 'model', %s, %s, %s, %s)""",
                (operation[:100], input_tokens, output_tokens, total_tokens, _usage_user.get()),
            )
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    except Exception:
        # Usage reporting must never turn a successful learner interaction into
        # a failed exam or a fallback response.
        logger.exception("Could not record LLM usage for %s", operation)


def _summary(totals: Dict, by_type: Dict) -> Dict:
    return {
        "agent_name": "certificate_agent",
        "total_requests": int(totals.get("total_requests") or 0),
        "total_tokens": int(totals.get("total_tokens") or 0),
        "prompt_tokens": int(totals.get("prompt_tokens") or 0),
        "completion_tokens": int(totals.get("completion_tokens") or 0),
        "by_request_type": by_type,
        "token_measurement": "provider_reported",
    }


def get_usage_summary(user_id: Optional[str]) -> Dict:
    """One user's own certificate-agent usage. Without a verified user there is
    nobody to report on, so the totals are zero -- never other learners'."""
    user_id = str(user_id or "").strip()
    if not user_id:
        return _summary({}, {})
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT
                 COALESCE(SUM(event_type = 'request'), 0) AS total_requests,
                 COALESCE(SUM(total_tokens), 0) AS total_tokens,
                 COALESCE(SUM(input_tokens), 0) AS prompt_tokens,
                 COALESCE(SUM(output_tokens), 0) AS completion_tokens
               FROM certificate_usage_events WHERE digidara_user_id = %s""",
            (user_id,),
        )
        totals = cursor.fetchone() or {}
        cursor.execute(
            "SELECT action_name, COUNT(*) AS request_count FROM certificate_usage_events "
            "WHERE event_type = 'request' AND digidara_user_id = %s GROUP BY action_name",
            (user_id,),
        )
        by_type = {row["action_name"]: int(row["request_count"]) for row in cursor.fetchall()}
        return _summary(totals, by_type)
    finally:
        cursor.close()
        conn.close()

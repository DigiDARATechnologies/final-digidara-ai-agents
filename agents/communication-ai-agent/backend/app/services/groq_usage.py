import logging
import uuid

from flask import current_app, has_app_context

from .groq_pricing import estimate_cost

logger = logging.getLogger("communication_agent.llm_usage")


def usage_logging_enabled():
    if not has_app_context():
        return False
    value = current_app.config.get("GROQ_USAGE_LOGGING", True)
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def new_trace_id():
    return uuid.uuid4().hex


def _get_value(obj, *names):
    if obj is None:
        return None
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj.get(name)
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


def _nested_value(obj, *path):
    current = obj
    for name in path:
        current = _get_value(current, name)
        if current is None:
            return None
    return current


def _int_or_none(value):
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_not_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def normalize_usage(usage):
    if not usage:
        return {
            "usage_available": False,
            "input_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "cached_tokens": None,
            "total_tokens": None,
        }

    input_tokens = _int_or_none(_get_value(usage, "prompt_tokens", "input_tokens"))
    output_tokens = _int_or_none(_get_value(usage, "completion_tokens", "output_tokens"))
    total_tokens = _int_or_none(_get_value(usage, "total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    reasoning_tokens = _int_or_none(_first_not_none(
        _get_value(usage, "reasoning_tokens"),
        _nested_value(usage, "completion_tokens_details", "reasoning_tokens"),
        _nested_value(usage, "usage_breakdown", "reasoning_tokens"),
    ))
    cached_tokens = _int_or_none(_first_not_none(
        _get_value(usage, "cached_tokens"),
        _nested_value(usage, "prompt_tokens_details", "cached_tokens"),
        _nested_value(usage, "usage_breakdown", "cached_tokens"),
    ))

    return {
        "usage_available": any(value is not None for value in (input_tokens, output_tokens, total_tokens)),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
    }


def usage_from_response_json(response_json):
    if not isinstance(response_json, dict):
        return normalize_usage(None)
    return normalize_usage(response_json.get("usage"))


def _money(value):
    if value is None:
        return "unavailable"
    return f"${value:.9f}"


def _tokens(value):
    if value is None:
        return "unavailable"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "unavailable"


def _terminal_block(title, rows):
    label_width = max((len(label) for label, _value in rows), default=0)
    lines = [
        "",
        "=" * 60,
        title,
    ]
    lines.extend(f"{label.ljust(label_width)} : {value}" for label, value in rows)
    lines.append("=" * 60)
    return "\n".join(lines)


def _cost_line(model, usage):
    cost = estimate_cost(model, usage)
    if not cost["pricing_available"]:
        return "unavailable"
    return f"{cost['currency']} {_money(cost['estimated_total_cost'])}"


def log_groq_attempt(
    *,
    operation,
    module=None,
    service=None,
    model,
    usage=None,
    response=None,
    latency_ms,
    attempt_number,
    status,
    http_status=None,
    error_code=None,
    trace_id=None,
    metadata=None,
):
    """Print safe Groq usage observability to the Flask backend terminal only.

    This function intentionally does not store usage in the database and does
    not expose prompts, learner answers, API keys, JWTs, headers or model
    response text.
    """
    if not usage_logging_enabled():
        return

    operation = operation or "groq.chat"
    usage = normalize_usage(usage)
    latency = f"{latency_ms / 1000.0:.3f} seconds"
    provider = str((metadata or {}).get("provider") or "Groq").strip() or "Groq"

    if status in {"success", "missing_usage"}:
        block = _terminal_block(
            f"{provider.upper()} TOKEN USAGE",
            [
                ("Operation", operation),
                ("Model", model or "unknown"),
                ("Input tokens", _tokens(usage.get("input_tokens")) if usage.get("usage_available") else "unavailable"),
                ("Output tokens", _tokens(usage.get("output_tokens")) if usage.get("usage_available") else "unavailable"),
                ("Total tokens", _tokens(usage.get("total_tokens")) if usage.get("usage_available") else "unavailable"),
                ("Estimated cost", _cost_line(model, usage)),
                ("Latency", latency),
                ("Attempt", attempt_number),
                ("Status", status),
            ],
        )
        print(block, flush=True)
        return

    block = _terminal_block(
        f"{provider.upper()} REQUEST",
        [
            ("Operation", operation),
            ("Model", model or "unknown"),
            ("Attempt", attempt_number),
            ("Status", status),
            ("HTTP status", http_status or "unavailable"),
            ("Tokens", "unavailable"),
            ("Latency", latency),
            ("Error code", error_code or "unavailable"),
        ],
    )
    print(block, flush=True)


def persist_llm_usage(*, operation, model, usage, provider="Groq"):
    """Best-effort DB persist of just the token counts for a successful call
    — never raises, never blocks the real LLM call it's attached to. Only
    writes what LlmUsage's docstring promises (model/tokens/operation label);
    see that model for why this doesn't conflict with log_groq_attempt's
    terminal-only design."""
    if not has_app_context():
        return
    usage = normalize_usage(usage)
    if not usage.get("usage_available"):
        return
    try:
        from ..extensions import db
        from ..models import LlmUsage

        db.session.add(LlmUsage(
            provider=str(provider or "Groq"),
            model_name=str(model or "unknown"),
            prompt_tokens=int(usage.get("input_tokens") or 0),
            completion_tokens=int(usage.get("output_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            request_type=str(operation or "unspecified"),
        ))
        db.session.commit()
    except Exception:
        logger.warning("failed to persist LLM usage for operation=%s", operation, exc_info=True)
        try:
            from ..extensions import db
            db.session.rollback()
        except Exception:
            pass


def get_usage_summary():
    """Platform-wide aggregate for the `usage_summary` Strategy F action —
    same shape as agents/project_AI_Agent's UsageSummaryResponse."""
    from sqlalchemy import func

    from ..extensions import db
    from ..models import LlmUsage

    totals = db.session.query(
        func.count(LlmUsage.id),
        func.coalesce(func.sum(LlmUsage.total_tokens), 0),
        func.coalesce(func.sum(LlmUsage.prompt_tokens), 0),
        func.coalesce(func.sum(LlmUsage.completion_tokens), 0),
    ).one()
    total_requests, total_tokens, prompt_tokens, completion_tokens = totals

    by_type_rows = (
        db.session.query(LlmUsage.request_type, func.count(LlmUsage.id))
        .group_by(LlmUsage.request_type)
        .all()
    )
    return {
        "agent_name": "communication_agent",
        "total_requests": int(total_requests or 0),
        "total_tokens": int(total_tokens or 0),
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "by_request_type": {str(request_type): int(count) for request_type, count in by_type_rows},
    }

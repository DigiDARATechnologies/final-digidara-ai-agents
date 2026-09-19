"""Provider-neutral AI usage capture and cost calculation."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from threading import Lock
from time import perf_counter

import db
from structured_logging import log_event
import logging


MICRO_DOLLARS_PER_DOLLAR = Decimal("1000000")

# Update prices here (or via environment configuration in a future deployment)
# when a provider changes its published model rates. Values are USD / million tokens.
MODEL_PRICING = {
    "gpt-4o-mini": {
        "input_per_million": Decimal("0.15"),
        "output_per_million": Decimal("0.60"),
    },
    # OpenAI transcription usage is billed as audio tokens rather than the
    # chat prompt/completion token pair used by this cost estimator.
    "gpt-4o-mini-transcribe": {
        "input_per_million": Decimal("0"),
        "output_per_million": Decimal("0"),
    },
}


@dataclass
class UsageScope:
    student_id: int | None = None
    interview_id: int | None = None
    question_id: int | None = None
    request_type: str = "unspecified"
    usage_ids: list[int] = field(default_factory=list)
    _usage_ids_lock: Lock = field(default_factory=Lock, repr=False)

    def add_usage_id(self, usage_id):
        """Safely retain provider usage captured by concurrent plan workers."""
        with self._usage_ids_lock:
            self.usage_ids.append(usage_id)

    def attach(self, interview_id, question_id=None):
        """Attach requests captured before a newly-created row existed."""
        if not self.usage_ids:
            return
        placeholders = ", ".join(["%s"] * len(self.usage_ids))
        db.query(
            f"""UPDATE ai_usage_records
                SET interview_id = %s,
                    question_id = COALESCE(%s, question_id)
                WHERE id IN ({placeholders})""",
            (interview_id, question_id, *self.usage_ids),
        )


_usage_scope = ContextVar("ai_usage_scope", default=None)


@contextmanager
def track_ai_usage(*, student_id=None, interview_id=None, question_id=None, request_type):
    """Make attribution available to the low-level OpenAI client per request."""
    scope = UsageScope(student_id, interview_id, question_id, request_type)
    token = _usage_scope.set(scope)
    try:
        yield scope
    finally:
        _usage_scope.reset(token)


def measure_request(callable_):
    """Run a provider request and return its response with elapsed milliseconds."""
    started = perf_counter()
    response = callable_()
    return response, int((perf_counter() - started) * 1000)


def _usage_value(usage, key):
    if usage is None:
        return 0
    value = usage.get(key) if isinstance(usage, dict) else getattr(usage, key, None)
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def estimate_cost(prompt_tokens, completion_tokens, model_name):
    pricing = MODEL_PRICING.get(model_name, {
        "input_per_million": Decimal("0"),
        "output_per_million": Decimal("0"),
    })
    return (
        Decimal(prompt_tokens) * pricing["input_per_million"]
        + Decimal(completion_tokens) * pricing["output_per_million"]
    ) / MICRO_DOLLARS_PER_DOLLAR


def record_provider_usage(response, *, provider, model_name, response_time_ms):
    """Persist provider-reported usage. Never infer tokens from request text."""
    scope = _usage_scope.get()
    usage = getattr(response, "usage", None)
    prompt_tokens = _usage_value(usage, "prompt_tokens")
    completion_tokens = _usage_value(usage, "completion_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    if usage is None:
        log_event(
            logging.getLogger(__name__), logging.WARNING,
            "ai_usage_unavailable", "AI provider response did not include usage",
            provider=provider, model_name=model_name,
            request_type=scope.request_type if scope else "unspecified",
        )
    if not total_tokens:
        total_tokens = prompt_tokens + completion_tokens
    estimated_cost = estimate_cost(prompt_tokens, completion_tokens, model_name)
    _, usage_id = db.query(
        """INSERT INTO ai_usage_records
             (student_id, interview_id, question_id, provider, model_name,
              prompt_tokens, completion_tokens, total_tokens, estimated_cost,
              request_type, response_time_ms)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            scope.student_id if scope else None,
            scope.interview_id if scope else None,
            scope.question_id if scope else None,
            provider, model_name, prompt_tokens, completion_tokens, total_tokens,
            estimated_cost, scope.request_type if scope else "unspecified",
            response_time_ms,
        ),
    )
    if scope and usage_id:
        scope.add_usage_id(usage_id)
    return usage_id


def decimal_to_float(value):
    return float(Decimal(value or 0).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))

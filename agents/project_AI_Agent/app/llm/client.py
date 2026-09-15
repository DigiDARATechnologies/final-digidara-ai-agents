"""
Provider-agnostic LLM client.

The rest of the app never imports a vendor SDK directly and never hardcodes a
model name. Swapping providers (Groq / OpenAI / Claude / local Ollama) is a
single environment variable change (LLM_MODEL in .env) — see .env.example.
litellm normalizes the request/response shape across all of them.
"""
from __future__ import annotations

import inspect
import itertools
import json
import logging
import re
import time
from typing import Any

import litellm
from litellm.exceptions import BadRequestError, RateLimitError

from app import config
from app.db.database import get_session
from app.db.models import LlmUsage
from app.request_context import current_user_id

litellm.drop_params = True  # silently drop params a given provider doesn't support

logger = logging.getLogger("capstone.llm")
_call_counter = itertools.count(1)

_PROMPT_LOG_CHARS = 2000  # cap so a code-review prompt with embedded files doesn't flood the terminal
_RATE_LIMIT_RETRIES = 3


def _retry_after_seconds(exc: Exception, attempt: int) -> float:
    """Use Groq's reset hint when available, otherwise bounded backoff."""
    match = re.search(r"try again in\\s+([0-9.]+)s", str(exc), re.IGNORECASE)
    if match:
        return min(60.0, max(1.0, float(match.group(1)) + 1.0))
    return min(60.0, 5.0 * (2 ** attempt))


def _provider_completion(kwargs: dict[str, Any], caller: str, call_id: int) -> Any:
    """Retry only genuine rate limits; never repeat every provider failure."""
    for attempt in range(_RATE_LIMIT_RETRIES + 1):
        try:
            return litellm.completion(**kwargs)
        except RateLimitError as exc:
            if attempt >= _RATE_LIMIT_RETRIES:
                raise LLMError("The AI provider is temporarily rate limited. Please retry in about one minute.") from exc
            wait_seconds = _retry_after_seconds(exc, attempt)
            logger.warning("[LLM #%d] %s rate limited; retrying in %.1fs (%d/%d)", call_id, caller, wait_seconds, attempt + 1, _RATE_LIMIT_RETRIES)
            time.sleep(wait_seconds)


def _caller_name() -> str:
    """Best-effort name of the graph node that triggered this call, purely for
    readable log lines — walks up past call_json/call_text/_complete."""
    frame = inspect.currentframe()
    try:
        f = frame.f_back.f_back  # skip this function + the call_json/call_text wrapper
        return f.f_code.co_name if f else "unknown"
    finally:
        del frame


def _truncate(text: str, limit: int = _PROMPT_LOG_CHARS) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n... [truncated, {len(text)} chars total]"


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction: try a straight parse, then fall back to
    pulling the outermost {...} block out of chatty/markdown-wrapped output."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise LLMError(f"Could not parse JSON from model output: {text[:500]!r}")


def _record_usage(usage: Any, caller: str, model: str) -> None:
    """Best-effort persist — a usage-logging failure must never break the
    actual LLM call it's attached to."""
    if usage is None:
        return
    session = get_session()
    try:
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", 0) or (prompt_tokens + completion_tokens))
        provider = model.split("/", 1)[0] if "/" in model else model
        session.add(LlmUsage(
            user_id=current_user_id.get(),
            provider=provider,
            model_name=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            request_type=caller,
        ))
        session.commit()
    except Exception:
        logger.warning("failed to record LLM usage for caller=%s", caller, exc_info=True)
        session.rollback()
    finally:
        session.close()


def _complete(
    system: str, user: str, json_mode: bool, caller: str, call_id: int, temperature: float, web_search: bool = False
) -> str:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    # web_search routes to a dedicated OpenAI search-preview model rather
    # than switching the whole app's LLM_MODEL — keeps the (pricier, slower)
    # search path scoped to just the calls that actually need current,
    # real-world grounding (see nodes.topic_generator_node for free-topic
    # requests), not every LLM call in the graph.
    model = config.WEB_SEARCH_LLM_MODEL if web_search else config.LLM_MODEL
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if web_search:
        # Search-capable models reject `temperature` outright (a hard 400,
        # not something litellm.drop_params catches — that only pre-filters
        # params litellm already knows a provider rejects) — simplest fix is
        # to just not send it for this call shape.
        # "low" is OpenAI's own token/cost lever for how much search-result
        # content gets pulled into context — the cheapest setting that still
        # grounds the answer, since this call only needs enough to steer two
        # short topic ideas, not a research report.
        kwargs["web_search_options"] = {"search_context_size": config.WEB_SEARCH_CONTEXT_SIZE}
    else:
        kwargs["temperature"] = temperature
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    logger.info("[LLM #%d] %s -> model=%s json_mode=%s web_search=%s", call_id, caller, model, json_mode, web_search)
    logger.debug("[LLM #%d] %s SYSTEM PROMPT:\n%s", call_id, caller, _truncate(system))
    logger.debug("[LLM #%d] %s USER PROMPT:\n%s", call_id, caller, _truncate(user))

    started = time.perf_counter()
    try:
        response = _provider_completion(kwargs, caller, call_id)
    except BadRequestError:
        if "response_format" not in kwargs:
            raise
        # Some providers/models reject response_format outright rather than
        # ignoring it (older Ollama builds). Retry once without it.
        logger.warning("[LLM #%d] %s response_format rejected, retrying without it", call_id, caller)
        kwargs.pop("response_format", None)
        response = _provider_completion(kwargs, caller, call_id)
    elapsed = time.perf_counter() - started

    content = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    _record_usage(usage, caller, model)
    usage_str = (
        f"input={usage.prompt_tokens} output={usage.completion_tokens}"
        if usage is not None
        else "usage=unavailable"
    )
    logger.info("[LLM #%d] %s <- %.2fs, %s", call_id, caller, elapsed, usage_str)
    logger.debug("[LLM #%d] %s RESPONSE:\n%s", call_id, caller, _truncate(content))

    return content


def call_json(
    system: str, user: str, retries: int = 1, temperature: float = 0.2, web_search: bool = False
) -> dict[str, Any]:
    """Call the configured LLM and return parsed JSON. Retries once with a
    stricter reminder if the first response isn't valid JSON.

    `temperature` defaults low (consistent, repeatable judgments) — validators
    and scorers want that. Pass a higher value for calls that should vary
    run-to-run (e.g. topic generation), where low temperature just means the
    model keeps producing near-identical output for the same input.

    `web_search` routes this call through a dedicated OpenAI search-preview
    model (config.WEB_SEARCH_LLM_MODEL) instead of config.LLM_MODEL — see
    _complete's docstring comment. Only pass True for calls that genuinely
    benefit from current, real-world grounding; it costs more and is slower
    than a plain completion, so it isn't the default for every call."""
    caller = _caller_name()
    call_id = next(_call_counter)
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        prompt = user
        if attempt > 0:
            logger.warning("[LLM #%d] %s retrying after invalid JSON (attempt %d)", call_id, caller, attempt + 1)
            prompt = (
                user
                + "\n\nYour previous reply was not valid JSON. "
                + "Reply with ONLY the JSON object — no prose, no markdown fences."
            )
        try:
            raw = _complete(
                system, prompt, json_mode=True, caller=caller, call_id=call_id,
                temperature=temperature, web_search=web_search,
            )
            parsed = _extract_json(raw)
            logger.info("[LLM #%d] %s parsed JSON keys: %s", call_id, caller, list(parsed.keys()))
            return parsed
        except LLMError as exc:
            last_error = exc
            logger.error("[LLM #%d] %s JSON parse failed: %s", call_id, caller, exc)
    raise last_error or LLMError("LLM call failed with no captured error")


def call_text(system: str, user: str, temperature: float = 0.2) -> str:
    """Call the configured LLM and return plain text (for the final,
    human-readable feedback message — not routed on, so no JSON needed)."""
    caller = _caller_name()
    call_id = next(_call_counter)
    return _complete(system, user, json_mode=False, caller=caller, call_id=call_id, temperature=temperature).strip()

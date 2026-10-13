"""Provider-agnostic LLM client with OpenAI-style function-calling, used by
the orchestrator's `route_node` to pick a registered agent. Swapping
providers is a single `LLM_MODEL` env var change — see .env."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterator

import litellm

from app import config

litellm.drop_params = True  # silently drop params a given provider doesn't support

logger = logging.getLogger("orchestrator.llm")


def call_with_tools(
    system: str, user: str, tools: list[dict[str, Any]], history: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    """One LLM turn with optional tools bound. Returns either
    {"tool_name": str, "tool_args": dict} if the model chose to call one of
    the given tools, or {"text": str} if it answered directly.

    `history` (each item `{"role": "user"|"assistant", "content": str}`,
    oldest first) lets a routing decision see the whole conversation, not
    just the latest message — a request that's genuinely ambiguous as one
    line ("html developer") is often obvious by the third or fourth turn."""
    messages = [{"role": "system", "content": system}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user})
    # max_tokens bounds both cost and how much a manipulated reply can say.
    kwargs: dict[str, Any] = {"model": config.LLM_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 700}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    started = time.perf_counter()
    response = litellm.completion(**kwargs)
    elapsed = time.perf_counter() - started

    message = response.choices[0].message
    tool_calls = getattr(message, "tool_calls", None)
    logger.info(
        "route turn in %.2fs, tools_offered=%d, tool_called=%s",
        elapsed, len(tools), bool(tool_calls),
    )

    if tool_calls:
        call = tool_calls[0]
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            # Length only: the arguments echo the learner's own words.
            logger.warning("model returned non-JSON tool arguments (%d chars)", len(call.function.arguments or ""))
            args = {}
        return {"tool_name": call.function.name, "tool_args": args}

    return {"text": (message.content or "").strip()}


def stream_with_tools(
    system: str, user: str, tools: list[dict[str, Any]], history: list[dict[str, str]] | None = None,
    max_tokens: int = 700,
) -> Iterator[tuple[str, Any]]:
    """call_with_tools, streamed: yields ("text", delta) as the answer is
    written, then ("tool", {"tool_name", "tool_args"}) if the model chose a
    tool instead. A spoken reply can start after its first sentence."""
    messages = [{"role": "system", "content": system}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user})
    kwargs: dict[str, Any] = {
        "model": config.LLM_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens, "stream": True,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    started = time.perf_counter()
    first_token: float | None = None
    tool_name = ""
    tool_args = ""
    for chunk in litellm.completion(**kwargs):
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        delta = choices[0].delta
        for call in getattr(delta, "tool_calls", None) or []:
            function = getattr(call, "function", None)
            if function is None:
                continue
            tool_name += getattr(function, "name", None) or ""
            tool_args += getattr(function, "arguments", None) or ""
        content = getattr(delta, "content", None)
        if content:
            if first_token is None:
                first_token = time.perf_counter() - started
            yield "text", content
    logger.info(
        "streamed route turn in %.2fs (first text %.2fs), tools_offered=%d, tool_called=%s",
        time.perf_counter() - started, first_token or 0.0, len(tools), bool(tool_name),
    )
    if tool_name:
        try:
            args = json.loads(tool_args or "{}")
        except json.JSONDecodeError:
            logger.warning("model returned non-JSON tool arguments (%d chars)", len(tool_args))
            args = {}
        yield "tool", {"tool_name": tool_name, "tool_args": args}


def call_text(system: str, user: str, temperature: float = 0.3) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    response = litellm.completion(model=config.LLM_MODEL, messages=messages, temperature=temperature)
    return (response.choices[0].message.content or "").strip()

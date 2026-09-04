"""Provider-agnostic LLM client with OpenAI-style function-calling, used by
the orchestrator's `route_node` to pick a registered agent. Swapping
providers is a single `LLM_MODEL` env var change — see .env."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

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
    kwargs: dict[str, Any] = {"model": config.LLM_MODEL, "messages": messages, "temperature": 0.2}
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
            logger.warning("model returned non-JSON tool arguments: %r", call.function.arguments)
            args = {}
        return {"tool_name": call.function.name, "tool_args": args}

    return {"text": (message.content or "").strip()}


def call_text(system: str, user: str, temperature: float = 0.3) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    response = litellm.completion(model=config.LLM_MODEL, messages=messages, temperature=temperature)
    return (response.choices[0].message.content or "").strip()

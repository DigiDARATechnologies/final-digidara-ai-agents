"""Provider-agnostic LLM client with OpenAI-style function-calling, used by
the orchestrator's `route_node` to pick a registered agent. Swapping
providers is a single `LLM_MODEL` env var change — see .env."""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from typing import Any, Iterator

import litellm

from app import config

litellm.drop_params = True  # silently drop params a given provider doesn't support

logger = logging.getLogger("orchestrator.llm")


def call_with_tools(
    system: str, user: str, tools: list[dict[str, Any]], history: list[dict[str, str]] | None = None,
    usage: dict[str, int] | None = None,
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
    if usage is not None:
        record_usage(usage, getattr(response, "usage", None), messages, response.choices[0].message.content or "")

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


# A streamed turn whose first word has not arrived by then gets a second,
# identical request, and whichever answers first is used. Provider latency
# spikes (a 4-10 s first word from a model that usually starts in ~1 s) are
# what makes Boss feel slow in a voice conversation; 0 turns this off.
HEDGE_AFTER_SECONDS = float(os.environ.get("LLM_HEDGE_AFTER_SECONDS", "1.5"))

_END = object()

# Without a usage report from the provider, a screenshot is counted at about
# what a 1280px image costs.
_IMAGE_TOKENS = 1_100


def estimate_tokens(messages: list[dict[str, Any]], output: str) -> int:
    """Roughly what a call cost when the provider did not say: about four
    characters a token, plus a fixed amount per image."""
    chars = len(output)
    images = 0
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    images += 1
                else:
                    chars += len(str(part.get("text") or ""))
    return max(1, chars // 4) + images * _IMAGE_TOKENS


def record_usage(usage: dict[str, int], reported: Any, messages: list[dict[str, Any]], output: str) -> None:
    """Adds one call's tokens to `usage["tokens"]`: the provider's own count
    when it sent one, else an estimate, so a call is never free by accident."""
    total = getattr(reported, "total_tokens", None) if reported is not None else None
    if not isinstance(total, int) or total <= 0:
        total = estimate_tokens(messages, output)
    usage["tokens"] = usage.get("tokens", 0) + total


def _chunk_usage(chunk: Any) -> Any:
    """The usage report a stream sends with its last chunk (None before)."""
    reported = getattr(chunk, "usage", None)
    return reported if getattr(reported, "total_tokens", None) else None


def _has_output(chunk: Any) -> bool:
    """A chunk carrying answer text or a tool call (not the bare role chunk)."""
    choices = getattr(chunk, "choices", None) or []
    if not choices:
        return False
    delta = choices[0].delta
    return bool(getattr(delta, "content", None) or getattr(delta, "tool_calls", None))


def _hedged_chunks(kwargs: dict[str, Any]) -> Iterator[Any]:
    """litellm's stream, hedged: after HEDGE_AFTER_SECONDS with no output a
    second request starts; the first to produce output wins and the other's
    chunks are dropped. A request that fails is ignored while the other one
    can still answer."""
    if HEDGE_AFTER_SECONDS <= 0:
        yield from litellm.completion(**kwargs)
        return
    events: queue.Queue[tuple[int, Any]] = queue.Queue()
    stop = [threading.Event(), threading.Event()]

    def run(tag: int) -> None:
        try:
            for chunk in litellm.completion(**kwargs):
                if stop[tag].is_set():
                    return
                events.put((tag, chunk))
            events.put((tag, _END))
        except Exception as exc:  # noqa: BLE001 - handed to the reader below
            events.put((tag, exc))

    def start(tag: int) -> None:
        threading.Thread(target=run, args=(tag,), name=f"llm-stream-{tag}", daemon=True).start()

    start(0)
    started = 1
    deadline = time.monotonic() + HEDGE_AFTER_SECONDS
    winner: int | None = None
    waiting: dict[int, list[Any]] = {0: [], 1: []}
    failed: dict[int, BaseException] = {}
    while True:
        timeout = None if winner is not None or started == 2 else max(0.0, deadline - time.monotonic())
        try:
            tag, item = events.get(timeout=timeout)
        except queue.Empty:
            logger.info("no first word after %.1fs: sending a second request", HEDGE_AFTER_SECONDS)
            start(1)
            started = 2
            continue
        if winner is not None and tag != winner:
            continue
        if isinstance(item, BaseException):
            if winner is not None:
                raise item
            failed[tag] = item
            if len(failed) == started:
                if started == 1:
                    raise item
                raise failed[0]
            continue
        if item is _END:
            if winner is not None:
                return
            # Finished without any output (an empty answer): nothing to race for.
            stop[1 - tag].set()
            yield from waiting[tag]
            return
        if winner is None:
            if not _has_output(item):
                waiting[tag].append(item)
                continue
            winner = tag
            stop[1 - tag].set()
            if tag == 1:
                logger.info("the second request answered first")
            yield from waiting[tag]
        yield item


def stream_with_tools(
    system: str, user: str, tools: list[dict[str, Any]], history: list[dict[str, str]] | None = None,
    max_tokens: int = 700, usage: dict[str, int] | None = None,
) -> Iterator[tuple[str, Any]]:
    """call_with_tools, streamed: yields ("text", delta) as the answer is
    written, then ("tool", {"tool_name", "tool_args"}) if the model chose a
    tool instead. A spoken reply can start after its first sentence."""
    messages = [{"role": "system", "content": system}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user})
    kwargs: dict[str, Any] = {
        "model": config.LLM_MODEL, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens, "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    started = time.perf_counter()
    first_token: float | None = None
    tool_name = ""
    tool_args = ""
    reported = None
    written = ""
    for chunk in _hedged_chunks(kwargs):
        reported = _chunk_usage(chunk) or reported
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
            written += content
            yield "text", content
    logger.info(
        "streamed route turn in %.2fs (first text %.2fs), tools_offered=%d, tool_called=%s",
        time.perf_counter() - started, first_token or 0.0, len(tools), bool(tool_name),
    )
    if usage is not None:
        record_usage(usage, reported, messages, written + tool_name + tool_args)
    if tool_name:
        try:
            args = json.loads(tool_args or "{}")
        except json.JSONDecodeError:
            logger.warning("model returned non-JSON tool arguments (%d chars)", len(tool_args))
            args = {}
        yield "tool", {"tool_name": tool_name, "tool_args": args}


def stream_plain(messages: list[dict[str, Any]], max_tokens: int = 600,
                 usage: dict[str, int] | None = None) -> Iterator[str]:
    """A plain streamed answer (no tools): yields text as it is written.
    `messages` may carry an image; a single request, not hedged, so a
    screenshot is not sent twice. `usage["tokens"]` gets what it cost."""
    reported = None
    written = ""
    for chunk in litellm.completion(
        model=config.LLM_MODEL, messages=messages, temperature=0.2, max_tokens=max_tokens, stream=True,
        stream_options={"include_usage": True},
    ):
        reported = _chunk_usage(chunk) or reported
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            continue
        content = getattr(choices[0].delta, "content", None)
        if content:
            written += content
            yield content
    if usage is not None:
        record_usage(usage, reported, messages, written)


def warm_up() -> None:
    """One-word request, so the first real question of a voice conversation
    does not pay for opening the connection to the model (a cold first turn
    measured 12 s against 1.5 s for the next). Never raises."""
    try:
        litellm.completion(model=config.LLM_MODEL, messages=[{"role": "user", "content": "Hi"}], max_tokens=1)
    except Exception:  # noqa: BLE001 - a warm-up must never fail a request
        logger.info("llm warm-up failed", exc_info=True)


def call_text(system: str, user: str, temperature: float = 0.3) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    response = litellm.completion(model=config.LLM_MODEL, messages=messages, temperature=temperature)
    return (response.choices[0].message.content or "").strip()

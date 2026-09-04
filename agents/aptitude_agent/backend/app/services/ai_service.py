"""OpenAI-backed provider used by the Aptitude Agent.

This module intentionally keeps the provider-neutral completion contract that
the feature services already use while removing the agent's runtime Groq
dependency.  Retry, deadline, and circuit-breaker policy remains centralized
here so question, hint, and recommendation calls behave consistently.
"""
import json
import math
import threading
import time
from typing import Any

from flask import current_app
from openai import OpenAI


_circuit_lock = threading.Lock()
_circuits = {}


class AIProviderError(RuntimeError):
    def __init__(self, kind, message, transient=False, status_code=None, retry_after=None):
        super().__init__(message)
        self.kind = kind
        self.transient = transient
        self.status_code = status_code
        self.retry_after = retry_after


def _provider_error(exc):
    name = type(exc).__name__.lower()
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    retry_after = headers.get("retry-after")
    if "auth" in name or status in (401, 403):
        return AIProviderError("authentication", str(exc), False, status, retry_after)
    if status == 404:
        return AIProviderError("model_not_found", str(exc), False, status, retry_after)
    if status == 400:
        return AIProviderError("invalid_request", str(exc), False, status, retry_after)
    if "rate" in name or status == 429:
        return AIProviderError("rate_limit", str(exc), True, status, retry_after)
    if "timeout" in name or "connect" in name or status == 408 or (isinstance(status, int) and status >= 500):
        return AIProviderError("transient", str(exc), True, status, retry_after)
    return AIProviderError("request", str(exc), False, status, retry_after)


def empty_usage():
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "model": None}


def merge_usage(first, second):
    merged = {key: int(first.get(key, 0) or 0) + int(second.get(key, 0) or 0)
              for key in ("input_tokens", "output_tokens", "total_tokens")}
    merged["model"] = second.get("model") or first.get("model")
    for key in ("provider_wait_ms", "provider_retry_count", "provider_attempt_count"):
        merged[key] = (float(first.get(key, 0) or 0) + float(second.get(key, 0) or 0))
    merged["provider_retry_count"] = int(merged["provider_retry_count"])
    merged["provider_attempt_count"] = int(merged["provider_attempt_count"])
    return merged


def response_usage(response, model):
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens,
            "total_tokens": int(getattr(usage, "total_tokens", 0) or input_tokens + output_tokens),
            "model": model}


def client(timeout=None):
    key = current_app.config.get("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key, timeout=timeout or current_app.config["OPENAI_TIMEOUT_SECONDS"], max_retries=0)


def _models():
    ordered = [current_app.config.get("OPENAI_MODEL"), *current_app.config.get("OPENAI_FALLBACK_MODELS", ())]
    return list(dict.fromkeys(model for model in ordered if model))


def _available(model):
    with _circuit_lock:
        return _circuits.get(model, {}).get("open_until", 0) <= time.monotonic()


def _success(model):
    with _circuit_lock:
        _circuits[model] = {"failures": 0, "open_until": 0}


def _failure(model, error):
    with _circuit_lock:
        state = _circuits.setdefault(model, {"failures": 0, "open_until": 0})
        state["failures"] += 1
        if state["failures"] >= current_app.config["OPENAI_CIRCUIT_FAILURE_THRESHOLD"]:
            state["open_until"] = time.monotonic() + current_app.config["OPENAI_CIRCUIT_COOLDOWN_SECONDS"]


def _rate_limited(model, error):
    try:
        retry_after = max(0.1, float(error.retry_after))
    except (TypeError, ValueError):
        retry_after = float(current_app.config["OPENAI_CIRCUIT_COOLDOWN_SECONDS"])
    with _circuit_lock:
        state = _circuits.setdefault(model, {"failures": 0, "open_until": 0})
        state["open_until"] = max(state.get("open_until", 0), time.monotonic() + retry_after + 0.15)


def _remaining_seconds(deadline):
    return None if deadline is None else deadline - time.monotonic()


def _complete(request_builder, *, models=None, deadline=None, timeout=None):
    if not current_app.config.get("OPENAI_API_KEY"):
        raise AIProviderError("authentication", "OPENAI_API_KEY is not configured", False)
    selected_models = list(dict.fromkeys(models or _models()))
    last_error = None
    wait_ms = 0.0
    retries = 0
    attempts = 0
    for model in selected_models:
        if not _available(model):
            continue
        for model_attempt in range(2):
            remaining = _remaining_seconds(deadline)
            if remaining is not None and remaining <= 0:
                raise AIProviderError("deadline_exceeded", "OpenAI request deadline exceeded", True)
            call_timeout = float(timeout or current_app.config["OPENAI_TIMEOUT_SECONDS"])
            if remaining is not None:
                call_timeout = min(call_timeout, remaining)
            call_timeout = max(0.1, call_timeout)
            started = time.perf_counter()
            attempts += 1
            try:
                response = request_builder(client(call_timeout), model)
                elapsed = (time.perf_counter() - started) * 1000
                wait_ms += elapsed
                _success(model)
                current_app.logger.info("OpenAI provider timing model=%s attempt=%s status=success duration_ms=%.2f retry_count=%s", model, model_attempt + 1, elapsed, retries)
                return response, model, {"provider_wait_ms": round(wait_ms, 2), "provider_retry_count": retries, "provider_attempt_count": attempts}
            except Exception as exc:
                elapsed = (time.perf_counter() - started) * 1000
                wait_ms += elapsed
                last_error = _provider_error(exc)
                current_app.logger.warning("OpenAI provider timing model=%s attempt=%s status=failed duration_ms=%.2f kind=%s http_status=%s retry_after=%s error_type=%s error=%s", model, model_attempt + 1, elapsed, last_error.kind, last_error.status_code, last_error.retry_after, type(exc).__name__, str(exc)[:500])
                if last_error.kind == "rate_limit":
                    _rate_limited(model, last_error)
                    break
                if last_error.transient:
                    _failure(model, last_error)
                if not last_error.transient or model_attempt == 1:
                    break
                retries += 1
    if last_error:
        raise last_error
    raise AIProviderError("circuit_open", f"OpenAI circuit is open for configured models: {', '.join(selected_models)}", True)


def json_completion(system: str, prompt: str, temperature: float = 0, *, models=None, deadline=None, timeout=None, maximum_tokens=None):
    def request(openai_client, model):
        return openai_client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=maximum_tokens or current_app.config["OPENAI_JSON_MAX_COMPLETION_TOKENS"],
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
    response, model, meta = _complete(request, models=models, deadline=deadline, timeout=timeout)
    content = response.choices[0].message.content
    if not content:
        raise AIProviderError("empty_response", "OpenAI returned an empty JSON response", True)
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content
        content = content.rsplit("```", 1)[0].strip()
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI response must be a JSON object")
    return parsed, {**response_usage(response, model), **meta}


def text_completion(system: str, prompt: str, maximum_tokens: int = 180, *, models=None, deadline=None, timeout=None, reasoning_effort=None):
    def request(openai_client, model):
        return openai_client.chat.completions.create(
            model=model,
            temperature=0.3,
            max_tokens=maximum_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        )
    response, model, meta = _complete(request, models=models, deadline=deadline, timeout=timeout)
    content = response.choices[0].message.content
    usage = {**response_usage(response, model), **meta}
    if not content:
        raise AIProviderError("empty_response", f"OpenAI returned empty text content model={model}", True)
    return content, usage

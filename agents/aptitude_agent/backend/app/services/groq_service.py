import json
import math
import threading
import time
from typing import Any
from flask import current_app
# Legacy compatibility module. Runtime code imports ``ai_service``; this alias
# avoids importing the removed Groq SDK for older callers during migration.
from openai import OpenAI as Groq


_circuit_lock=threading.Lock()
_circuits={}
class GroqProviderError(RuntimeError):
    def __init__(self, kind, message, transient=False, status_code=None, retry_after=None):
        super().__init__(message)
        self.kind=kind;self.transient=transient;self.status_code=status_code;self.retry_after=retry_after

def _provider_error(exc):
    name=type(exc).__name__.lower();status=getattr(exc,"status_code",None)
    headers=getattr(getattr(exc,"response",None),"headers",{}) or {}
    retry_after=headers.get("retry-after")
    if status==400 and "json_validate_failed" in str(exc):
        return GroqProviderError("invalid_json",str(exc),True,status,retry_after)
    if "auth" in name or status in (401,403):return GroqProviderError("authentication",str(exc),False,status,retry_after)
    if status==404:return GroqProviderError("model_not_found",str(exc),False,status,retry_after)
    if status==400:return GroqProviderError("invalid_request",str(exc),False,status,retry_after)
    if "rate" in name or status==429:return GroqProviderError("rate_limit",str(exc),True,status,retry_after)
    if "timeout" in name or "connect" in name or status==408 or isinstance(status,int) and status>=500:return GroqProviderError("transient",str(exc),True,status,retry_after)
    return GroqProviderError("request",str(exc),False,status,retry_after)


def empty_usage():
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "model": None}


def merge_usage(first, second):
    merged={key:int(first.get(key,0) or 0)+int(second.get(key,0) or 0) for key in ("input_tokens","output_tokens","total_tokens")}
    merged["model"]=second.get("model") or first.get("model")
    merged["provider_wait_ms"]=round(float(first.get("provider_wait_ms",0) or 0)+float(second.get("provider_wait_ms",0) or 0),2)
    merged["provider_retry_count"]=int(first.get("provider_retry_count",0) or 0)+int(second.get("provider_retry_count",0) or 0)
    merged["provider_attempt_count"]=int(first.get("provider_attempt_count",0) or 0)+int(second.get("provider_attempt_count",0) or 0)
    return merged


def response_usage(response, model):
    usage = getattr(response, "usage", None)
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": int(getattr(usage, "total_tokens", 0) or input_tokens + output_tokens), "model": model,
    }


def client(timeout=None):
    if not current_app.config["GROQ_API_KEY"]:
        return None
    return Groq(
        api_key=current_app.config["GROQ_API_KEY"],
        timeout=timeout or current_app.config["GROQ_TIMEOUT_SECONDS"],
        # Retry/failover is owned below. Hidden SDK retries previously added
        # 5-6 second sleeps that were invisible to the request budget.
        max_retries=0,
    )


def _models():
    ordered=[current_app.config["GROQ_MODEL"],*current_app.config.get("GROQ_FALLBACK_MODELS",())]
    return list(dict.fromkeys(model for model in ordered if model))


def _available(model):
    with _circuit_lock:
        return _circuits.get(model,{}).get("open_until",0)<=time.monotonic()


def _availability(model):
    with _circuit_lock:
        state=dict(_circuits.get(model,{"open_until":0}))
    return max(0.0,float(state.get("open_until",0) or 0)-time.monotonic()),state.get("last_error_kind")


def _success(model):
    with _circuit_lock:_circuits[model]={"failures":0,"open_until":0}


def _failure(model, error):
    threshold=current_app.config["GROQ_CIRCUIT_FAILURE_THRESHOLD"]
    cooldown=current_app.config["GROQ_CIRCUIT_COOLDOWN_SECONDS"]
    with _circuit_lock:
        state=_circuits.setdefault(model,{"failures":0,"open_until":0});state["failures"]+=1
        state["last_error_kind"]=error.kind
        if state["failures"]>=threshold:state["open_until"]=time.monotonic()+cooldown


def _rate_limited(model,error):
    try:
        retry_after=max(0.1,float(error.retry_after))
    except (TypeError,ValueError):
        retry_after=float(current_app.config["GROQ_CIRCUIT_COOLDOWN_SECONDS"])
    with _circuit_lock:
        state=_circuits.setdefault(model,{"failures":0,"open_until":0})
        state["last_error_kind"]="rate_limit"
        # A small guard avoids retrying on the exact boundary reported by the
        # provider, where clock/network skew can produce another immediate 429.
        state["open_until"]=max(state.get("open_until",0),time.monotonic()+retry_after+.15)
    return retry_after


def _wait_for_rate_limit_window(models,deadline):
    states=[(model,*_availability(model)) for model in models]
    if any(remaining<=0 for _model,remaining,_kind in states):
        return
    if not states or any(kind!="rate_limit" for _model,_remaining,kind in states):
        return
    wait_seconds=min(remaining for _model,remaining,_kind in states)
    deadline_remaining=_remaining_seconds(deadline)
    if deadline_remaining is None or wait_seconds<deadline_remaining:
        current_app.logger.info(
            "Groq rate-limit cooldown wait duration_ms=%.2f models=%s",
            wait_seconds*1000,",".join(models),
        )
        time.sleep(wait_seconds)
        return
    raise GroqProviderError(
        "rate_limit",
        "Groq models remain rate-limited beyond the request deadline",
        True,429,str(max(1,math.ceil(wait_seconds))),
    )


def _remaining_seconds(deadline):
    return None if deadline is None else deadline-time.monotonic()


def _complete(request_builder, *, models=None, deadline=None, timeout=None):
    if not current_app.config["GROQ_API_KEY"]:return None
    attempted=[];last_error=None;provider_wait=0.0;provider_retries=0;provider_attempts=0
    selected_models=list(dict.fromkeys(models or _models()))
    # A previous request (often background prefetch) may already have received
    # Retry-After from every model. A later foreground request can wait once,
    # within its own shared deadline, instead of immediately repeating 429s.
    _wait_for_rate_limit_window(selected_models,deadline)
    for model in selected_models:
        if not _available(model):continue
        attempted.append(model)
        # One initial attempt plus exactly one same-model retry for transport
        # failures. Rate limits always move directly to the next model.
        for model_attempt in range(2):
            remaining=_remaining_seconds(deadline)
            if remaining is not None and remaining<=0:
                raise GroqProviderError("deadline_exceeded","Groq request deadline exceeded",True)
            call_timeout=min(float(timeout or current_app.config["GROQ_TIMEOUT_SECONDS"]),remaining) if remaining is not None else float(timeout or current_app.config["GROQ_TIMEOUT_SECONDS"])
            call_timeout=max(.1,call_timeout)
            groq=client(call_timeout)
            call_started=time.perf_counter();provider_attempts+=1
            try:
                response=request_builder(groq,model)
                elapsed=(time.perf_counter()-call_started)*1000;provider_wait+=elapsed
                _success(model)
                current_app.logger.info(
                    "Groq provider timing model=%s attempt=%s status=success duration_ms=%.2f retry_count=%s",
                    model,model_attempt+1,elapsed,provider_retries,
                )
                return response,model,{"provider_wait_ms":round(provider_wait,2),"provider_retry_count":provider_retries,"provider_attempt_count":provider_attempts}
            except Exception as exc:
                elapsed=(time.perf_counter()-call_started)*1000;provider_wait+=elapsed
                last_error=_provider_error(exc)
                current_app.logger.warning(
                    "Groq provider timing model=%s attempt=%s status=failed duration_ms=%.2f kind=%s http_status=%s retry_after=%s error_type=%s error=%s",
                    model,model_attempt+1,elapsed,last_error.kind,last_error.status_code,last_error.retry_after,type(exc).__name__,str(exc)[:500],
                )
                if last_error.kind=="rate_limit":
                    _rate_limited(model,last_error)
                elif last_error.transient and last_error.kind!="invalid_json":
                    _failure(model,last_error)
                if last_error.kind=="authentication":break
                if last_error.kind=="rate_limit":break
                if not last_error.transient or model_attempt==1:break
                provider_retries+=1
        if last_error and last_error.kind=="authentication":break
    if last_error:raise last_error
    raise GroqProviderError("circuit_open",f"Groq circuit is open for configured models: {', '.join(selected_models)}",True)

def _complete_with_retry(request_builder, **options):
    """Compatibility wrapper; retry policy is centralized in `_complete`."""
    return _complete(request_builder,**options)


def json_completion(system: str, prompt: str, temperature: float = 0, *, models=None, deadline=None, timeout=None, maximum_tokens=None) -> tuple[dict[str, Any], dict] | None:
    def request(groq,model):
        options={
            "model":model,"temperature":temperature,"response_format":{"type":"json_object"},
            "max_completion_tokens":maximum_tokens or current_app.config["GROQ_JSON_MAX_COMPLETION_TOKENS"],
            "messages":[{"role":"system","content":system},{"role":"user","content":prompt}],
        }
        # The configured GPT-OSS models otherwise may expose reasoning text
        # before the JSON object, which Groq rejects under JSON mode.
        if model.startswith("openai/gpt-oss"):
            options["reasoning_format"]="hidden"
        return groq.chat.completions.create(**options)
    completed=_complete_with_retry(request,models=models,deadline=deadline,timeout=timeout)
    if not completed:return None
    response,model,provider_meta=completed
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Groq returned an empty JSON response")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Groq response must be a JSON object")
    return parsed, {**response_usage(response,model),**provider_meta}


def text_completion(system: str, prompt: str, maximum_tokens: int = 180, *, models=None, deadline=None, timeout=None, reasoning_effort=None) -> tuple[str, dict] | None:
    def request(groq,model):
        options={
            "model":model,"temperature":0.3,
            "max_completion_tokens":max(maximum_tokens,256) if model.startswith("openai/gpt-oss") else maximum_tokens,
            "messages":[{"role":"system","content":system},{"role":"user","content":prompt}],
        }
        if model.startswith("openai/gpt-oss"):
            options["reasoning_format"]="hidden"
            if reasoning_effort:
                options["reasoning_effort"]=reasoning_effort
        return groq.chat.completions.create(**options)

    completed=_complete_with_retry(request,models=models,deadline=deadline,timeout=timeout)
    if not completed:return None
    response,model,provider_meta=completed
    content = response.choices[0].message.content
    usage={**response_usage(response,model),**provider_meta}
    if not content:
        finish_reason=getattr(response.choices[0],"finish_reason",None)
        raise GroqProviderError(
            "empty_response",
            f"Groq returned empty text content model={model} "
            f"finish_reason={finish_reason} completion_tokens={usage['output_tokens']}",
            True,
        )
    return content,usage


# Backward-compatible import surface for old extensions. The implementation
# above is retired; every exported callable is delegated to the OpenAI layer.
from .ai_service import (
    AIProviderError as GroqProviderError,
    empty_usage,
    json_completion,
    merge_usage,
    text_completion,
)

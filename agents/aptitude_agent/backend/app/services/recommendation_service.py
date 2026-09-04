import json
import time
from flask import current_app
from ..utils.security import clean_text
from .ai_service import AIProviderError, text_completion
ProviderError = AIProviderError


def generate_recommendation(metrics, *, deadline=None, timeout=None):
    system=(
        "Write exactly 2 or 3 short, actionable aptitude-study sentences using only the supplied aggregate metrics. "
        "Keep each sentence under 18 words and the whole response under 55 words. "
        "For perfect performance, congratulate briefly and recommend harder practice. "
        "For zero correct answers, recommend fundamentals without discouraging language. "
        "Do not repeat every metric, add a long introduction, or use markdown."
    )
    # A recommendation is a small summarization task. Prefer the faster model,
    # then try the primary model once if the first response is empty or fails.
    models=list(dict.fromkeys([
        *current_app.config.get("OPENAI_FALLBACK_MODELS",()),
        current_app.config.get("OPENAI_MODEL"),
    ]))
    models=[model for model in models if model]
    last_error=None
    for attempt,model in enumerate(models[:2],start=1):
        if deadline is not None and time.monotonic()>=deadline:
            break
        try:
            result=text_completion(
                system,json.dumps(metrics),maximum_tokens=512,models=[model],
                deadline=deadline,timeout=timeout,reasoning_effort="low",
            )
            if not result:
                raise ProviderError(
                    "unavailable",f"OpenAI model {model} returned no recommendation",True,
                )
            text,usage=result
            recommendation=clean_text(text,600)
            if not recommendation:
                raise ProviderError(
                    "invalid_response",f"OpenAI model {model} returned an empty recommendation",True,
                )
            return recommendation,usage.get("model") or model,usage
        except ProviderError as exc:
            last_error=exc
            current_app.logger.warning(
                "Recommendation provider attempt failed model=%s attempt=%s/%s "
                "kind=%s status_code=%s retry_after=%s error=%s",
                model,attempt,min(2,len(models)),exc.kind,exc.status_code,
                exc.retry_after,str(exc)[:500],
            )
    if last_error:
        raise last_error
    raise ProviderError(
        "deadline_exceeded","Recommendation deadline expired before a provider call",True,
    )

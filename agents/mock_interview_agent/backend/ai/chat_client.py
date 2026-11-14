"""Low-level OpenAI chat and audio transcription transport."""

import json
import logging
import os

from openai import OpenAI
from services.ai_usage import current_usage_context, measure_request, record_provider_usage


OPENAI_REQUEST_TIMEOUT_SECONDS = float(
    os.environ.get("OPENAI_REQUEST_TIMEOUT_SECONDS", "20")
)
OPENAI_MAX_RETRIES = max(0, int(os.environ.get("OPENAI_MAX_RETRIES", "2")))
OPENAI_QUESTION_TIMEOUT_SECONDS = float(
    os.environ.get("OPENAI_QUESTION_TIMEOUT_SECONDS", "10")
)
client = None
logger = logging.getLogger(__name__)

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
EVAL_MODEL = os.environ.get("OPENAI_EVAL_MODEL", "gpt-5-mini").strip()
# GPT-5 models think before answering; at their default ("medium") grading five
# answers took longer than the 20-second request limit, every try timed out and
# learners only ever got the provisional report. "low" answers in seconds and
# is plenty for a correct/partial/wrong verdict.
EVAL_REASONING_EFFORT = os.environ.get("OPENAI_EVAL_REASONING_EFFORT", "low").strip().lower()
# One answer-grading call may take this long (all answers in one reply).
OPENAI_BATCH_EVALUATION_TIMEOUT_SECONDS = float(
    os.environ.get("OPENAI_BATCH_EVALUATION_TIMEOUT_SECONDS", "45")
)
TRANSCRIPTION_MODEL = os.environ.get(
    "OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"
).strip()
TRANSCRIPTION_PROMPTS = {
    "hr": "This is a spoken HR or behavioral interview answer.",
}
TECHNICAL_TRANSCRIPTION_TERMS = {
    "python": "Python, tuple, list, dictionary, decorator, generator, docstring, exception, endpoint, URL, URI, REST API, JSON",
    "javascript": "JavaScript, JSX, HTML, CSS, closure, promise, async, await, prototype, event loop, DOM",
    "react": "React, JavaScript, JSX, HTML, component, props, state, hook, useEffect, lifecycle, context, virtual DOM",
    "mysql": "MySQL, query, index, join, transaction, normalization, InnoDB, foreign key",
    "flask": "Flask, route, blueprint, request, response, decorator, WSGI, SQLAlchemy",
    "data science": "data science, DataFrame, NumPy, pandas, feature, distribution, correlation",
    "machine learning": "machine learning, model, training, inference, feature, overfitting, validation",
}

GENERAL_TECHNICAL_TRANSCRIPTION_TERMS = (
    "API, REST API, endpoint, URL, URI, HTTP, HTTPS, JSON, JavaScript, JSX, "
    "HTML, CSS, frontend, backend, database"
)


def validate_configured_models():
    """Fail fast when required OpenAI configuration is absent."""
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError("OPENAI_API_KEY must be configured at startup.")
    configured_models = {
        "OPENAI_MODEL": MODEL,
        "OPENAI_EVAL_MODEL": EVAL_MODEL,
        "OPENAI_TRANSCRIPTION_MODEL": TRANSCRIPTION_MODEL,
    }
    invalid = {
        setting: model
        for setting, model in configured_models.items()
        if not model
    }
    if invalid:
        details = ", ".join(
            f"{setting}={model!r}" for setting, model in invalid.items()
        )
        raise RuntimeError(
            "OpenAI model configuration is missing or invalid at startup: "
            f"{details}."
        )


def _get_client():
    """Create the SDK client only after configuration has been validated."""
    global client
    if client is None:
        validate_configured_models()
        client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            timeout=OPENAI_REQUEST_TIMEOUT_SECONDS,
            # The SDK retries transient network, timeout, 429 and 5xx errors
            # with backoff. Keep the retry policy explicit and configurable.
            max_retries=OPENAI_MAX_RETRIES,
        )
    return client


def _clean_prompt_context(value, max_characters):
    if value is None:
        return ""
    return " ".join(str(value).split())[:max_characters].strip()


def build_transcription_prompt(round_type, subject=None, question=None):
    """Build concise Whisper context without making another model request."""
    subject_text = _clean_prompt_context(subject, 150)
    question_text = _clean_prompt_context(question, 500)
    if not subject_text and not question_text:
        return None

    if round_type == "hr":
        parts = [TRANSCRIPTION_PROMPTS["hr"]]
        if question_text:
            parts.append(f"The candidate is answering: {question_text}")
        parts.append("Transcribe every spoken word, including the first word; preserve the candidate's wording and intended meaning.")
        return " ".join(parts)

    topic = subject_text or "a technical topic"
    parts = [f"Technical interview about {topic}."]
    if question_text:
        parts.append(f"The candidate is answering: {question_text}")
    parts.append("Transcribe every spoken word, including the first word. Use the correct spelling of technical terminology where applicable.")
    parts.append(f"Common technical terminology includes: {GENERAL_TECHNICAL_TRANSCRIPTION_TERMS}.")
    terms = TECHNICAL_TRANSCRIPTION_TERMS.get(subject_text.casefold())
    if terms:
        parts.append(f"Relevant terminology includes: {terms}.")
    return " ".join(parts)


def transcribe_audio(
    audio_file,
    filename="answer.webm",
    round_type="technical",
    subject=None,
    question=None,
    content_type=None,
):
    """Transcribe a recorded candidate answer using OpenAI."""
    resolved_content_type = (
        (content_type or "audio/webm").split(";", 1)[0].strip().lower()
        or "audio/webm"
    )
    request_options = {
        "file": (filename or "answer.webm", audio_file, resolved_content_type),
        "model": TRANSCRIPTION_MODEL,
        # No forced language: another language comes back in its own script
        # and the SkillDARA app asks the candidate to speak English.
        # gpt-4o-mini-transcribe returns the OpenAI transcription JSON object.
        "response_format": "json",
        "temperature": 0,
    }
    prompt = build_transcription_prompt(round_type, subject, question)
    if prompt:
        request_options["prompt"] = prompt
    transcription, response_time_ms = measure_request(
        lambda: _get_client().audio.transcriptions.create(**request_options)
    )
    _record_usage_safely(
        transcription, model_name=TRANSCRIPTION_MODEL,
        response_time_ms=response_time_ms, request_kind="audio_transcription",
    )
    text = transcription if isinstance(transcription, str) else transcription.text
    return (text or "").strip()


def chat(
    messages,
    json_mode=False,
    temperature=0.7,
    *,
    model_override=None,
    timeout=None,
    max_retries=None,
    request_kind="chat",
    provider="openai",
    reasoning_effort=None,
):
    model_name = (model_override or MODEL).strip()
    request_options = {
        "model": model_name,
        "messages": messages,
        "response_format": {"type": "json_object"} if json_mode else None,
    }
    # GPT-5-family chat models reject non-default temperatures.  The callers
    # still provide their difficulty-specific values for compatible models;
    # omitting the unsupported field lets GPT-5 Mini use its required default.
    if not model_name.casefold().startswith("gpt-5"):
        request_options["temperature"] = temperature
    elif reasoning_effort:
        request_options["reasoning_effort"] = reasoning_effort

    request_client = _get_client()
    if timeout is not None or max_retries is not None:
        request_client = request_client.with_options(
            timeout=timeout if timeout is not None else OPENAI_REQUEST_TIMEOUT_SECONDS,
            max_retries=max_retries if max_retries is not None else OPENAI_MAX_RETRIES,
        )
    response, response_time_ms = measure_request(
        lambda: request_client.chat.completions.create(**request_options)
    )
    _record_usage_safely(
        response, model_name=model_name, response_time_ms=response_time_ms,
        request_kind=request_kind,
    )
    if request_kind == "question_generation" and response_time_ms > 5000:
        usage = getattr(response, "usage", None)
        logger.warning(
            "Slow OpenAI question-generation completion: model=%s elapsed_ms=%s prompt_tokens=%s completion_tokens=%s",
            model_name,
            response_time_ms,
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            extra={
                "event": "slow_question_generation_completion",
                "model_name": model_name,
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "duration_ms": response_time_ms,
            },
        )
    return response.choices[0].message.content


def _record_usage_safely(response, *, model_name, response_time_ms, request_kind):
    """Usage telemetry must never turn a successful provider response into failure."""
    try:
        record_provider_usage(
            response,
            provider="openai",
            model_name=model_name,
            response_time_ms=response_time_ms,
        )
    except Exception:
        logger.exception(
            "Could not persist AI usage after successful provider response",
            extra={"event": "ai_usage_persistence_failed", "request_kind": request_kind,
                   "model_name": model_name, **current_usage_context()},
        )


def json_object(raw):
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("The AI response was not a JSON object.")
    return value


def score(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"The AI returned an invalid {field} score.") from None
    if not 0 <= number <= 10:
        raise ValueError(f"The AI returned an out-of-range {field} score.")
    return number

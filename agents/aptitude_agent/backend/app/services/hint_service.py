"""Generate short, answer-safe conceptual hints."""

import re
import time

from flask import current_app

from .ai_service import AIProviderError, empty_usage, json_completion, merge_usage
ProviderError = AIProviderError
from ..utils.security import clean_text


class HintUnavailable(Exception):
    """Raised when a safe conceptual hint cannot be produced."""

    def __init__(self, message, usage=None):
        super().__init__(message)
        self.usage = usage or {}


TOPIC_HINTS={
    "Percentages":"Translate each percentage into a part of the whole, then identify whether the problem asks for the part, rate, or base.",
    "Ratio & Proportion":"Keep corresponding quantities in the same order, simplify their relationship, and use an equivalent proportion to find the unknown.",
    "Time & Work":"Express each worker's contribution as a rate, combine the rates for shared work, then isolate the remaining work.",
    "Probability":"List the equally likely outcomes carefully, then compare the favorable outcomes with the complete outcome set.",
    "Average":"Use the relationship between total, count, and average, adjusting the total when a value is added, removed, or replaced.",
    "Number Series":"Compare consecutive terms and also inspect alternating positions for a repeating arithmetic or multiplicative pattern.",
    "Coding-Decoding":"Identify the transformation applied to each symbol or letter, then apply that same rule consistently to the target.",
    "Direction Sense":"Sketch each movement from a fixed starting point and track the final horizontal and vertical displacement separately.",
    "Syllogism":"Use only the stated relationships, testing whether the conclusion must follow rather than whether it merely seems possible.",
    "Synonyms":"Replace the target word in context and choose the option that preserves its meaning and tone most closely.",
    "Sentence Correction":"Check agreement, tense, parallel structure, and word placement, then choose the version that is both grammatical and clear.",
    "Fill in the Blanks":"Read the whole sentence for meaning and grammar before selecting the word that fits both context and structure.",
    "Pattern Recognition":"Separate the changing features and look for a consistent transformation in position, shape, count, or direction.",
    "Critical Thinking":"Distinguish facts from assumptions and choose the conclusion supported by the evidence without adding unstated claims.",
    "Data Analysis":"Identify the relevant values and units first, then compare or combine only the data needed by the question.",
    "Operating Systems":"Focus on which operating-system responsibility manages the resource or behavior described in the scenario.",
    "Networking Basics":"Trace how data moves between endpoints and match each described responsibility to the appropriate network concept.",
    "Database Basics":"Identify whether the scenario concerns storage, relationships, querying, consistency, or transactions before choosing the matching concept.",
    "Computer Architecture":"Map the described responsibility to the processor, memory, storage, or input/output component that performs it.",
    "Cybersecurity":"Identify the security goal first, then match the scenario to the control that protects confidentiality, integrity, or access.",
    "Programming Fundamentals":"Trace the program state one operation at a time, paying attention to control flow, scope, and data types.",
    "Data Structures":"Match the required access, ordering, and update behavior to the data structure designed to provide those operations.",
}


def _fallback_hint(question):
    return TOPIC_HINTS.get(
        question.topic,
        "Identify the core concept being tested, remove irrelevant details, and compare each option against the rule that concept requires.",
    )


def _validate_hint(value, correct_text=None):
    hint = clean_text(value, 240)
    words = hint.split()
    unsafe = (
        not hint
        or len(words) > 25
        or len(re.findall(r"[.!?]", hint)) > 1
        or bool(re.search(r"\d", hint))
        or (correct_text and correct_text.strip().lower() in hint.lower())
        or bool(
            re.search(
                r"\b(?:answer\s+is|correct\s+(?:answer|option|choice)|(?:option|choice)\s*[A-D])\b",
                hint,
                re.IGNORECASE,
            )
        )
    )
    if unsafe:
        raise HintUnavailable("OpenAI did not return an answer-safe conceptual hint")
    return hint


def generate_hint(question):
    if not current_app.config.get("OPENAI_API_KEY"):
        return _fallback_hint(question),{**empty_usage(),"model":"deterministic-fallback","fallback":True}
    total_started=time.perf_counter()
    accumulated_usage=empty_usage()
    small_models=list(current_app.config.get("OPENAI_FALLBACK_MODELS") or ())
    if not small_models:small_models=[current_app.config["OPENAI_MODEL"]]
    deadline=time.monotonic()+current_app.config["HINT_TIMEOUT_SECONDS"]
    try:
        last_error=None
        for attempt in range(1,3):
            result = json_completion(
                (
                    "Give exactly one conceptual hint sentence of no more than 25 words. "
                    "Name the underlying technique and gently suggest an approach. Never solve the problem, "
                    "state or imply an answer, mention options A/B/C/D, repeat numerical values, IP addresses, "
                    "slash notation, calculations, or reproduce an explanation. Return JSON only: {\"hint\":\"...\"}."
                ),
                (
                    f"Category: {question.category}\n"
                    f"Topic: {question.topic}\n"
                    f"Question: {question.question_text}\n"
                    f"Safety retry: {attempt}/2. Give a general method, not a value-specific clue."
                ),
                0,
                models=small_models,deadline=deadline,
                timeout=current_app.config["HINT_TIMEOUT_SECONDS"],
                maximum_tokens=current_app.config["HINT_MAX_COMPLETION_TOKENS"],
            )
            if result is None:
                break
            payload, usage = result
            accumulated_usage=merge_usage(accumulated_usage,usage)
            try:
                hint=_validate_hint(payload.get("hint"), question.options.get(question.correct_answer))
                current_app.logger.info(
                    "Hint generation timing topic=%s source=openai attempts=%s provider_wait_ms=%.2f total_ms=%.2f",
                    question.topic,attempt,accumulated_usage.get("provider_wait_ms",0),(time.perf_counter()-total_started)*1000,
                )
                return hint,accumulated_usage
            except HintUnavailable as exc:
                last_error=exc
                current_app.logger.warning(
                    "Conceptual hint safety validation failed attempt=%s/2 topic=%s reason=%s",
                    attempt, question.topic, str(exc),
                )
        if last_error:current_app.logger.warning("Conceptual hint safety attempts exhausted topic=%s",question.topic)
    except ProviderError as exc:
        current_app.logger.warning("Conceptual hint provider unavailable kind=%s; using deterministic fallback",exc.kind)
    except Exception as exc:
        current_app.logger.exception(
            "Conceptual hint generation failed error_type=%s error=%s",
            type(exc).__name__,str(exc)[:500],
        )
    fallback=_fallback_hint(question)
    usage={**accumulated_usage,"model":accumulated_usage.get("model") or "deterministic-fallback","fallback":True}
    current_app.logger.info(
        "Hint generation timing topic=%s source=deterministic_fallback attempts=%s provider_wait_ms=%.2f total_ms=%.2f",
        question.topic,usage.get("provider_attempt_count",0),usage.get("provider_wait_ms",0),(time.perf_counter()-total_started)*1000,
    )
    return fallback,usage

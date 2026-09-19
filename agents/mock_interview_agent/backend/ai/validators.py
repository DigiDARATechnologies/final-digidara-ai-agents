"""Question complexity validation, retry policy, and safe fallbacks."""

import json
import logging
import re
import unicodedata

from .chat_client import chat as default_chat


logger = logging.getLogger("llm_client")

QUESTION_WORD_LIMITS = {
    "beginner": 18,
    "intermediate": 30,
    "advanced": 45,
}
QUESTION_GENERATION_MAX_ATTEMPTS = 3
TOPIC_AREA_MAX_LENGTH = 100
QUESTION_COMPLEXITY_PATTERN = re.compile(
    r"\b(?:and|also|considering|especially|including)\b"
    r"|as well as"
    r"|taking into account"
    r"|in addition to",
    re.IGNORECASE,
)
QUESTION_INTERROGATIVE_PATTERN = re.compile(
    r"\b(?:what|why|how|when|where|which)\b",
    re.IGNORECASE,
)
QUESTION_WORD_PATTERN = re.compile(r"\b[\w]+(?:[-'][\w]+)*\b")
SAFE_QUESTION_TEMPLATES = {
    "beginner": (
        "What is one core concept in {subject}?",
        "What purpose does a common {subject} feature serve?",
        "How does one basic {subject} feature behave?",
    ),
    "intermediate": (
        "How would you diagnose a common {subject} failure?",
        "When would you choose one common {subject} approach over another?",
        "How would you apply a core {subject} concept in practice?",
    ),
    "advanced": (
        "What {subject} design trade-off would you evaluate first, and why?",
        "How would you diagnose a subtle reliability problem in {subject}?",
        "What {subject} failure mode deserves the most attention, and why?",
    ),
}
SAFE_HR_QUESTION_TEMPLATES = {
    "beginner": (
        "Why are you interested in this opportunity?",
        "How do you respond to constructive feedback?",
        "Tell me about a time you helped a teammate?",
    ),
    "intermediate": (
        "Tell me about a time you resolved a disagreement with a teammate?",
        "How have you prioritized competing responsibilities under a tight deadline?",
        "Describe a situation where you adapted your communication for someone else?",
    ),
    "advanced": (
        "Describe a difficult decision you made with incomplete information and explain your reasoning?",
        "Tell me about a time you took ownership of a serious failure?",
        "How did you influence an important decision without formal authority?",
    ),
}
SAFE_FOLLOWUP_QUESTIONS = {
    "technical": {
        "beginner": "Can you clarify the main concept in your answer?",
        "intermediate": "What reasoning supports the approach you described?",
        "advanced": "Which trade-off most influenced your answer, and why?",
    },
    "hr": {
        "beginner": "What did you do in that situation?",
        "intermediate": "What specific action did you take, and what happened next?",
        "advanced": "What was the most important factor behind your decision?",
    },
}

SKILL_FALLBACK_QUESTIONS = {
    "python fundamentals": ["What is a Python variable and why is it useful?", "How does a Python function organize reusable logic?"],
    "flask or django basics": ["What is a route in Flask or Django and why is it needed?", "How does a web framework handle an incoming request?"],
    "rest api basics": ["What does an HTTP GET request do in a REST API?", "Why would a REST API return a 404 status code?"],
    "sql and relational databases": ["What is a primary key in SQL and why is it important?", "What is the purpose of a SQL JOIN?"],
    "html, css and javascript basics": ["What is the purpose of an HTML element?", "What does CSS control on a web page?"],
    "git basics": ["What does git commit do?", "Why is git branch useful when developing software?"],
}


def _question_validation_errors(question, difficulty):
    """Return deterministic reasons any generated interview question is unsafe."""
    cleaned = (question or "").strip()
    errors = []
    if not cleaned:
        return ["empty question"]

    word_count = len(QUESTION_WORD_PATTERN.findall(cleaned))
    word_limit = QUESTION_WORD_LIMITS.get(difficulty, 45)
    if word_count > word_limit:
        errors.append(f"word count {word_count} exceeds {word_limit}")

    question_mark_count = cleaned.count("?")
    if question_mark_count != 1:
        errors.append(
            f"expected one question mark, found {question_mark_count}"
        )

    comma_count = cleaned.count(",")
    if comma_count > 2:
        errors.append(
            f"contains {comma_count} comma-separated qualifiers"
        )
    if ";" in cleaned:
        errors.append("contains a semicolon joining multiple clauses")

    complexity_markers = QUESTION_COMPLEXITY_PATTERN.findall(cleaned)
    if len(complexity_markers) > 2:
        errors.append(
            f"contains {len(complexity_markers)} complexity markers"
        )

    interrogatives = QUESTION_INTERROGATIVE_PATTERN.findall(cleaned)
    if len(interrogatives) > 2:
        errors.append(
            f"contains {len(interrogatives)} question clauses"
        )
    return errors


def _safe_fallback_question(subject, difficulty, asked_so_far, round_type="technical"):
    """Choose a short, non-repeated question if all OpenAI attempts are rejected."""
    if round_type == "hr":
        templates = SAFE_HR_QUESTION_TEMPLATES.get(
            difficulty,
            SAFE_HR_QUESTION_TEMPLATES["intermediate"],
        )
        asked_normalized = {
            question.strip().casefold()
            for question in asked_so_far
            if isinstance(question, str)
        }
        for candidate in templates:
            if (
                candidate.casefold() not in asked_normalized
                and not _question_validation_errors(candidate, difficulty)
            ):
                return candidate
        return "What experience has taught you the most about working with others?"

    subject_label = " ".join((subject or "").split())
    skill_key = subject_label.casefold()
    if len(QUESTION_WORD_PATTERN.findall(subject_label)) > 6:
        subject_label = "this subject"

    templates = SKILL_FALLBACK_QUESTIONS.get(skill_key) or SAFE_QUESTION_TEMPLATES.get(
        difficulty,
        SAFE_QUESTION_TEMPLATES["intermediate"],
    )
    asked_normalized = {
        question.strip().casefold()
        for question in asked_so_far
        if isinstance(question, str)
    }
    for template in templates:
        candidate = template.format(subject=subject_label)
        if (
            candidate.casefold() not in asked_normalized
            and not _question_validation_errors(candidate, difficulty)
        ):
            return candidate

    return "Explain one core concept from this subject and why it matters?"


def _safe_fallback_followup(round_type, difficulty):
    """Return a deterministic, valid follow-up when OpenAI exhausts its retries."""
    questions = SAFE_FOLLOWUP_QUESTIONS.get(
        round_type,
        SAFE_FOLLOWUP_QUESTIONS["technical"],
    )
    candidate = questions.get(difficulty, questions["intermediate"])
    if _question_validation_errors(candidate, difficulty):
        return "Can you clarify or expand on your last point?"
    return candidate


def _validated_question_with_retries(
    messages,
    difficulty,
    fallback_factory,
    question_type,
    temperature=0.7,
    allow_none=False,
    initial_candidate=None,
    chat_fn=default_chat,
):
    """Generate, validate, retry, and safely fall back for every question path."""
    previous_rejection = None
    has_initial_candidate = initial_candidate is not None

    for attempt in range(1, QUESTION_GENERATION_MAX_ATTEMPTS + 1):
        if attempt == 1 and has_initial_candidate:
            candidate = initial_candidate.strip()
        else:
            attempt_messages = [dict(message) for message in messages]
            if previous_rejection:
                attempt_messages[0]["content"] += (
                    " Your previous attempt violated the mandatory complexity "
                    "constraints and was rejected. Regenerate a substantially simpler "
                    "question focused on ONE idea, using no more than two tightly "
                    "connected clauses and remaining within the word limit. "
                    f"Rejected attempt: {previous_rejection!r}"
                )
            candidate = chat_fn(
                attempt_messages,
                temperature=temperature,
            ).strip()

        if allow_none and candidate.upper() == "NONE":
            return None

        errors = _question_validation_errors(candidate, difficulty)
        if not errors:
            if attempt > 1:
                logger.info(
                    "Question regeneration succeeded type=%s difficulty=%s attempts=%d",
                    question_type,
                    difficulty,
                    attempt,
                    extra={"event": "question_regeneration_succeeded"},
                )
            return candidate

        logger.warning(
            "Rejected generated question type=%s difficulty=%s "
            "attempt=%d/%d reasons=%s question=%r",
            question_type,
            difficulty,
            attempt,
            QUESTION_GENERATION_MAX_ATTEMPTS,
            errors,
            candidate,
            extra={"event": "generated_question_rejected"},
        )
        previous_rejection = candidate

    fallback = fallback_factory()
    logger.error(
        "Question generation exhausted retries; using fallback "
        "type=%s difficulty=%s attempts=%d fallback=%r",
        question_type,
        difficulty,
        QUESTION_GENERATION_MAX_ATTEMPTS,
        fallback,
        extra={"event": "question_generation_fallback_used"},
    )
    return fallback


def _normalized_topic_area(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("The AI returned an invalid topic_area.")
    normalized = " ".join(
        unicodedata.normalize("NFKC", value).split()
    ).strip().casefold()
    if len(normalized) > TOPIC_AREA_MAX_LENGTH:
        raise ValueError(
            f"The AI topic_area exceeds {TOPIC_AREA_MAX_LENGTH} characters."
        )
    if "?" in normalized or len(QUESTION_WORD_PATTERN.findall(normalized)) > 8:
        raise ValueError("The AI topic_area must be a concise label.")
    return normalized


def _question_payload(
    value, *, required_topic_area=None, excluded_topic_areas=()
):
    """Parse and normalize one structured main-question response."""
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("The AI response was not a JSON object.")

    topic_area = value.get("topic_area")
    question = value.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("The AI returned an invalid question.")

    topic_area = _normalized_topic_area(topic_area)
    question = " ".join(
        unicodedata.normalize("NFKC", question).split()
    ).strip()
    if required_topic_area is not None:
        required = _normalized_topic_area(required_topic_area)
        if topic_area != required:
            raise ValueError(
                f"The AI ignored the required topic_area {required!r}."
            )
    excluded = {
        _normalized_topic_area(area)
        for area in excluded_topic_areas
        if isinstance(area, str) and area.strip()
    }
    if topic_area in excluded:
        raise ValueError(
            f"The AI reused excluded topic_area {topic_area!r}."
        )
    return {"topic_area": topic_area, "question": question}


def _validated_question_payload_with_retries(
    messages,
    difficulty,
    fallback_factory,
    question_type,
    temperature=0.7,
    required_topic_area=None,
    excluded_topic_areas=(),
    chat_fn=default_chat,
    fail_fast_on_transport_error=False,
):
    """Generate and validate a structured main-question payload."""
    previous_rejection = None

    for attempt in range(1, QUESTION_GENERATION_MAX_ATTEMPTS + 1):
        attempt_messages = [dict(message) for message in messages]
        if previous_rejection:
            attempt_messages[0]["content"] += (
                " Your previous JSON response was rejected. Return a substantially "
                "simpler question focused on ONE idea, keep the topic_area concise, "
                "and obey the required JSON shape and difficulty word limit. "
                f"Rejected response: {previous_rejection!r}"
            )
        try:
            raw = chat_fn(
                attempt_messages,
                json_mode=True,
                temperature=temperature,
            )
        except Exception as exc:
            if not fail_fast_on_transport_error:
                raise
            fallback = _question_payload(
                fallback_factory(),
                required_topic_area=required_topic_area,
                excluded_topic_areas=excluded_topic_areas,
            )
            logger.exception(
                "Question generation transport failed; using immediate fallback "
                "type=%s difficulty=%s exception_type=%s",
                question_type,
                difficulty,
                type(exc).__name__,
                extra={"event": "question_generation_timeout_fallback"},
            )
            return fallback
        try:
            payload = _question_payload(
                raw,
                required_topic_area=required_topic_area,
                excluded_topic_areas=excluded_topic_areas,
            )
            errors = _question_validation_errors(
                payload["question"], difficulty
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            payload = None
            errors = [str(exc)]

        if not errors:
            if attempt > 1:
                logger.info(
                    "Structured question regeneration succeeded "
                    "type=%s difficulty=%s attempts=%d",
                    question_type,
                    difficulty,
                    attempt,
                    extra={"event": "question_regeneration_succeeded"},
                )
            return payload

        logger.warning(
            "Rejected structured question type=%s difficulty=%s "
            "attempt=%d/%d reasons=%s response=%r",
            question_type,
            difficulty,
            attempt,
            QUESTION_GENERATION_MAX_ATTEMPTS,
            errors,
            raw,
            extra={"event": "generated_question_rejected"},
        )
        previous_rejection = raw

    fallback = _question_payload(
        fallback_factory(),
        required_topic_area=required_topic_area,
        excluded_topic_areas=excluded_topic_areas,
    )
    logger.error(
        "Structured question generation exhausted retries; using fallback "
        "type=%s difficulty=%s attempts=%d fallback=%r",
        question_type,
        difficulty,
        QUESTION_GENERATION_MAX_ATTEMPTS,
        fallback,
        extra={"event": "question_generation_fallback_used"},
    )
    return fallback

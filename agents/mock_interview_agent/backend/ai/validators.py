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
BEGINNER_TECHNICAL_EXCLUSIONS = (
    re.compile(pattern, re.IGNORECASE) for pattern in (
        r"\b(?:principles|constraints)\s+of\s+(?:rest|restful|architecture)\b",
        r"\b(?:architectural|architecture)\s+(?:principles|constraints)\b",
        r"\b(?:settings\.py|manage\.py|project scaffolding|project structure)\b",
        r"\b(?:context managers?|with statement|decorators?|metaclasses?)\b",
        r"__(?:enter|exit)__",
        r"\b(?:list|name|enumerate)\s+(?:the\s+)?(?:main\s+)?(?:principles|constraints|patterns)\b",
    )
)
BEGINNER_TECHNICAL_EXCLUSIONS = tuple(BEGINNER_TECHNICAL_EXCLUSIONS)
INTERMEDIATE_CODE_TASK_PATTERN = re.compile(
    r"\bimplement\s+(?:a\s+|an\s+|the\s+)?(?:simple\s+|basic\s+)?(?:context manager|decorator|function|class|algorithm|"
    r"token[- ]based authentication|authentication|authorization|encryption)\b",
    re.IGNORECASE,
)
INTERMEDIATE_ADVANCED_TOPIC_PATTERN = re.compile(
    r"\b(?:optimiz(?:e|ation|ing)|optimis(?:e|ation|ing)|performance|"
    r"scalability|system design|architecture trade-?offs?)\b",
    re.IGNORECASE,
)
INTERMEDIATE_PRODUCTION_DEPLOYMENT_PATTERN = re.compile(
    r"\bdeploy(?:ing|ment)?\b.{0,80}\bproduction\b|\bproduction\s+deployment\b",
    re.IGNORECASE,
)
SAFE_QUESTION_TEMPLATES = {
    "beginner": (
        "What is one core concept in {subject}?",
        "What purpose does a common {subject} feature serve?",
        "How does one basic {subject} feature behave?",
    ),
    "intermediate": (
        "How would you troubleshoot a common issue in {subject}?",
        "When would you use a common {subject} pattern?",
        "How would you apply one {subject} concept in practice?",
    ),
    "advanced": (
        "Which trade-off matters most in {subject}, and why?",
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
SKILL_FALLBACK_QUESTIONS = {
    "python fundamentals": ["What is a Python variable?", "What does a Python function do?"],
    "flask or django basics": ["What is a route in Flask or Django?", "What does a web framework do with a request?"],
    "rest api basics": ["What does an HTTP GET request do in a REST API?", "Why would a REST API return a 404 status code?"],
    "sql and relational databases": ["What is a primary key in SQL and why is it important?", "What is the purpose of a SQL JOIN?"],
    "html, css and javascript basics": ["What is the purpose of an HTML element?", "What does CSS control on a web page?"],
    "git basics": ["What does git commit do?", "Why is git branch useful when developing software?"],
}
INTERMEDIATE_SKILL_FALLBACK_QUESTIONS = {
    "python application design": "When would you separate Python code into modules?",
    "flask or django configuration and routing": "How would you configure a route in Flask or Django?",
    "rest api design and authentication": "How does token authentication work in a typical REST API?",
    "sql joins and aggregations": "When would you use a SQL JOIN instead of separate queries?",
    "react or frontend integration": "How would a React component request data from a backend API?",
    "testing and debugging": "How would you diagnose a failing unit test?",
    "git workflows and deployment": "When would you use a feature branch in Git?",
}
ADVANCED_SKILL_FALLBACK_QUESTIONS = {
    "python performance and reliability": "How would you balance Python throughput against reliability during peak load?",
    "scalable backend architecture": "Which service boundary would you choose for scaling a busy backend, and why?",
    "api security and versioning": "How would you secure a public API while preserving compatibility for existing clients?",
    "database design and optimization": "Which database indexing trade-off matters most under heavy writes, and why?",
    "frontend-backend system design": "How would you deliver real-time updates while controlling backend load?",
    "ci/cd and cloud deployment": "How would you make cloud deployments safe to roll back after a failure?",
    "observability and incident debugging": "How would you isolate the cause of a latency spike across services?",
}
HR_AREA_FALLBACK_QUESTIONS = {
    "beginner": {
        "candidate introduction and background": "Tell me a little about yourself?",
        "motivation for the role": "Why are you interested in this role?",
        "strengths and areas for growth": "What is one strength you bring to a team?",
        "teamwork": "Tell me about a time you helped a teammate?",
        "receiving feedback": "How do you respond to constructive feedback?",
        "career goals": "What would you like to learn in this role?",
        "basic workplace communication": "How do you keep teammates informed about your work?",
        "adaptability": "How do you respond when plans change?",
        "taking responsibility": "Tell me about a time you owned a mistake?",
        "learning from experience": "What is one thing you learned from a recent project?",
    },
    "intermediate": {
        "teamwork and collaboration": "Tell me about a time you resolved a team disagreement?",
        "handling disagreement": "How did you handle a disagreement with a teammate?",
        "prioritization": "How did you prioritize tasks when deadlines competed?",
        "communication with different people": "When did you adapt your communication for a different audience?",
        "adapting to change": "How did you adjust when a project requirement changed?",
        "taking responsibility": "How did you respond after making a mistake on a project?",
        "role readiness": "How did you prepare for a responsibility you had not handled before?",
        "receiving feedback": "How did you apply constructive feedback to your work?",
        "failure and learning": "What did you learn from a project that did not go as planned?",
        "career development": "How have you worked toward a professional goal?",
    },
    "advanced": {
        "leadership": "How did you lead a team through resistance to a difficult change?",
        "ownership": "How did you take ownership when a project failed?",
        "resolving conflict": "How did you resolve a conflict between colleagues with opposing priorities?",
        "difficult workplace trade-offs": "How did you balance quality against a critical deadline?",
        "decision-making under uncertainty": "How did you make a consequential decision with incomplete information?",
        "influencing others": "How did you influence a decision without formal authority?",
        "handling failure and accountability": "How did you communicate and recover from a serious failure?",
        "strategic communication": "How did you communicate an unpopular decision to a team?",
        "ethics and judgment": "How did you resolve an ethical dilemma under pressure?",
        "mentoring and developing others": "How did you adapt your mentoring when someone resisted feedback?",
    },
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


def _beginner_technical_question_errors(question):
    """Reject known advanced question types even when their wording is short."""
    return ["requires knowledge beyond beginner technical fundamentals"] if any(
        pattern.search(question or "") for pattern in BEGINNER_TECHNICAL_EXCLUSIONS
    ) else []


def _intermediate_technical_question_errors(question):
    """Keep code implementation and performance design in the advanced tier."""
    errors = []
    if INTERMEDIATE_CODE_TASK_PATTERN.search(question or ""):
        errors.append("asks for implementation rather than verbal reasoning")
    if INTERMEDIATE_ADVANCED_TOPIC_PATTERN.search(question or ""):
        errors.append("requires advanced performance or architecture reasoning")
    if INTERMEDIATE_PRODUCTION_DEPLOYMENT_PATTERN.search(question or ""):
        errors.append("requires production deployment planning")
    return errors


def _safe_fallback_question(subject, difficulty, asked_so_far, round_type="technical"):
    """Choose a short, non-repeated question if all OpenAI attempts are rejected."""
    if round_type == "hr":
        area_question = HR_AREA_FALLBACK_QUESTIONS.get(difficulty, {}).get(
            str(subject or "").strip().casefold()
        )
        templates = ((area_question,) if area_question else ()) + SAFE_HR_QUESTION_TEMPLATES.get(
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
    # Parenthetical examples are useful in prompts but make fallback wording
    # noisy and can be truncated mid-example.
    subject_label = re.sub(r"\s*\([^)]*\)", "", subject_label).strip()
    if len(QUESTION_WORD_PATTERN.findall(subject_label)) > 6:
        # Keep a short recognizable skill label in deterministic fallbacks;
        # replacing it with "this subject" loses role scoping and calibration.
        words = subject_label.split()[:6]
        while words and words[-1].casefold() in {"and", "or", "with", "of", "the"}:
            words.pop()
        subject_label = " ".join(words)

    level_specific = (
        INTERMEDIATE_SKILL_FALLBACK_QUESTIONS if difficulty == "intermediate"
        else ADVANCED_SKILL_FALLBACK_QUESTIONS if difficulty == "advanced"
        else {}
    ).get(skill_key)
    generic_templates = SAFE_QUESTION_TEMPLATES.get(
        difficulty, SAFE_QUESTION_TEMPLATES["intermediate"]
    )
    if level_specific:
        templates = (level_specific,) + generic_templates
    elif difficulty == "beginner" and skill_key in SKILL_FALLBACK_QUESTIONS:
        templates = tuple(SKILL_FALLBACK_QUESTIONS[skill_key]) + generic_templates
    else:
        templates = generic_templates
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

    return {
        "beginner": "What is one core concept in this subject?",
        "intermediate": "How would you apply one practical concept in this subject?",
        "advanced": "Which trade-off matters most in this subject, and why?",
    }.get(difficulty, "How would you apply one practical concept in this subject?")


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
                "For HR, use one sentence and exactly one question mark, without a second "
                "action/result question. "
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
            errors = _question_validation_errors(payload["question"], difficulty)
            if question_type == "technical_main" and difficulty == "beginner":
                errors.extend(_beginner_technical_question_errors(payload["question"]))
            if question_type == "technical_main" and difficulty == "intermediate":
                errors.extend(_intermediate_technical_question_errors(payload["question"]))
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

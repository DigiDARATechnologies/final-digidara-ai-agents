"""Planned interview question generation."""

import json
import logging
import os
import random
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextvars import copy_context
from functools import partial

from openai import OpenAI
from services.question_history import question_hash


from .validators import (
    QUESTION_WORD_LIMITS,
    _beginner_technical_question_errors,
    _intermediate_technical_question_errors,
    _safe_fallback_question,
    _question_validation_errors,
    _validated_question_payload_with_retries,
)

logger = logging.getLogger(__name__)

# OpenAI's hosted web-search filters require a Responses model that supports
# web-search controls; gpt-4o-mini rejects ``filters.allowed_domains``.
DEFAULT_OPENAI_SEARCH_MODEL = "gpt-5.5"
# Live search runs after the interview plan has been saved by a background
# worker, so it may wait longer without delaying the student-facing request.
DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS = 45
# Responses counts reasoning tokens and visible answer tokens against this
# shared cap.  Leave sufficient headroom for a web-search tool round trip and
# the final JSON question list.
DEFAULT_WEB_SEARCH_MAX_OUTPUT_TOKENS = 8192
search_client = None
ROLE_SKILL_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
_role_skill_cache = {}

TECHNICAL_LEVEL_GUIDANCE = {
    "beginner": (
        "BEGINNER / FRESHER: Ask exactly one everyday foundational concept in plain language. "
        "The answer must fit a one- or two-sentence definition, purpose, or basic use. "
        "Good types: 'What is a variable?', 'What does git status do?', "
        "'What is CSS used for?', or a simple difference between two everyday concepts. "
        "Do not ask to name or list multiple architectural principles or constraints; "
        "'What are the main principles of RESTful architecture?' is NOT beginner. "
        "Do not ask about framework configuration files or project structure conventions; "
        "'What is settings.py for in Django?' is NOT beginner. "
        "Do not ask about language internals or magic methods, context managers, the Python "
        "with statement, __enter__/__exit__, decorators, or metaclasses; "
        "'What is the purpose of the with statement?' is NOT beginner. "
        "Avoid architecture, optimization, security design, deployment, and multi-step scenarios. "
        "Keep one question under 18 words; if an assigned skill is broad, test its simplest user-facing idea."
    ),
    "intermediate": (
        "INTERMEDIATE: Assume basic definitions are known. Ask one practical concept or a short "
        "application/debugging scenario. Named principles and patterns such as REST constraints, "
        "MVC, and ORM concepts, basic framework configuration, and common language features such "
        "as context managers, decorators, and list comprehensions are appropriate. "
        "Ask how or why a common choice works, or how the candidate would approach a familiar "
        "problem. Framework configuration means ordinary settings and routing, not production "
        "deployment planning. Do not require senior architecture, obscure internals, or complex multi-step "
        "trade-offs. Keep one focused question under 30 words."
    ),
    "advanced": (
        "ADVANCED: Test informed judgment through architecture trade-offs, performance and "
        "optimization, security considerations, component-level system design, reliability, "
        "or edge cases. A realistic multi-step scenario is appropriate when its parts form one "
        "coherent decision. Ask the candidate to justify a choice and its consequences, not to "
        "recite definitions. Keep one focused question under 45 words."
    ),
}

HR_LEVEL_GUIDANCE = {
    "beginner": (
        "BEGINNER HR: Ask one simple conversational question about introduction, motivation, "
        "strengths, goals, basic teamwork, feedback, or an everyday situation. "
        "Examples: 'Tell me about yourself?' or 'How do you respond to feedback?' "
        "Accept school, projects, volunteering, and daily life as experience. "
        "Do not demand formal employment, leadership, conflict mediation, ambiguous trade-offs, "
        "or a structured STAR story. Keep it under 18 words."
    ),
    "intermediate": (
        "INTERMEDIATE HR: Ask one focused behavioral or situational question inviting a concrete "
        "example with situation, personal action, and result or learning. Familiar teamwork, "
        "prioritization, communication, adaptability, and manageable conflict fit this level. "
        "Do not require executive leadership or highly ambiguous judgment. Keep it under 30 words."
    ),
    "advanced": (
        "ADVANCED HR: Ask one realistic behavioral or ambiguous scenario about leadership, "
        "complex conflict resolution, accountability, influencing without authority, or a "
        "difficult ethical or strategic trade-off. Invite the candidate to explain their judgment, "
        "actions, and consequences. Keep it focused and under 45 words."
    ),
}


def _technical_skill_calibration(skill_area, difficulty):
    """Return a compact, skill-specific calibration instruction for a slot."""
    skill = str(skill_area or "").casefold()
    if difficulty == "beginner":
        examples = "define one everyday term, purpose, or basic command"
    elif difficulty == "intermediate":
        examples = "explain a named feature/pattern or a practical troubleshooting scenario"
    else:
        examples = "reason through a trade-off, failure mode, security/performance risk, or design decision"

    if any(token in skill for token in ("python", "pandas", "numpy")):
        focus = "stay within Python/data-library concepts named by this skill"
    elif any(token in skill for token in ("sql", "database", "data model")):
        focus = "stay within queries, joins, modeling, or database behavior named by this skill"
    elif any(token in skill for token in ("statistics", "forecast", "experimental")):
        focus = "stay within statistical reasoning, experiments, or forecasting named by this skill"
    elif any(token in skill for token in ("excel", "dashboard", "visualization", "power bi", "tableau")):
        focus = "stay within the spreadsheet, dashboard, or visualization practice named by this skill"
    elif any(token in skill for token in ("flask", "django", "rest", "api", "frontend", "react", "git", "test")):
        focus = "stay within the framework, API, frontend, version-control, or testing practice named by this skill"
    elif any(token in skill for token in ("security", "iam", "cloud", "encryption", "network", "incident", "compliance", "container")):
        focus = "stay within the cloud/security subject named by this skill"
    else:
        focus = "stay tightly within the exact skill label"
    return f"For '{skill_area}', {examples}; {focus}."

# These are deliberately role-level competencies, rather than the old
# course/subject topic catalogue.  They provide predictable, reviewed
# coverage for the roles offered in the UI while custom roles are inferred.
PRESET_ROLE_SKILLS = {
    "python fullstack developer": {
        "beginner": ["Python fundamentals", "Flask or Django basics", "REST API basics", "SQL and relational databases", "HTML, CSS and JavaScript basics", "Git basics"],
        "intermediate": ["Python application design", "Flask or Django configuration and routing", "REST API design and authentication", "SQL joins and aggregations", "React or frontend integration", "testing and debugging", "Git workflows and deployment"],
        "advanced": ["Python performance and reliability", "scalable backend architecture", "API security and versioning", "database design and optimization", "frontend-backend system design", "CI/CD and cloud deployment", "observability and incident debugging"],
    },
    "data analyst": {
        "beginner": ["Python fundamentals", "Pandas and DataFrames", "NumPy basics", "Statistics fundamentals", "Data visualization basics", "Excel basics", "SQL basics"],
        "intermediate": ["Python functions and data structures", "Pandas data cleaning and joins", "NumPy array operations", "statistical analysis", "Power BI or Tableau dashboards", "Excel analysis and lookup functions", "SQL joins and aggregations"],
        "advanced": ["Python performance and automation", "Pandas performance and scalable data processing", "NumPy vectorization", "experimental design and forecasting", "dashboard performance and metric design", "Excel model auditing", "advanced SQL optimization"],
    },
    "data scientist": {
        "beginner": ["Python fundamentals", "Pandas and DataFrames", "NumPy basics", "Statistics fundamentals", "Data visualization basics", "Excel basics", "SQL basics"],
        "intermediate": ["Python functions and object-oriented programming", "Pandas data cleaning and joins", "NumPy array operations", "Statistical inference and hypothesis testing", "data visualization and storytelling", "Excel analysis and lookup functions", "SQL joins and aggregations"],
        "advanced": ["Python performance and packaging", "Pandas performance and scalable data processing", "NumPy vectorization", "experimental design and statistical modeling", "visualization design and metric communication", "Excel model auditing", "SQL query optimization and data modeling"],
    },
    "digital marketing executive": {
        "beginner": ["marketing funnel basics", "audience research", "content planning", "SEO fundamentals", "social media basics", "campaign metrics"],
        "intermediate": ["SEO and keyword strategy", "Google Ads campaign management", "social media campaign optimization", "content marketing", "email marketing automation", "conversion tracking", "performance reporting"],
        "advanced": ["integrated campaign strategy", "budget allocation and ROI", "attribution analysis", "audience segmentation", "A/B testing and optimization", "brand safety", "marketing analytics leadership"],
    },
    "ai engineer": {
        "beginner": ["Python for AI", "machine learning fundamentals", "data preparation", "model evaluation basics", "LLM and prompt basics", "API fundamentals"],
        "intermediate": ["machine learning pipelines", "LLM prompting and evaluation", "RAG systems", "embeddings and vector databases", "model deployment APIs", "testing and monitoring AI systems", "responsible AI"],
        "advanced": ["production ML system design", "LLM architecture and orchestration", "RAG quality and retrieval optimization", "model evaluation and observability", "scalable inference", "AI safety and governance", "cost and latency trade-offs"],
    },
}

MASTER_FAQ_PROMPT = """You curate real, frequently asked interview questions. Never invent questions.

CONTEXT:
Role: {role}
Difficulty: {difficulty}
Interview Round: {round}
Number of questions needed: {count}

{search_context}

RULES:
{difficulty_guidance}
1. Return only questions commonly asked in real {role} interviews at {difficulty}, based on the search results.
2. Keep source wording close; do not invent or creatively rephrase.
3. Exclude duplicates, vague text, ads, navigation, and headers; prioritize repeated patterns.
4. If insufficient questions exist, return fewer; never fabricate filler.

OUTPUT: Return ONLY valid JSON, no markdown:
[
  {{"question":"exact real question text","role":"{role}","difficulty":"{difficulty}","round":"{round}","frequency_score":1,"source":"source pattern"}}
]
"""


def _web_search_timeout_seconds():
    """Return a positive timeout for the background live-search path."""
    try:
        value = float(os.environ.get(
            "WEB_SEARCH_TIMEOUT_SECONDS", DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS,
        ))
    except ValueError:
        value = DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_WEB_SEARCH_TIMEOUT_SECONDS


def _web_search_max_output_tokens():
    """Return the output-token cap used only by the background search call."""
    try:
        value = int(os.environ.get(
            "WEB_SEARCH_MAX_OUTPUT_TOKENS", DEFAULT_WEB_SEARCH_MAX_OUTPUT_TOKENS,
        ))
    except ValueError:
        value = DEFAULT_WEB_SEARCH_MAX_OUTPUT_TOKENS
    return value if value > 0 else DEFAULT_WEB_SEARCH_MAX_OUTPUT_TOKENS


def _question_generation_timeout_seconds():
    """Return the end-to-end deadline for one initial-plan question slot."""
    try:
        value = float(os.environ.get("OPENAI_QUESTION_TIMEOUT_SECONDS", "10"))
    except ValueError:
        value = 10.0
    return value if value > 0 else 10.0


def _get_search_client():
    """Create a background-search client without changing normal chat clients."""
    global search_client
    if search_client is None:
        search_client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            max_retries=0,
            timeout=_web_search_timeout_seconds(),
        )
    return search_client


def _normalize_role_skill_key(role_or_topic, difficulty):
    role = " ".join(str(role_or_topic or "").split()).casefold()
    return role, str(difficulty or "intermediate").casefold()


def _parse_skill_list(raw):
    """Parse and validate the compact JSON skill list returned by the LLM."""
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    value = json.loads(text)
    if not isinstance(value, list):
        raise ValueError("Role skill inference must return a JSON array.")
    skills, seen = [], set()
    for item in value:
        skill = " ".join(str(item).split()).strip()
        key = skill.casefold()
        if skill and len(skill) <= 100 and key not in seen:
            seen.add(key)
            skills.append(skill)
    if not 6 <= len(skills) <= 10:
        raise ValueError("Role skill inference must return 6 to 10 unique skills.")
    return skills


def infer_role_skills(role_or_topic, difficulty, *, chat_fn=None):
    """Return cached, role-specific interview skills for a technical session.

    Preset roles never make an LLM request. Custom role results live in an
    in-process cache for 30 days, so a role is inferred only on its first use
    by this app process.
    """
    role, level = _normalize_role_skill_key(role_or_topic, difficulty)
    preset = PRESET_ROLE_SKILLS.get(role, {}).get(level)
    if preset:
        logger.info(
            "Role skill cache hit (preset): role=%r difficulty=%s",
            role_or_topic,
            difficulty,
            extra={"event": "role_skills_cache_hit", "cache_source": "preset"},
        )
        return list(preset)

    cache_key = (role, level)
    cached = _role_skill_cache.get(cache_key)
    if cached and cached[0] > time.time():
        logger.info(
            "Role skill cache hit (memory): role=%r difficulty=%s",
            role_or_topic,
            difficulty,
            extra={"event": "role_skills_cache_hit", "cache_source": "memory"},
        )
        return list(cached[1])
    if not role:
        raise ValueError("A role or custom topic is required to infer skills.")
    if chat_fn is None:
        from .chat_client import chat as chat_fn

    logger.info(
        "Role skill cache miss: role=%r difficulty=%s",
        role_or_topic,
        difficulty,
        extra={"event": "role_skills_cache_miss"},
    )

    prompt = (
        "You are a technical interviewer. For the job role "
        f"'{role_or_topic}' at '{difficulty}' level, list the 6-10 most important, "
        "specific skill areas or subtopics a real interviewer would test for this role. "
        "Be concrete; use skills such as Python fundamentals, REST API design, SQL/databases, "
        "or deployment basics rather than vague categories. Return ONLY a JSON array of short "
        "skill area strings, with no explanation."
    )
    skills = _parse_skill_list(chat_fn([{"role": "system", "content": prompt}]))
    _role_skill_cache[cache_key] = (time.time() + ROLE_SKILL_CACHE_TTL_SECONDS, skills)
    logger.info("Inferred role skills for %r at %s: %s", role_or_topic, difficulty, skills,
                extra={"event": "role_skills_inferred"})
    return list(skills)


def _search_response(prompt, model):
    return _get_search_client().responses.create(
        model=model,
        tools=[{
            "type": "web_search",
            "filters": {
                "allowed_domains": ["glassdoor.com", "geeksforgeeks.org"],
            },
        }],
        tool_choice="auto",
        input=prompt,
        max_output_tokens=_web_search_max_output_tokens(),
        # Set it per request too, so the bounded timeout remains explicit
        # even if a caller reuses this client in the future.
        timeout=_web_search_timeout_seconds(),
    )


def fetch_live_real_questions(
    role, difficulty, round_, count=5, already_asked_hashes=None,
    role_skills=None,
):
    """Use OpenAI web search to curate source-backed FAQ interview questions."""
    prompt = MASTER_FAQ_PROMPT.format(
        role=role,
        difficulty=difficulty,
        round=round_,
        count=count,
        difficulty_guidance=(
            TECHNICAL_LEVEL_GUIDANCE if round_ == "technical" else HR_LEVEL_GUIDANCE
        ).get(difficulty, ""),
        search_context=(
            f"Search for real, frequently-asked '{role}' interview "
            f"questions at '{difficulty}' level on Glassdoor and "
            f"GeeksforGeeks. Cover these role skill areas across the results: "
            f"{', '.join((role_skills or [])[:3]) or 'the role-specific skills in the role title'}. "
            "Extract genuine questions only, close to their original phrasing."
        ),
    )
    model = os.environ.get("OPENAI_SEARCH_MODEL", DEFAULT_OPENAI_SEARCH_MODEL).strip()
    model = model or DEFAULT_OPENAI_SEARCH_MODEL
    api_key = os.environ.get("OPENAI_API_KEY", "")
    timeout_seconds = _web_search_timeout_seconds()
    max_output_tokens = _web_search_max_output_tokens()
    logger.info(
        "Live web search started: model=%s timeout_seconds=%s max_output_tokens=%s max_retries=0 api_key=%s api_key_length=%s role=%r difficulty=%s round=%s count=%s",
        model,
        timeout_seconds,
        max_output_tokens,
        "present" if api_key.strip() else "missing",
        len(api_key),
        role,
        difficulty,
        round_,
        count,
        extra={"event": "live_question_search_started"},
    )
    started = time.perf_counter()
    try:
        response = _search_response(prompt, model)
    except Exception as exc:
        elapsed_seconds = time.perf_counter() - started
        logger.exception(
            "Web search failed after %.2fs; falling back to AI-generated questions: model=%s exception_type=%s message=%s",
            elapsed_seconds,
            model,
            type(exc).__name__,
            str(exc),
            extra={"event": "live_question_search_exception"},
        )
        return []
    raw_text = getattr(response, "output_text", None)
    raw_response = (
        response.model_dump(mode="json")
        if hasattr(response, "model_dump")
        else repr(response)
    )
    output_items = [
        {
            "type": getattr(item, "type", None),
            "status": getattr(item, "status", None),
        }
        for item in (getattr(response, "output", None) or [])
    ]
    usage = getattr(response, "usage", None)
    logger.info(
        "OpenAI Responses web search full response=%r",
        raw_response,
        extra={"event": "live_question_search_full_response"},
    )
    logger.info(
        "OpenAI Responses web search output items=%s usage=%r output_text=%r",
        output_items,
        usage,
        raw_text,
        extra={"event": "live_question_search_response_diagnostics"},
    )
    try:
        value = json.loads(raw_text)
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "Web search failed after %.2fs because question curation JSON was invalid; falling back to AI-generated questions: exception_type=%s message=%s raw_output=%r",
            time.perf_counter() - started,
            type(exc).__name__,
            str(exc),
            str(raw_text)[:1000],
            extra={"event": "live_question_curation_failed"},
        )
        return []
    questions, seen = [], set()
    already_asked_hashes = already_asked_hashes or set()
    for item in value if isinstance(value, list) else []:
        question = " ".join(str(item.get("question", "")).split()).strip()
        key = question.casefold()
        if question and question.endswith("?") and key not in seen and question_hash(question) not in already_asked_hashes and not (
            round_ == "technical" and (
                _question_validation_errors(question, difficulty)
                or (difficulty == "beginner" and _beginner_technical_question_errors(question))
                or (difficulty == "intermediate" and _intermediate_technical_question_errors(question))
            )
        ):
            seen.add(key)
            questions.append({**item, "question": question, "source": "real"})
        if len(questions) >= count:
            break
    logger.info(
        "Web search finished in %.2fs with %s usable real questions from %s parsed items",
        time.perf_counter() - started,
        len(questions),
        len(value) if isinstance(value, list) else 0,
        extra={"event": "live_question_search_result_count"},
    )
    return questions


def build_interview_questions(
    role, difficulty, round_, total_count, *, chat_fn, generate_ai_question,
    rng, already_asked_hashes=None, role_skills=None,
    initial_asked_context=None,
):
    """Synchronously create a complete AI-only plan for immediate serving.

    Source-backed questions are fetched separately in the background after the
    interview is persisted, so a slow web-search request can never delay the
    student's first question.
    """
    already_asked_hashes = set(already_asked_hashes or ())
    initial_asked_context = list(initial_asked_context or ())
    skill_slots = (
        "Assign the output items to these skills in this exact order: "
        + " ".join(
            f"Item {index + 1}: {role_skills[index % len(role_skills)]}. "
            f"{_technical_skill_calibration(role_skills[index % len(role_skills)], difficulty)}"
            for index in range(total_count)
        )
        if round_ == "technical" and role_skills else ""
    )
    # Batch mode keeps one model request for the complete initial plan.  Each
    # returned item is still persisted as an individual question row, so the
    # student-facing sequence and database shape remain unchanged.
    level_guidance = (
        TECHNICAL_LEVEL_GUIDANCE if round_ == "technical" else HR_LEVEL_GUIDANCE
    ).get(difficulty, "")
    batch_prompt = (
        f"Generate exactly {total_count} distinct {difficulty}-level {round_} interview questions for role/topic '{role}'. "
        f"{level_guidance} {skill_slots} "
        f"Cover these skill areas in order, cycling if needed: {role_skills or ['core concepts']}. "
        "Ask one concise question per item. Technical answers must be verbal; never require writing code. "
        f"Do not repeat these previous questions: {initial_asked_context}. "
        "Return ONLY valid JSON as an array of objects in this exact shape: "
        '{"questions":[{"topic_area":"concise lowercase area","question":"question text"}]}.'
    )
    try:
        raw_batch = chat_fn(
            [{"role": "system", "content": batch_prompt}],
            json_mode=True,
            temperature=0.7,
            request_kind="question_generation",
            timeout=_question_generation_timeout_seconds(),
            max_retries=0,
        )
        parsed_batch = json.loads(raw_batch)
        if isinstance(parsed_batch, dict):
            parsed_batch = parsed_batch.get("questions", [])
        if not isinstance(parsed_batch, list):
            raise ValueError("Batch question response was not an array")
    except Exception:
        parsed_batch = []

    plan = []
    seen = set(already_asked_hashes)
    for index in range(total_count):
        assigned_skill = role_skills[index % len(role_skills)] if role_skills else None
        item = parsed_batch[index] if index < len(parsed_batch) and isinstance(parsed_batch[index], dict) else {}
        question = " ".join(str(item.get("question", "")).split()).strip()
        returned_topic = " ".join(str(item.get("topic_area", "")).split()).casefold()
        required_topic = " ".join(str(assigned_skill or "").split()).casefold()
        if not question or not question.endswith("?") or question_hash(question) in seen or (
            (round_ == "technical" and role_skills and returned_topic != required_topic)
            or
            (_question_validation_errors(question, difficulty)
             or (round_ == "technical" and difficulty == "beginner"
                 and _beginner_technical_question_errors(question))
             or (round_ == "technical" and difficulty == "intermediate"
                 and _intermediate_technical_question_errors(question)))
        ):
            question = _safe_fallback_question(
                assigned_skill or role,
                difficulty,
                initial_asked_context + [p["question"] for p in plan],
            )
        seen.add(question_hash(question))
        plan.append({
            "question": question,
            "topic_area": assigned_skill or item.get("topic_area") or "core concepts",
            "source": "ai_generated",
            "assigned_skill_area": assigned_skill,
        })
    rng.shuffle(plan)
    logger.info("Built batched AI interview plan with one LLM call: questions=%s", len(plan), extra={"event": "interview_question_plan_built"})
    return plan

    # Legacy concurrent per-question implementation retained below for
    # reference and compatibility with callers that bypass batch mode.
    assignments = [
        (
            index,
            role_skills[index % len(role_skills)] if role_skills else None,
        )
        for index in range(total_count)
    ]
    attempts = {index: 0 for index, _ in assignments}

    accepted = {}
    seen_hashes = set(already_asked_hashes)
    future_metadata = {}
    question_timeout_seconds = _question_generation_timeout_seconds()
    plan_started_at = time.perf_counter()
    plan_deadline_at = plan_started_at + question_timeout_seconds

    def submit(executor, index, skill_area, asked_context):
        """Queue one isolated attempt on the executor used by the whole plan."""
        context = copy_context()
        future = executor.submit(
            context.run,
            generate_ai_question,
            list(asked_context),
            skill_area,
        )
        started_at = time.perf_counter()
        future_metadata[future] = (index, skill_area, started_at)

    def fallback_for_timeout(index, skill_area):
        fallback_subject = skill_area or role
        return {
            "topic_area": skill_area or "core concepts",
            "question": _safe_fallback_question(
                fallback_subject,
                difficulty,
                initial_asked_context + [
                    item["question"] for _, item in sorted(accepted.items())
                ],
            ),
        }

    # Keep one executor alive for the entire plan. A collision is detected as
    # soon as that slot completes, so its retry starts while slower initial
    # slots are still in flight instead of after the batch is fully drained.
    executor = ThreadPoolExecutor(
        max_workers=max(1, total_count),
        thread_name_prefix="initial-question",
    )
    try:
        for index, skill_area in assignments:
            submit(executor, index, skill_area, initial_asked_context)

        while future_metadata:
            now = time.perf_counter()
            # A retry shares the same plan deadline as its original attempt.
            # Otherwise, a collision discovered near the end of the initial
            # batch could add another full timeout to /api/start_interview.
            next_deadline_seconds = max(0.0, plan_deadline_at - now)
            completed, _ = wait(
                future_metadata,
                timeout=next_deadline_seconds,
                return_when=FIRST_COMPLETED,
            )
            now = time.perf_counter()
            timed_out = [
                future
                for future, (_, _, started_at) in future_metadata.items()
                if not future.done() and now >= plan_deadline_at
            ]
            for future in timed_out:
                index, skill_area, started_at = future_metadata.pop(future)
                future.cancel()
                fallback = fallback_for_timeout(index, skill_area)
                accepted[index] = fallback
                seen_hashes.add(question_hash(fallback["question"]))
                logger.warning(
                    "Question %s exceeded the %.1fs plan deadline; using a safe fallback without retrying",
                    index + 1,
                    question_timeout_seconds,
                    extra={
                        "event": "question_generation_deadline_fallback",
                        "question_number": index + 1,
                        "skill_area": skill_area,
                        "elapsed_seconds": round(time.perf_counter() - plan_started_at, 4),
                    },
                )
            for future in completed:
                if future not in future_metadata:
                    continue
                index, skill_area, started_at = future_metadata.pop(future)
                generated = future.result()
                attempts[index] += 1
                elapsed_seconds = time.perf_counter() - started_at
                logger.info(
                    "Generated initial interview-plan question %s in %.2fs (attempt=%s)",
                    index + 1,
                    elapsed_seconds,
                    attempts[index],
                    extra={
                        "event": "initial_question_generation_completed",
                        "question_number": index + 1,
                        "skill_area": skill_area,
                        "elapsed_seconds": round(elapsed_seconds, 4),
                        "collision_retry_occurred": attempts[index] > 1,
                        "attempts": attempts[index],
                    },
                )
                generated_hash = question_hash(generated["question"])
                if generated_hash not in seen_hashes:
                    accepted[index] = generated
                    seen_hashes.add(generated_hash)
                    continue

                if attempts[index] < 3:
                    logger.warning(
                        "Generated question %s collided; retrying without waiting for the initial batch",
                        index + 1,
                        extra={
                            "event": "historical_question_collision",
                            "question_number": index + 1,
                        },
                    )
                    retry_context = initial_asked_context + [
                        accepted_indexed["question"]
                        for _, accepted_indexed in sorted(accepted.items())
                    ]
                    submit(executor, index, skill_area, retry_context)
                    continue

                accepted[index] = generated
                seen_hashes.add(generated_hash)
                logger.warning(
                    "Allowed repeated question %s after two regeneration attempts",
                    index + 1,
                    extra={
                        "event": "historical_question_collision_allowed",
                        "question_number": index + 1,
                    },
                )
    finally:
        # Network calls already in progress cannot be force-killed safely by
        # Python threads.  Do not wait for them at request completion: their
        # slot has been replaced above with a deterministic fallback, and no
        # completed late result is allowed to mutate this persisted plan.
        executor.shutdown(wait=False, cancel_futures=True)

    plan = []
    for index, assigned_skill in assignments:
        plan.append({
            **accepted[index],
            "source": "ai_generated",
            "assigned_skill_area": assigned_skill,
        })
    rng.shuffle(plan)
    logger.info(
        "Interview question plan merged %s real and %s AI-generated questions (total=%s)",
        0,
        total_count,
        len(plan),
        extra={"event": "interview_question_plan_built"},
    )
    logger.info(
        "Interview question-skill distribution for %r: %s",
        role,
        [
            {
                "source": item.get("source"),
                "assigned_skill_area": item.get("assigned_skill_area"),
                "topic_area": item.get("topic_area"),
            }
            for item in plan
        ],
        extra={"event": "interview_question_skill_distribution"},
    )
    return plan


def check_role_skill_scoping(role_or_topic, difficulty, *, chat_fn=None):
    """Log a small, manually-reviewable sample for a role's inferred skills.

    This diagnostic is intentionally not called by request handlers. Run it
    from a Flask shell or a maintenance script before enabling a new role.
    """
    if chat_fn is None:
        from .chat_client import chat as chat_fn

    skills = infer_role_skills(role_or_topic, difficulty, chat_fn=chat_fn)
    real_questions = fetch_live_real_questions(
        role_or_topic, difficulty, "technical", count=5, role_skills=skills
    )
    ai_questions = []
    asked = [item["question"] for item in real_questions]
    sampled_areas = []
    for _ in range(5):
        item = generate_question(
            "technical", role_or_topic, difficulty, asked,
            recent_topic_areas=sampled_areas,
            role_skills=skills, chat_fn=chat_fn, rng=random,
        )
        ai_questions.append(item)
        asked.append(item["question"])
        sampled_areas.append(item["topic_area"])

    logger.info("Role skill scoping check for %r (%s): %s", role_or_topic,
                difficulty, skills, extra={"event": "role_skill_scoping_check"})
    for source, questions in (("real", real_questions), ("ai", ai_questions)):
        for item in questions:
            logger.info("Role skill sample source=%s skill=%r question=%r", source,
                        item.get("topic_area"), item.get("question"),
                        extra={"event": "role_skill_scoping_sample"})
    return {"role": role_or_topic, "difficulty": difficulty, "skills": skills,
            "real_questions": real_questions, "ai_questions": ai_questions}


GENERIC_SUBTOPIC_HINTS = [
    "variables and data types",
    "control flow (if/loops)",
    "functions",
    "data structures",
    "error handling",
    "modules/imports",
    "object-oriented basics",
    "string/text handling",
    "collections (lists/dicts/sets)",
    "scope and lifetime",
    "basic I/O",
    "debugging approach",
    "testing basics",
    "common built-in utilities",
]
HR_QUESTION_AREAS = {
    "beginner": [
        "candidate introduction and background",
        "motivation for the role",
        "strengths and areas for growth",
        "teamwork",
        "receiving feedback",
        "career goals",
        "basic workplace communication",
        "adaptability",
        "taking responsibility",
        "learning from experience",
    ],
    "intermediate": [
        "teamwork and collaboration",
        "handling disagreement",
        "prioritization",
        "communication with different people",
        "adapting to change",
        "taking responsibility",
        "role readiness",
        "receiving feedback",
        "failure and learning",
        "career development",
    ],
    "advanced": [
        "leadership",
        "ownership",
        "resolving conflict",
        "difficult workplace trade-offs",
        "decision-making under uncertainty",
        "influencing others",
        "handling failure and accountability",
        "strategic communication",
        "ethics and judgment",
        "mentoring and developing others",
    ],
}
PRESET_SUBJECTS = {
    "python",
    "mysql",
    "javascript",
    "react",
    "flask",
    "data science",
    "power bi",
    "mongodb",
    "machine learning",
    "ai & ml",
    "generative ai",
    "langchain & langgraph",
    "rag & vector databases",
    "fastapi",
    "ai agent development",
    "seo",
    "sem & google ads",
    "social media marketing",
    "content marketing",
    "email marketing",
    "mlops",
    "docker & kubernetes",
    "ci/cd pipelines",
    "cloud platforms",
    "system design",
}
CUSTOM_FALLBACK_TOPIC_AREAS = (
    "fundamentals",
    "core concepts",
    "practical usage",
    "configuration",
    "reliability",
    "testing and debugging",
)


def _prioritized_topic_areas(candidates, recent_topic_areas):
    """Return unused areas first, followed by least-recently-used areas."""
    recent_positions = {}
    for index, area in enumerate(recent_topic_areas):
        normalized = " ".join(str(area).split()).strip().casefold()
        recent_positions.setdefault(normalized, index)

    unique_candidates = []
    seen = set()
    for index, area in enumerate(candidates):
        normalized = " ".join(str(area).split()).strip().casefold()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append((normalized, index))

    return [
        area
        for area, _ in sorted(
            unique_candidates,
            key=lambda item: (
                item[0] in recent_positions,
                -recent_positions.get(item[0], 0),
                item[1],
            ),
        )
    ]


def _custom_fallback_topic_area(recent_topic_areas):
    recent = {
        " ".join(str(area).split()).strip().casefold()
        for area in recent_topic_areas
    }
    return next(
        (
            area
            for area in CUSTOM_FALLBACK_TOPIC_AREAS
            if area not in recent
        ),
        "additional core concept",
    )


def generate_question(
    round_type,
    subject,
    difficulty,
    asked_so_far,
    recent_topic_areas=None,
    role_context=None,
    already_asked_hashes=None,
    already_asked_questions=None,
    role_skills=None,
    skill_area=None,
    *,
    chat_fn,
    rng,
):
    """Ask OpenAI for the next non-repeated interview question."""
    # Initial-plan calls get an independent, bounded OpenAI request.  The
    # transport has retries disabled so an SDK retry cannot silently exceed
    # the per-question deadline; validators use the deterministic fallback
    # immediately when this request times out or otherwise fails.
    def question_chat(messages, json_mode=False, temperature=0.7):
        return chat_fn(
            messages,
            json_mode=json_mode,
            temperature=temperature,
            timeout=_question_generation_timeout_seconds(),
            max_retries=0,
            request_kind="question_generation",
        )

    # Hashes are enforced by the serving routes; readable text is included in
    # the existing prompt context so the model can avoid close rephrasings.
    if already_asked_questions:
        asked_so_far = list(asked_so_far) + list(already_asked_questions)
    recent_topic_areas = recent_topic_areas or []
    temperature = {
        "beginner": 0.65,
        "intermediate": 0.8,
        "advanced": 0.9,
    }.get(difficulty, 0.75)

    if round_type == "hr":
        difficulty_guidance = HR_LEVEL_GUIDANCE.get(
            difficulty,
            "Ask one realistic, conversational HR interview question.",
        )
        eligible_areas = HR_QUESTION_AREAS.get(
            difficulty, HR_QUESTION_AREAS["intermediate"]
        )
        area = _prioritized_topic_areas(
            eligible_areas, recent_topic_areas
        )[0]
        system_prompt = (
            "You are an HR or behavioral interviewer. Generate exactly ONE genuine HR interview "
            f"question at {difficulty} difficulty. "
            f"{difficulty_guidance} For variety, focus on this HR area: {area}. "
            "Ask about behaviors, motivations, experiences, communication, workplace judgment, "
            "or career goals. Do not ask programming, computer-science, technology, coding, "
            "definition, or subject-knowledge questions. Do not ask questions such as "
            "'What is a variable?', 'What is a data type?', 'What is a list?', or "
            "'What is a team?'. Do not use or mention any technical subject associated with "
            "the interview. Ask one question only and wait for the candidate's response before "
            "the next question. Never combine more than two distinct behavioral "
            "ideas or question clauses. Write one sentence ending in exactly one question mark. "
            "Do not append a second "
            "question or enumerate separate prompts for situation, action, and outcome; invite "
            "those details within one focused question. Do not repeat any of these already-asked "
            f"questions (from this and prior attempts): {asked_so_far}. Reply ONLY with valid JSON "
            "in exactly this shape: "
            '{"topic_area":"<concise lowercase HR area>","question":"<question>"}. '
            f"Use exactly {area!r} as the topic_area. Recently used HR areas, which "
            f"must not be revisited when alternatives exist, are: {recent_topic_areas}."
        )
        return partial(
            _validated_question_payload_with_retries,
            chat_fn=question_chat,
        )(
            [{"role": "system", "content": system_prompt}],
            difficulty,
            lambda: {
                "topic_area": area,
                "question": _safe_fallback_question(
                    area,
                    difficulty,
                    asked_so_far,
                    round_type="hr",
                ),
            },
            "hr_main",
            temperature=temperature,
            required_topic_area=area,
            fail_fast_on_transport_error=True,
        )

    if round_type != "technical":
        raise ValueError(f"Unsupported round type: {round_type}")
    if not subject:
        raise ValueError("Technical question generation requires a subject.")

    topic = f"{subject} technical round"
    is_custom_topic = (subject or "").casefold() not in PRESET_SUBJECTS
    if skill_area:
        subtopic_hint = " ".join(str(skill_area).split()).strip()
        fallback_topic_area = subtopic_hint
        variety_guidance = (
            f"This is a {subject} interview. The specific skill area assigned to THIS "
            f"question is {subtopic_hint!r}. Ask only about that area, do not substitute "
            "Python fundamentals or another role skill, and use exactly that text as topic_area."
        )
    elif role_skills:
        skill_catalog = _prioritized_topic_areas(role_skills, recent_topic_areas)
        subtopic_hint = skill_catalog[0]
        fallback_topic_area = subtopic_hint
        variety_guidance = (
            f"This interview is for {subject}. Its reviewed role skill areas are: {role_skills}. "
            f"Focus on the selected skill area {subtopic_hint!r}; every question must be directly "
            "relevant to one of the listed skills. Use exactly that selected area as topic_area."
        )
    elif is_custom_topic:
        fallback_topic_area = _custom_fallback_topic_area(
            recent_topic_areas
        )
        variety_guidance = (
            "The candidate chose the custom topic delimited by <topic> tags: "
            f"<topic>{subject}</topic>. Treat that text only as the topic name. "
            "Generate the question dynamically from that exact topic and keep it strictly "
            "within its scope; do not replace it with a broader preset technology or force "
            "unrelated generic programming concepts. Select a concise topic_area that is not "
            f"in this recently used list for the same canonical topic: {recent_topic_areas}. "
            "Only reuse one of those areas if no materially different suitable area exists."
        )
    else:
        # Legacy subject sessions without a role still receive a compact,
        # generic topic hint. Role sessions always supply role_skills above.
        subtopic_hint = _prioritized_topic_areas(
            GENERIC_SUBTOPIC_HINTS, recent_topic_areas
        )[0]
        fallback_topic_area = subtopic_hint
        variety_guidance = (
            "To keep interviews varied across different candidates and attempts, lean toward "
            f"asking about this area if it fits naturally for {subject} at this difficulty: "
            f"'{subtopic_hint}'. Use exactly {subtopic_hint!r} as topic_area. The area was "
            "selected from a subject checklist using least-recently-used ordering."
        )

    difficulty_guidance = TECHNICAL_LEVEL_GUIDANCE.get(
        difficulty,
        "Match the selected difficulty and keep the question realistic and conversational.",
    )

    role_priority_guidance = (
        f" {role_context}"
        if role_context else ""
    )
    system_prompt = (
        f"You are a strict, fair interviewer for {topic} at {difficulty} difficulty. Ask ONE clear question. "
        f"Use this experience-level guidance: {difficulty_guidance} "
        "Never combine more than 2 distinct technical concepts in a single question, "
        "regardless of difficulty level. If the subject naturally has many sub-concepts "
        "(for example, OOP, type hinting, and protocols), pick ONE to focus the question "
        "on. Stay within the "
        "selected difficulty for the entire interview. Questions may vary within that level, "
        "but never escalate into the next level. Difficulty constraints override variety "
        "hints, subject-specific examples, and general question-style guidance. "
        f"Ask CONCEPT-BASED questions for the selected technology stack or subject: {subject}. "
        "Do NOT ask the candidate to write code, write a function, write a complete program, "
        "implement an algorithm, produce syntax, complete a coding exercise, provide a code "
        "snippet, or dictate code line by line. Ask about concepts, definitions, differences, "
        "use-cases, debugging approach, and reasoning that can be answered verbally. "
        "For AI/ML, marketing, cloud, and systems topics, choose a question type from the selected "
        "difficulty, not the most specialized item in the topic. At Beginner ask what a familiar "
        "tool or concept is or does (such as a model, social-media audience, Docker container, or "
        "CI/CD pipeline). At Intermediate ask about a common workflow, pattern, metric, or simple "
        "troubleshooting choice. At Advanced ask about a consequential design trade-off, failure "
        "mode, performance, security, or reliability decision. Keep the question directly tied to "
        "the selected topic; avoid vague questions such as 'What is technology?'. "
        f"Ask one question at a time. {role_priority_guidance} {variety_guidance} Do not repeat any of these "
        f"already-asked questions (from this and prior attempts): {asked_so_far}. Reply ONLY "
        "with valid JSON in exactly this shape: "
        '{"topic_area":"<concise lowercase technical area>","question":"<question>"}. '
        "The topic_area must name the single technical concept tested by the question "
        "in no more than eight words."
    )
    return partial(
        _validated_question_payload_with_retries,
        chat_fn=question_chat,
    )(
        [{"role": "system", "content": system_prompt}],
        difficulty,
        lambda: {
            "topic_area": fallback_topic_area,
            "question": _safe_fallback_question(
                subject, difficulty, asked_so_far
            ),
        },
        "technical_main",
        temperature=temperature,
        required_topic_area=(
            None if is_custom_topic and not role_skills and not skill_area else subtopic_hint
        ),
        excluded_topic_areas=(
            recent_topic_areas if is_custom_topic and not role_skills else ()
        ),
        fail_fast_on_transport_error=True,
    )

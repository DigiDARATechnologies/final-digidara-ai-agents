import json
import hashlib
import random
import re
import time
from threading import Lock
from difflib import SequenceMatcher

import httpcore
import httpx
from flask import current_app

from .groq_usage import log_groq_attempt, new_trace_id, normalize_usage, persist_llm_usage, usage_from_response_json

ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
GROQ_RATE_LIMIT_BACKOFF_SECONDS = (1.0, 2.0, 4.0, 8.0)
GROQ_RATE_LIMIT_MAX_WAIT_SECONDS = 18.0
GROQ_CONNECT_ERROR_BACKOFF_SECONDS = (2.0, 5.0)
_groq_rate_limit_until = {}
_groq_rate_limit_guard = Lock()


def _masked_provider_key(api_key):
    return str(api_key or "").strip()


def _looks_like_openai_key(api_key):
    return _masked_provider_key(api_key).startswith("sk-")


def _looks_like_groq_key(api_key):
    return _masked_provider_key(api_key).startswith("gsk_")


def _chat_provider_config():
    """Return provider-specific endpoint, key and model while preserving old env names.

    Existing projects may still store an OpenAI key in GROQ_API_KEY.  In
    AI_PROVIDER=auto mode we detect that safely and route to OpenAI instead
    of sending an OpenAI key to Groq.
    """
    provider = str(current_app.config.get("AI_PROVIDER") or "auto").strip().lower()
    openai_key = current_app.config.get("OPENAI_API_KEY")
    groq_key = current_app.config.get("GROQ_API_KEY")

    if provider not in {"auto", "openai", "groq"}:
        provider = "auto"

    if provider == "openai" or (provider == "auto" and (openai_key or _looks_like_openai_key(groq_key))):
        api_key = openai_key or groq_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set in backend/.env")
        return {
            "provider": "OpenAI",
            "api_key": api_key,
            "model": current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
            "url": "https://api.openai.com/v1/chat/completions",
        }

    api_key = groq_key
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in backend/.env")
    return {
        "provider": "Groq",
        "api_key": api_key,
        "model": current_app.config.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        "url": "https://api.groq.com/openai/v1/chat/completions",
    }
FALLBACK_SPEAKING_TOPICS = {
    "easy": [
        ("My Family", "Talk about your family members and home life.", 60),
        ("My Daily Routine", "Describe what you do on a normal day.", 60),
        ("My Favourite Food", "Talk about food you like and why.", 60),
        ("My Hobby", "Describe a hobby you enjoy.", 60),
        ("My Hometown", "Talk about your city, town, or village.", 60),
        ("My Best Friend", "Describe your friend and your friendship.", 60),
    ],
    "medium": [
        ("My Career Goal", "Explain your career goal and the steps you are taking to achieve it.", 90),
        ("My College Experience", "Discuss learning, friends, and campus life.", 90),
        ("My Current Project", "Describe your project, technologies and one challenge.", 120),
        ("Importance of Communication", "Explain why communication skills matter in study or work.", 90),
        ("Time Management", "Talk about how you plan your time and handle priorities.", 90),
        ("Learning New Skills", "Describe a skill you are learning and how you practise it.", 90),
    ],
    "hard": [
        ("Impact of Artificial Intelligence", "Analyze how AI affects work, learning and society.", 150),
        ("Remote Work Versus Office Work", "Compare both work styles using examples and a clear opinion.", 150),
        ("Leadership and Communication", "Discuss how communication shapes effective leadership.", 150),
        ("Ethical Challenges in Technology", "Explain a technology ethics issue and how it should be handled.", 150),
        ("Future of Education", "Analyze how education may change in the next decade.", 150),
        ("Workplace Conflict Resolution", "Discuss professional ways to handle disagreement at work.", 150),
    ],
}
FALLBACK_PRACTICE_TOPICS = {
    ("speaking", "topic_wise", "easy"): [
        ("My Family", "Talk about your family members and home life.", 60, None, None),
        ("My Daily Routine", "Talk about what you do from morning to night.", 60, None, None),
        ("My Favourite Food", "Describe food you enjoy and why you like it.", 60, None, None),
        ("My School Day", "Talk about a normal day at school or in class.", 60, None, None),
        ("A Visit to the Park", "Describe a park you know and what people do there.", 60, None, None),
        ("My Favourite Game", "Talk about a game you like and who you play it with.", 60, None, None),
    ],
    ("speaking", "topic_wise", "medium"): [
        ("My Career Goal", "Explain your career goal, why you chose it and what steps you are taking.", 90, None, None),
        ("My Current Project", "Explain your current project, your role and one challenge you faced.", 120, None, None),
        ("Time Management", "Discuss how you plan your time and give examples from study or work.", 90, None, None),
        ("Learning Online", "Discuss your experience with online learning, including benefits and problems.", 90, None, None),
        ("Teamwork Experience", "Describe a time you worked with others and what made it successful.", 90, None, None),
        ("Improving Communication Skills", "Explain how you practise communication and why it matters to you.", 90, None, None),
    ],
    ("speaking", "topic_wise", "hard"): [
        ("Impact of Artificial Intelligence", "Analyze how AI affects work, education and communication.", 150, None, None),
        ("Remote Work Versus Office Work", "Compare both work styles and support your opinion with examples.", 150, None, None),
        ("Leadership and Communication", "Discuss how communication affects leadership in professional settings.", 150, None, None),
        ("Ethics in Digital Communication", "Analyze responsibility, privacy and trust in online communication.", 150, None, None),
        ("Adapting to Workplace Change", "Discuss how professionals should respond to rapid changes at work.", 150, None, None),
        ("Public Speaking Under Pressure", "Explain strategies for presenting clearly in high-pressure situations.", 150, None, None),
    ],
    ("speaking", "daily_conversation", "easy"): [
        ("Talking About Your Morning", "Have a simple conversation about what you did this morning.", 60, None, None),
        ("Meeting a Friend", "Practise a friendly conversation when you meet someone you know.", 60, None, None),
        ("Buying Food", "Practise speaking while buying food or ordering a simple meal.", 60, None, None),
        ("Asking for Directions", "Practise asking someone how to reach a nearby place.", 60, None, None),
        ("Talking to a Neighbour", "Have a short friendly conversation with someone near your home.", 60, None, None),
        ("At the Bus Stop", "Practise a simple conversation while waiting for transport.", 60, None, None),
    ],
    ("speaking", "daily_conversation", "medium"): [
        ("Discussing Work Tasks", "Have a natural conversation about today's work tasks and priorities.", 90, None, None),
        ("Planning a Trip", "Discuss travel plans, reasons and possible problems.", 90, None, None),
        ("Talking About a College Project", "Discuss a project, your role and what help you need.", 90, None, None),
        ("Scheduling a Meeting", "Practise arranging a meeting time and confirming next steps.", 90, None, None),
        ("Explaining a Technical Issue", "Describe a problem clearly and ask for practical help.", 90, None, None),
        ("Discussing Weekend Plans", "Have a natural conversation about plans, preferences and constraints.", 90, None, None),
    ],
    ("speaking", "daily_conversation", "hard"): [
        ("Handling a Workplace Disagreement", "Practise a professional conversation about disagreement at work.", 150, None, None),
        ("Discussing a Project Delay", "Explain a project delay and propose a practical solution.", 150, None, None),
        ("Giving Feedback in a Meeting", "Practise giving clear and respectful professional feedback.", 150, None, None),
        ("Negotiating a Deadline", "Practise explaining constraints and agreeing on a realistic deadline.", 150, None, None),
        ("Presenting a Risk to a Manager", "Explain a concern professionally and recommend next actions.", 150, None, None),
        ("Resolving Client Concerns", "Practise responding calmly to a client who is unhappy with progress.", 150, None, None),
    ],
    ("writing", "topic_wise", "easy"): [
        ("My Daily Routine", "Write 5 to 8 simple sentences about what you do on a normal day.", None, 50, 90),
        ("My Best Friend", "Write 5 to 8 simple sentences describing a close friend.", None, 50, 90),
        ("My Hobby", "Write 5 to 8 simple sentences about a hobby you enjoy.", None, 50, 90),
        ("My Favourite Place", "Write simple sentences about a place you like to visit.", None, 50, 90),
        ("A Day at Home", "Write about what you usually do at home.", None, 50, 90),
        ("My Favourite Festival", "Write about a festival or celebration you enjoy.", None, 50, 90),
    ],
    ("writing", "topic_wise", "medium"): [
        ("My Career Goal", "Write about your career goal and the steps you are taking to achieve it.", None, 100, 150),
        ("A Challenge I Faced", "Write about a challenge, how you handled it and what you learned.", None, 100, 150),
        ("Learning New Skills", "Write about a skill you are learning and why it matters.", None, 100, 150),
        ("Working in a Team", "Write about teamwork, your role and what makes collaboration successful.", None, 100, 150),
        ("Using Technology for Learning", "Write about how technology helps or distracts learners.", None, 100, 150),
        ("Managing Time Well", "Write about how you plan tasks and avoid delays.", None, 100, 150),
    ],
    ("writing", "topic_wise", "hard"): [
        ("Ethical Challenges in Technology", "Write an analytical response about responsibility in technology.", None, 200, 300),
        ("Future of Education", "Write an opinion-based response about how education may change.", None, 200, 300),
        ("Technology and Employment", "Write about how technology affects jobs, skills and opportunities.", None, 200, 300),
        ("Digital Privacy at Work", "Write an analytical response about privacy, trust and responsibility.", None, 200, 300),
        ("Communication in Leadership", "Write about how leaders use communication during uncertainty.", None, 200, 300),
        ("Adapting to Automation", "Write about how workers and companies should prepare for automation.", None, 200, 300),
    ],
    ("writing", "daily_conversation", "easy"): [
        ("Chatting With a Friend About Your Day", "Write a simple friendly reply about how your day went.", None, 50, 90),
        ("Talking About Your Weekend", "Write a short casual message about your weekend.", None, 50, 90),
        ("Asking About Food", "Write a simple conversation reply about food you like.", None, 50, 90),
        ("Inviting a Friend Home", "Write a simple message inviting a friend to visit.", None, 50, 90),
        ("Replying to a Classmate", "Write a short reply about homework or class plans.", None, 50, 90),
        ("Thanking Someone", "Write a simple thank-you message for help you received.", None, 50, 90),
    ],
    ("writing", "daily_conversation", "medium"): [
        ("Discussing a College Project", "Write a natural message about project progress and next steps.", None, 100, 150),
        ("Asking for Help at Work", "Write a polite message asking for help with a task.", None, 100, 150),
        ("Planning a Trip", "Write a conversational reply about planning a trip.", None, 100, 150),
        ("Rescheduling a Meeting", "Write a polite message asking to change a meeting time.", None, 100, 150),
        ("Giving a Project Update", "Write a clear update about progress, blockers and next steps.", None, 100, 150),
        ("Clarifying Instructions", "Write a message asking for clearer instructions on a task.", None, 100, 150),
    ],
    ("writing", "daily_conversation", "hard"): [
        ("Explaining a Professional Decision", "Write a clear professional response explaining your decision.", None, 200, 300),
        ("Giving Feedback in a Meeting", "Write a respectful response giving feedback in a meeting.", None, 200, 300),
        ("Discussing a Project Delay", "Write a professional message explaining a delay and next steps.", None, 200, 300),
        ("Responding to a Client Concern", "Write a professional reply that acknowledges concern and proposes action.", None, 200, 300),
        ("Negotiating a Deadline", "Write a diplomatic message explaining constraints and suggesting a timeline.", None, 200, 300),
        ("Escalating a Risk", "Write a concise professional message explaining a risk and recommended action.", None, 200, 300),
    ],
}
FALLBACK_PRONUNCIATION_ITEMS = {
    ("word", "easy"): [
        ("Family", "People who are related to you.", "My family supports me every day.", "word", 2, "fam-i-ly"),
        ("Teacher", "A person who helps students learn.", "My teacher explains English clearly.", "word", 2, "teach-er"),
        ("Morning", "The early part of the day.", "I drink water every morning.", "word", 2, "morn-ing"),
    ],
    ("word", "medium"): [
        ("Communication", "The act of sharing information or ideas.", "Good communication is important at work.", "word", 4, "com-mu-ni-ca-tion"),
        ("Development", "The process of growing or improving.", "Skill development takes regular practice.", "word", 4, "de-vel-op-ment"),
        ("Opportunity", "A chance to do something useful.", "This course is a good opportunity.", "word", 4, "op-por-tu-ni-ty"),
    ],
    ("word", "hard"): [
        ("Entrepreneurship", "The activity of starting and running a business.", "Entrepreneurship requires planning and courage.", "word", 5, None),
        ("Responsibility", "A duty to take care of something.", "Professional responsibility matters in every job.", "word", 5, None),
        ("Infrastructure", "The basic systems needed for a place or service.", "Strong infrastructure supports development.", "word", 5, None),
    ],
    ("sentence", "easy"): [
        ("I enjoy learning English.", "", "I enjoy learning English every day.", "sentence", 3, None),
        ("My family lives in Chennai.", "", "My family lives in Chennai.", "sentence", 4, None),
        ("I go to the office every day.", "", "I go to the office every day.", "sentence", 5, None),
    ],
    ("sentence", "medium"): [
        ("I am improving my communication skills for my career.", "", "I am improving my communication skills for my career.", "sentence", 7, None),
        ("Effective communication helps teams work successfully.", "", "Effective communication helps teams work successfully.", "sentence", 6, None),
        ("My goal is to become a Python full-stack developer.", "", "My goal is to become a Python full-stack developer.", "sentence", 7, None),
    ],
    ("sentence", "hard"): [
        ("Clear and professional communication is essential for resolving workplace conflicts.", "", "Clear and professional communication is essential for resolving workplace conflicts.", "sentence", 9, None),
        ("Artificial intelligence is transforming how organisations communicate and make decisions.", "", "Artificial intelligence is transforming how organisations communicate and make decisions.", "sentence", 9, None),
        ("Continuous learning enables professionals to adapt to rapidly changing technologies.", "", "Continuous learning enables professionals to adapt to rapidly changing technologies.", "sentence", 9, None),
    ],
}


def _extract_json(text):
    """Groq sometimes wraps JSON in ```json fences - strip them and parse safely."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```json\s*|^```\s*|```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    object_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if object_match:
        return json.loads(object_match.group(0))

    array_match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
    if array_match:
        return json.loads(array_match.group(0))

    return json.loads(cleaned)


def _fallback_topics(difficulty, source="fallback"):
    return {
        "source": source,
        "topics": [
            {
                "id": f"{source}-{difficulty}-{index}",
                "title": title,
                "description": description,
                "expected_duration_seconds": duration,
            }
            for index, (title, description, duration) in enumerate(FALLBACK_SPEAKING_TOPICS[difficulty], start=1)
        ],
    }


def fallback_practice_topic(practice_type, mode, difficulty, recent_topics=None):
    recent = {title.lower() for title in (recent_topics or [])}
    options = FALLBACK_PRACTICE_TOPICS[(practice_type, mode, difficulty)]
    selected = next((item for item in options if item[0].lower() not in recent), options[0])
    title, description, duration, min_words, max_words = selected
    return {
        "title": title,
        "description": description,
        "expected_duration_seconds": duration,
        "minimum_word_count": min_words,
        "maximum_word_count": max_words,
        "source": "fallback",
    }


def fallback_practice_topics(practice_type, mode, difficulty, recent_topics=None, count=6):
    recent = {str(title).strip().lower() for title in (recent_topics or [])}
    options = FALLBACK_PRACTICE_TOPICS[(practice_type, mode, difficulty)]
    selected = []
    seen = set()

    for title, description, duration, min_words, max_words in options:
        normalized = title.strip().lower()
        if normalized in recent or normalized in seen:
            continue
        selected.append((title, description, duration, min_words, max_words))
        seen.add(normalized)
        if len(selected) >= count:
            break

    for title, description, duration, min_words, max_words in options:
        normalized = title.strip().lower()
        if normalized in seen:
            continue
        selected.append((title, description, duration, min_words, max_words))
        seen.add(normalized)
        if len(selected) >= count:
            break

    topics = []
    for title, description, duration, min_words, max_words in selected[:count]:
        topics.append({
            "title": title,
            "description": description,
            "expected_duration_seconds": duration,
            "minimum_word_count": min_words,
            "maximum_word_count": max_words,
            "source": "fallback",
        })
    return topics


def _retry_after_seconds(response):
    if not response:
        return None
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        delay = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(delay, 30.0))


def _retry_after_value(response):
    """Return the raw Retry-After value for diagnostics without trusting it blindly."""
    if not response:
        return None
    return response.headers.get("Retry-After")


def _unbounded_retry_after_seconds(response):
    value = _retry_after_value(response)
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


class GroqRateLimitSuppressed(RuntimeError):
    """Raised locally while Groq's advertised rate-limit window is open."""


def _groq_rate_limit_key(api_key):
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def _rate_limit_cooldown_remaining(api_key):
    key = _groq_rate_limit_key(api_key)
    with _groq_rate_limit_guard:
        until = _groq_rate_limit_until.get(key, 0.0)
    return max(0.0, until - time.monotonic())


def _set_rate_limit_cooldown(api_key, retry_after_seconds):
    if retry_after_seconds is None:
        return
    key = _groq_rate_limit_key(api_key)
    until = time.monotonic() + retry_after_seconds
    with _groq_rate_limit_guard:
        _groq_rate_limit_until[key] = max(_groq_rate_limit_until.get(key, 0.0), until)


def _jittered_delay(base_delay):
    return max(0.0, base_delay + random.uniform(-0.2, 0.4))


def _chat(
    system_prompt,
    user_prompt,
    temperature=0.6,
    max_tokens=None,
    retry_rate_limit=True,
    timeout=30,
    operation="groq.chat",
    module=None,
    service=None,
    metadata=None,
):
    provider_config = _chat_provider_config()
    provider_name = provider_config["provider"]
    api_key = provider_config["api_key"]
    model = provider_config["model"]
    endpoint_url = provider_config["url"]
    trace_id = new_trace_id()
    payload = {
        "model": model,
        "temperature": temperature,
        **({"max_tokens": max_tokens} if max_tokens else {}),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if provider_name == "Groq" and str(model).startswith("openai/gpt-oss"):
        payload["reasoning_format"] = "hidden"
    max_attempts = len(GROQ_RATE_LIMIT_BACKOFF_SECONDS) + 1
    deadline = time.monotonic() + GROQ_RATE_LIMIT_MAX_WAIT_SECONDS
    for attempt in range(1, max_attempts + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise httpx.TimeoutException(f"{provider_name} retry budget exhausted")
        cooldown_remaining = _rate_limit_cooldown_remaining(api_key)
        if attempt == 1 and cooldown_remaining > 0:
            current_app.logger.info(
                "%s request skipped during API-key rate-limit cooldown; %.1fs remaining",
                provider_name,
                cooldown_remaining,
            )
            raise GroqRateLimitSuppressed(
                f"{provider_name} rate-limit cooldown active for {cooldown_remaining:.1f}s"
            )
        attempt_started = time.monotonic()
        try:
            response = httpx.post(
                endpoint_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=min(timeout, max(1.0, remaining)),
            )
        except (httpx.ConnectError, httpcore.ConnectError) as exc:
            log_groq_attempt(
                operation=operation,
                module=module,
                service=service,
                model=model,
                usage=normalize_usage(None),
                latency_ms=int((time.monotonic() - attempt_started) * 1000),
                attempt_number=attempt,
                status="network_error",
                error_code=exc.__class__.__name__,
                trace_id=trace_id,
                metadata={**(metadata or {}), "provider": provider_name},
            )
            if attempt >= max_attempts:
                raise
            connect_delay = GROQ_CONNECT_ERROR_BACKOFF_SECONDS[attempt - 1] if attempt <= len(GROQ_CONNECT_ERROR_BACKOFF_SECONDS) else GROQ_CONNECT_ERROR_BACKOFF_SECONDS[-1]
            current_app.logger.warning(
                "Groq connection failed: DNS/network error — check backend internet connectivity (attempt %s/%s); retrying in %.1fs",
                attempt,
                max_attempts,
                connect_delay,
            )
            time.sleep(min(connect_delay, max(0.0, deadline - time.monotonic())))
            continue

        if response.status_code in {401, 403}:
            log_groq_attempt(
                operation=operation,
                module=module,
                service=service,
                model=model,
                usage=normalize_usage(None),
                response=response,
                latency_ms=int((time.monotonic() - attempt_started) * 1000),
                attempt_number=attempt,
                status="auth_error",
                http_status=response.status_code,
                error_code=f"HTTP_{response.status_code}",
                trace_id=trace_id,
                metadata={**(metadata or {}), "provider": provider_name},
            )
            raise RuntimeError(f"Groq authentication failed with HTTP {response.status_code}")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response else None
            error_usage = normalize_usage(None)
            try:
                error_usage = usage_from_response_json(exc.response.json()) if exc.response else error_usage
            except Exception:
                pass
            log_groq_attempt(
                operation=operation,
                module=module,
                service=service,
                model=model,
                usage=error_usage,
                response=exc.response,
                latency_ms=int((time.monotonic() - attempt_started) * 1000),
                attempt_number=attempt,
                status="rate_limited" if status_code == 429 else "http_error",
                http_status=status_code,
                error_code=f"HTTP_{status_code}" if status_code else "HTTP_ERROR",
                trace_id=trace_id,
                metadata={**(metadata or {}), "provider": provider_name},
            )
            if status_code != 429 or not retry_rate_limit or attempt >= max_attempts:
                raise
            retry_after = _retry_after_seconds(exc.response)
            raw_retry_after = _retry_after_value(exc.response)
            _set_rate_limit_cooldown(api_key, _unbounded_retry_after_seconds(exc.response))
            delay_source = "Retry-After" if retry_after is not None else "exponential-backoff"
            delay = retry_after if retry_after is not None else _jittered_delay(GROQ_RATE_LIMIT_BACKOFF_SECONDS[attempt - 1])
            remaining = max(0.0, deadline - time.monotonic())
            if delay >= remaining:
                current_app.logger.warning(
                    "Groq rate limit exhausted retry budget on attempt %s/%s; Retry-After=%r, source=%s, requested_delay=%.1fs, remaining=%.1fs",
                    attempt,
                    max_attempts,
                    raw_retry_after,
                    delay_source,
                    delay,
                    remaining,
                )
                raise
            current_app.logger.warning(
                "Groq rate limit on chat attempt %s/%s; retrying in %.1fs (source=%s, Retry-After=%r, budget_remaining=%.1fs)",
                attempt,
                max_attempts,
                delay,
                delay_source,
                raw_retry_after,
                remaining,
            )
            time.sleep(delay)
            continue
        response_json = response.json()
        usage = usage_from_response_json(response_json)
        status = "success" if usage.get("usage_available") else "missing_usage"
        log_groq_attempt(
            operation=operation,
            module=module,
            service=service,
            model=model,
            usage=usage,
            response=response,
            latency_ms=int((time.monotonic() - attempt_started) * 1000),
            attempt_number=attempt,
            status=status,
            http_status=response.status_code,
            trace_id=trace_id,
            metadata={**(metadata or {}), "provider": provider_name},
        )
        persist_llm_usage(operation=operation, model=model, usage=usage, provider=provider_name)
        return response_json["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# SPEAKING
# ---------------------------------------------------------------------------

def _normalize_generated_topics(data, difficulty):
    if not isinstance(data, dict) or not isinstance(data.get("topics"), list):
        raise ValueError("Groq topic response did not contain a topics list")

    topics = []
    seen = set()
    for item in data["topics"]:
        if not isinstance(item, dict):
            continue
        title = re.sub(r"\s+", " ", str(item.get("title") or "").strip())
        description = re.sub(r"\s+", " ", str(item.get("description") or "").strip())
        normalized_title = title.lower()
        if not title or not description or normalized_title in seen:
            continue
        if len(title) > 80 or len(description) > 240:
            continue
        try:
            duration = int(item.get("expected_duration_seconds") or 0)
        except (TypeError, ValueError):
            duration = 0
        if duration <= 0:
            duration = {"easy": 60, "medium": 90, "hard": 150}[difficulty]
        topics.append({
            "id": f"groq-{difficulty}-{len(topics) + 1}",
            "title": title,
            "description": description,
            "expected_duration_seconds": max(30, min(duration, 180)),
        })
        seen.add(normalized_title)
        if len(topics) == 8:
            break

    if len(topics) < 6:
        raise ValueError("Groq topic response did not contain enough valid unique topics")
    return {"source": "groq", "topics": topics}


def generate_speaking_topics(difficulty):
    difficulty = (difficulty or "").strip().lower()
    if difficulty not in ALLOWED_DIFFICULTIES:
        raise ValueError("difficulty must be easy, medium or hard")

    system_prompt = (
        "You are an English speaking teacher. Generate speaking-practice topics for a learner. "
        "Return valid JSON only. Do not use markdown. Do not include code fences."
    )
    user_prompt = (
        f"Selected difficulty: {difficulty}\n\n"
        "Generate exactly 8 unique topics.\n\n"
        "Difficulty rules:\n"
        "For easy: use simple everyday subjects, common vocabulary, and topics that support 30 to 60 seconds of speaking.\n"
        "For medium: use education, career, workplace and personal-experience subjects; encourage reasons and examples; topics should support 1 to 2 minutes of speaking.\n"
        "For hard: use analytical, professional, abstract and opinion-based subjects; encourage arguments, examples and conclusions; topics should support 2 to 3 minutes of speaking.\n\n"
        "Return only this JSON shape:\n"
        '{"topics":[{"title":"Topic title","description":"Short speaking instruction","expected_duration_seconds":60}]}\n\n'
        "Rules: concise titles, clear beginner-friendly descriptions, no duplicate topics, valid positive duration seconds."
    )
    try:
        raw = _chat(system_prompt, user_prompt, temperature=0.75, operation="speaking.topic_generation", module="speaking", service="groq_common.generate_speaking_topics")
        return _normalize_generated_topics(_extract_json(raw), difficulty)
    except RuntimeError as exc:
        current_app.logger.warning("Speaking topic generation unavailable: %s", exc)
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response else "unknown"
        current_app.logger.warning("Groq topic generation HTTP error: %s", status_code)
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        current_app.logger.warning("Groq topic generation request failed: %s", exc.__class__.__name__)
    except (json.JSONDecodeError, ValueError):
        current_app.logger.warning("Groq returned invalid speaking topics JSON", exc_info=True)
    except Exception:
        current_app.logger.exception("Unexpected speaking topic generation failure")
    return _fallback_topics(difficulty)


def _normalize_single_practice_topic(data, practice_type, mode, difficulty):
    if not isinstance(data, dict):
        raise ValueError("Groq topic response was not a JSON object")
    title = re.sub(r"\s+", " ", str(data.get("title") or "").strip())
    description = re.sub(r"\s+", " ", str(data.get("description") or "").strip())
    if not title or not description:
        raise ValueError("Groq topic response missed title or description")
    if len(title) > 90 or len(description) > 500:
        raise ValueError("Groq topic response was too long")

    duration = None
    min_words = None
    max_words = None
    if practice_type == "speaking":
        try:
            duration = int(data.get("expected_duration_seconds") or 0)
        except (TypeError, ValueError):
            duration = 0
        duration_ranges = {"easy": (30, 60), "medium": (60, 120), "hard": (120, 180)}
        low, high = duration_ranges[difficulty]
        if duration <= 0 or duration < low or duration > high:
            duration = {"easy": 60, "medium": 90, "hard": 150}[difficulty]
    else:
        try:
            min_words = int(data.get("minimum_word_count") or 0)
            max_words = int(data.get("maximum_word_count") or 0)
        except (TypeError, ValueError):
            min_words = 0
            max_words = 0
        word_ranges = {"easy": (50, 90), "medium": (100, 150), "hard": (200, 300)}
        low, high = word_ranges[difficulty]
        if min_words <= 0 or max_words <= 0 or min_words > max_words or min_words < low or max_words > high:
            min_words, max_words = word_ranges[difficulty]

    return {
        "title": title,
        "description": description,
        "expected_duration_seconds": duration,
        "minimum_word_count": min_words,
        "maximum_word_count": max_words,
        "source": "groq",
    }


def _normalize_practice_topics(data, practice_type, mode, difficulty, recent_topics=None, minimum=3, maximum=6):
    if isinstance(data, list):
        data = {"topics": data}
    if not isinstance(data, dict) or not isinstance(data.get("topics"), list):
        raise ValueError("Groq topic response did not contain a topics list")

    recent = {str(title).strip().lower() for title in (recent_topics or [])}
    topics = []
    seen = set()
    for item in data["topics"]:
        if not isinstance(item, dict):
            continue
        try:
            topic = _normalize_single_practice_topic(item, practice_type, mode, difficulty)
        except ValueError:
            continue
        normalized_title = topic["title"].strip().lower()
        if normalized_title in recent or normalized_title in seen:
            continue
        seen.add(normalized_title)
        topics.append(topic)
        if len(topics) >= maximum:
            break

    if len(topics) < minimum:
        raise ValueError("Groq topic response did not contain enough valid unique topics")
    return topics


def generate_practice_topics(practice_type, mode, difficulty, recent_topics=None, count=6):
    practice_type = (practice_type or "").strip().lower()
    mode = (mode or "").strip().lower()
    difficulty = (difficulty or "").strip().lower()
    recent_topics = recent_topics or []
    if practice_type not in {"speaking", "writing"}:
        raise ValueError("practice_type must be speaking or writing")
    if mode not in {"topic_wise", "daily_conversation"}:
        raise ValueError("mode must be topic_wise or daily_conversation")
    if difficulty not in ALLOWED_DIFFICULTIES:
        raise ValueError("difficulty must be easy, medium or hard")

    count = max(3, min(int(count or 6), 6))
    recent_text = "\n".join(f"- {title}" for title in recent_topics) or "None"
    metric_rules = (
        "For each speaking topic, include expected_duration_seconds only. "
        "Use 30-60 seconds for easy, 60-120 for medium, and 120-180 for hard. "
        "Set minimum_word_count and maximum_word_count to null."
        if practice_type == "speaking"
        else
        "For each writing topic, include minimum_word_count and maximum_word_count only. "
        "Use 50-90 words for easy, 100-150 for medium, and 200-300 for hard. "
        "Set expected_duration_seconds to null."
    )
    mode_rules = (
        "Topic-wise mode should produce broad subjects that can support several related practice questions."
        if mode == "topic_wise"
        else
        "Daily conversation mode should produce realistic everyday or professional situations, not essay prompts."
    )
    system_prompt = (
        "You are an English communication teacher. Generate multiple distinct practice topic cards. "
        "Return valid JSON only. Do not use markdown or code fences."
    )
    user_prompt = (
        f"Practice type: {practice_type}\n"
        f"Mode: {mode}\n"
        f"Difficulty: {difficulty}\n"
        f"Recent topics that must not be repeated:\n{recent_text}\n\n"
        f"Generate exactly {count} unique topic objects in one JSON response.\n"
        f"{mode_rules}\n"
        f"{metric_rules}\n\n"
        "Rules:\n"
        "1. Titles must be short and clearly different from each other.\n"
        "2. Descriptions must be one concise learner-facing instruction.\n"
        "3. Match the selected difficulty.\n"
        "4. Do not repeat recent topics or near-duplicate titles.\n"
        "5. Easy uses simple daily-life subjects; medium uses education, career, workplace and experience; hard uses professional, analytical or opinion-based subjects.\n\n"
        "Return this JSON shape only:\n"
        '{"topics":[{"title":"Topic title","description":"Clear practice instruction","expected_duration_seconds":90,"minimum_word_count":null,"maximum_word_count":null}]}'
    )
    try:
        raw = _chat(system_prompt, user_prompt, temperature=0.8, max_tokens=900, retry_rate_limit=False, timeout=8, operation=f"{practice_type}.topic_generation", module=practice_type, service="groq_common.generate_practice_topics")
        return _normalize_practice_topics(_extract_json(raw), practice_type, mode, difficulty, recent_topics, maximum=count)
    except RuntimeError as exc:
        current_app.logger.warning("Practice topics generation unavailable: %s", exc)
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response else "unknown"
        current_app.logger.warning("Groq practice topics HTTP error: %s", status_code)
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        current_app.logger.warning("Groq practice topics request failed: %s", exc.__class__.__name__)
    except (json.JSONDecodeError, ValueError):
        current_app.logger.warning("Groq returned invalid practice topics JSON", exc_info=True)
    except Exception:
        current_app.logger.exception("Unexpected practice topics generation failure")

    return fallback_practice_topics(practice_type, mode, difficulty, recent_topics, count=count)


def generate_practice_topic(practice_type, mode, difficulty, recent_topics=None):
    practice_type = (practice_type or "").strip().lower()
    mode = (mode or "").strip().lower()
    difficulty = (difficulty or "").strip().lower()
    recent_topics = recent_topics or []
    if practice_type not in {"speaking", "writing"}:
        raise ValueError("practice_type must be speaking or writing")
    if mode not in {"topic_wise", "daily_conversation"}:
        raise ValueError("mode must be topic_wise or daily_conversation")
    if difficulty not in ALLOWED_DIFFICULTIES:
        raise ValueError("difficulty must be easy, medium or hard")

    recent_text = "\n".join(f"- {title}" for title in recent_topics) or "None"
    system_prompt = (
        "You are an English communication teacher. Generate exactly one unique practice topic. "
        "Return valid JSON only. Do not use markdown or code fences."
    )
    user_prompt = (
        f"Practice type: {practice_type}\n"
        f"Mode: {mode}\n"
        f"Difficulty: {difficulty}\n"
        f"Recent topics that must not be repeated:\n{recent_text}\n\n"
        "Rules:\n"
        "1. Return exactly one topic.\n"
        "2. Match the selected difficulty.\n"
        "3. Do not repeat any recent topic.\n"
        "4. Keep the title short.\n"
        "5. Give a clear description.\n"
        "6. For topic_wise mode, generate a subject that supports multiple related questions.\n"
        "7. For daily_conversation mode, generate a realistic everyday situation.\n"
        "8. For speaking, include expected_duration_seconds.\n"
        "9. For writing, include minimum_word_count and maximum_word_count.\n"
        "10. Easy uses simple daily-life subjects; medium uses education, career, workplace and experience; hard uses professional, analytical or opinion-based subjects.\n"
        "11. If mode is daily_conversation, the title must be a realistic conversation situation, not an essay, debate or abstract subject.\n"
        "12. Daily easy examples: Talking About Your Morning, Meeting a Friend, Buying Food.\n"
        "13. Daily medium examples: Discussing Work Tasks, Planning a Trip, Talking About a College Project.\n"
        "14. Daily hard examples: Handling a Workplace Disagreement, Discussing a Project Delay, Explaining a Professional Decision, Giving Feedback in a Meeting.\n\n"
        "Return this JSON shape only:\n"
        '{"title":"Topic title","description":"Clear practice instruction","expected_duration_seconds":90,"minimum_word_count":null,"maximum_word_count":null}'
    )
    try:
        raw = _chat(system_prompt, user_prompt, temperature=0.85, operation=f"{practice_type}.topic_generation", module=practice_type, service="groq_common.generate_practice_topic")
        topic = _normalize_single_practice_topic(_extract_json(raw), practice_type, mode, difficulty)
        if topic["title"].lower() in {title.lower() for title in recent_topics}:
            raise ValueError("Groq repeated a recent topic")
        return topic
    except RuntimeError as exc:
        current_app.logger.warning("Practice topic generation unavailable: %s", exc)
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code if exc.response else "unknown"
        current_app.logger.warning("Groq practice topic HTTP error: %s", status_code)
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        current_app.logger.warning("Groq practice topic request failed: %s", exc.__class__.__name__)
    except (json.JSONDecodeError, ValueError):
        current_app.logger.warning("Groq returned invalid practice topic JSON", exc_info=True)
    except Exception:
        current_app.logger.exception("Unexpected practice topic generation failure")
    return fallback_practice_topic(practice_type, mode, difficulty, recent_topics)

def _clean_question(text):
    text = (text or "").strip().strip('"').strip("'")
    text = re.sub(r"^\s*(question\s*)?\d+[\).:-]\s*", "", text, flags=re.IGNORECASE)
    first = re.split(r"(?<=[?])\s+", text)[0].strip()
    return first if first.endswith("?") else first.rstrip(".!") + "?"


def _clamp_score(value, default=60):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = default
    return max(0, min(100, number))


def _score_average(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def _is_duplicate_question(question, previous_questions):
    normalized = re.sub(r"[^a-z0-9 ]+", "", (question or "").lower())
    for previous in previous_questions:
        other = re.sub(r"[^a-z0-9 ]+", "", (previous or "").lower())
        if normalized and other and SequenceMatcher(None, normalized, other).ratio() > 0.82:
            return True
    return False


import json
import re
import logging
import time
import random
from typing import List, Dict

from langchain_openai import ChatOpenAI
from openai import OpenAI

from cert_app.config import get_settings
from cert_app.db.database import get_cached_web_search_questions, save_cached_web_search_questions
from cert_app.services.usage_service import record_llm_usage

settings = get_settings()
logger = logging.getLogger(__name__)

_llm = None
_raw_client = None


def _get_raw_client() -> OpenAI:
    """Lazy-init the raw OpenAI SDK client (needed for the built-in web_search tool,
    which isn't exposed through the langchain ChatOpenAI wrapper)."""
    global _raw_client
    if _raw_client is None:
        _raw_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _raw_client


def _get_llm():
    """Lazy-initialize the OpenAI LLM so it always uses current settings."""
    global _llm
    if _llm is None:
        logger.info(f"[LLM] Initializing OpenAI LLM with model: {settings.OPENAI_MODEL}")
        _llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY,
            max_tokens=4096,
        )
    return _llm


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks produced by Qwen and similar models."""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


def _repair_json_string(clean: str) -> str:
    """Repair common LLM JSON formatting glitches:
    - Remove trailing commas before ] or }
    - Fix missing opening bracket in options array
    - Auto-close unclosed brackets/braces if response was truncated
    """
    clean = re.sub(r',\s*([\]}])', r'\1', clean)
    clean = re.sub(r'"options"\s*:\s*([^\["\s][^\]]*?\])', r'"options": [\1', clean)
    open_braces = clean.count('{') - clean.count('}')
    open_brackets = clean.count('[') - clean.count(']')
    if open_brackets > 0:
        clean += ']' * open_brackets
    if open_braces > 0:
        clean += '}' * open_braces
    return clean


def _extract_individual_questions(text: str) -> list[dict]:
    """Fallback extractor: recover individual question dicts using regex if full JSON parse fails."""
    questions = []
    pattern = re.compile(
        r'\{\s*"question"\s*:\s*".*?"\s*,\s*"options"\s*:\s*\[.*?\].*?\}',
        re.DOTALL
    )
    for match in pattern.finditer(text):
        try:
            block = _repair_json_string(match.group(0))
            obj = json.loads(block)
            if isinstance(obj, dict) and "question" in obj and "options" in obj:
                questions.append(obj)
        except Exception:
            continue
    return questions


def _extract_json(content: str) -> dict:
    """Try direct JSON parse first, then JSON repair, then regex extraction."""
    clean = _strip_think_tags(content)
    clean = re.sub(r'```json\s*', '', clean)
    clean = re.sub(r'```\s*', '', clean)
    clean = clean.strip()

    # 1. Direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # 2. Repaired parse
    try:
        repaired = _repair_json_string(clean)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 3. Regex extraction of outer {...}
    match = re.search(r'(\{.*\})', clean, re.DOTALL)
    if match:
        try:
            repaired = _repair_json_string(match.group(1))
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    # 4. Fallback: extract individual question objects directly from string
    recovered_qs = _extract_individual_questions(clean)
    if recovered_qs:
        logger.info(f"  [JSON Repair] Successfully recovered {len(recovered_qs)} individual question objects via regex")
        return {"questions": recovered_qs}

    raise ValueError(f"No valid JSON found in response: {clean[:200]}")


# ---------------------------------------------------------------------------
# Code-protection helpers
# ---------------------------------------------------------------------------

# Tokens that strongly indicate a code expression rather than plain prose.
# When found inside a question or option string, the token is wrapped in
# Markdown inline-code backticks so the frontend renderer cannot misinterpret
# ** as bold, _ as italic, etc.
# Multi-token code expressions containing operators (e.g. 2 ** 3 ** 2, a // b, x != y)
_EXPR_PATTERN = re.compile(
    r'(?<!`)\b(?:\d+|[a-zA-Z_]\w*)(?:\s*(?:\*\*|//|==|!=|<=|>=|\+=|-=|\*=|/=|->)\s*(?:\d+|[a-zA-Z_]\w*))+\b(?!`)'
)

# Single code elements: function calls foo(...), indexing arr[...], literals, or standalone operators
_ELEMENT_PATTERN = re.compile(
    r'(?<!`)(?:'
    r'\*\*|//|->|!=|==|<=|>=|\+=|-=|\*=|/=|'
    r'[a-zA-Z_]\w*\([^)]*\)|'
    r'[a-zA-Z_]\w*\[[^\]]+\]|'
    r'0x[0-9a-fA-F]+|0b[01]+|0o[0-7]+'
    r')(?!`)'
)


_STOPWORDS = {'the', 'a', 'an', 'is', 'are', 'operator', 'which', 'value', 'result', 'output', 'of', 'in', 'and', 'or', 'does', 'what', 'how'}


def _protect_code_in_text(text: str) -> str:
    """Wrap code expressions inside a string with Markdown inline-code backticks
    so that the frontend Markdown renderer displays them verbatim.

    Full code expressions like `2 ** 3 ** 2` or `a // b` are matched and wrapped
    together as a single backtick span (`2 ** 3 ** 2`).
    If an operator is surrounded by prose words (e.g., "the ** operator"),
    only the operator itself is wrapped (`**`).
    """
    if not text:
        return text

    def _replace_expr(match):
        expr = match.group(0)
        tokens = re.split(r'(\*\*|//|==|!=|<=|>=|\+=|-=|\*=|/=|->)', expr)
        left_words = set(re.findall(r'\b[a-zA-Z]+\b', tokens[0].lower()))
        right_words = set(re.findall(r'\b[a-zA-Z]+\b', tokens[-1].lower()))
        if (left_words & _STOPWORDS) or (right_words & _STOPWORDS):
            # Surrounded by English prose (e.g. "the ** operator") — wrap only the operator
            return re.sub(r'(\*\*|//|==|!=|<=|>=|\+=|-=|\*=|/=|->)', r'`\1`', expr)
        # Genuine code expression (e.g. 2 ** 3 ** 2) — wrap the whole expression
        return f'`{expr}`'

    # Step 1: Process multi-token expressions
    result = _EXPR_PATTERN.sub(_replace_expr, text)

    # Step 2: Wrap remaining standalone code elements outside existing backticks
    parts = result.split('`')
    for i in range(0, len(parts), 2):
        parts[i] = _ELEMENT_PATTERN.sub(lambda m: f'`{m.group(0)}`', parts[i])

    return '`'.join(parts)





def _validate_question(q: dict, source: str = '') -> bool:
    """Return True if the question is structurally sound and safe to ship.

    For MCQ questions (non-empty options list), correct_answer must appear
    verbatim in the options list.  Logs a WARNING for every failure so we
    can monitor LLM quality drift over time.
    """
    opts = q.get('options', [])
    ca = str(q.get('correct_answer', '')).strip()
    if opts and ca not in [str(o).strip() for o in opts]:
        logger.warning(
            f"[QValidation] {source} correct_answer {ca!r} not in options "
            f"{opts!r} — discarding: {str(q.get('question', ''))[:80]!r}"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_prompt(topic: str, count: int, difficulties: str, existing_questions: List[str] = None) -> str:
    """Build a single-batch question generation prompt."""
    avoid_str = ""
    if existing_questions:
        avoid_str = "\n\nCRITICAL: To ensure high quality, do NOT generate questions about these exact topics or questions (avoid duplication):\n" + "\n".join(f"- {q}" for q in existing_questions)

    return f"""You are an expert certification exam creator.
Generate exactly {count} multiple-choice certification questions about "{topic}".

Distribution: {difficulties}

Return ONLY a valid JSON object with a single key "questions" containing an array in this exact format (no markdown, no code blocks):
{{
  "questions": [
    {{
      "question": "Question text here?",
      "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
      "correct_answer": "Option 1",
      "expected_answer": "Brief explanation of why it is correct",
      "difficulty": "beginner"
    }}
  ]
}}

Important rules:
- Provide exactly 4 distinct options.
- The 'correct_answer' must perfectly match one of the strings in the 'options' array.
- Do NOT hallucinate formatting, only valid JSON.

Topic: {topic}{avoid_str}

IMPORTANT: Keep your thinking process extremely brief and short. Output the JSON as fast as possible."""


def _build_web_search_prompt(topic: str, count: int, difficulty: str = "mixed", existing_questions: List[str] = None) -> str:
    """Prompt that asks the model to actually use its web_search tool to find
    real, currently-circulating interview questions for the topic before
    writing MCQs, instead of relying only on its own trained-in knowledge."""
    avoid_str = ""
    if existing_questions:
        avoid_str = "\n\nDo NOT repeat or closely rephrase any of these already-used questions:\n" + \
            "\n".join(f"- {q}" for q in existing_questions)

    diff_clean = (difficulty or "mixed").strip().lower()
    diff_instruction = (
        "Mix difficulty across beginner, intermediate, and advanced."
        if diff_clean == "mixed"
        else f"Target difficulty: {diff_clean} level specifically."
    )

    return f"""You have a web_search tool. Use it now to search for real interview
questions and commonly-asked technical questions for the topic "{topic}".
Run at least 2 distinct searches, for example:
- "{topic} interview questions asked"
- "{topic} interview questions TCS Infosys Wipro Cognizant Accenture"
- "{topic} technical interview questions freshers experienced"

After reviewing what you find, write exactly {count} multiple-choice
certification questions for "{topic}", grounded in the real questions/themes
you found (rephrase into your own original wording — do not copy text
verbatim from any page). {diff_instruction}

Return ONLY a valid JSON object, no markdown, no code fences, in this exact
shape:
{{
  "questions": [
    {{
      "question": "Question text here?",
      "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
      "correct_answer": "Option 1",
      "expected_answer": "Brief explanation of why it is correct",
      "difficulty": "{diff_clean if diff_clean != 'mixed' else 'beginner'}"
    }}
  ]
}}

Rules:
- Provide exactly 4 distinct options per question.
- 'correct_answer' must exactly match one of the 'options' strings.
- Base the questions on what real candidates report being asked, not generic textbook trivia.
- Output only the JSON object, nothing before or after it.{avoid_str}"""


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------

def _call_web_search_llm(topic: str, count: int, difficulty: str = "mixed", existing_questions: List[str] = None) -> List[Dict]:
    """Generate `count` questions grounded in live web search results using
    OpenAI's Responses API + built-in web_search tool, or return from DB cache
    if recently generated. Returns [] on any failure so caller falls back to pure LLM."""
    s = get_settings()
    if not getattr(s, "ENABLE_WEB_SEARCH_QUESTIONS", True):
        return []

    diff_clean = (difficulty or "mixed").strip().lower()

    # 1. Try DB cache first
    ttl_hours = getattr(s, "WEB_SEARCH_CACHE_TTL_HOURS", 24)
    cached = get_cached_web_search_questions(topic, diff_clean, ttl_hours=ttl_hours)
    if cached:
        seen = set(str(q).strip().lower() for q in (existing_questions or []))
        valid_cached = [q for q in cached if str(q.get("question", "")).strip().lower() not in seen]
        if len(valid_cached) >= count:
            logger.info(f"  [WebSearchCache] Hit cache for topic='{topic}', difficulty='{diff_clean}': returning {count} questions from pool of {len(valid_cached)}")
            return random.sample(valid_cached, count)
        elif valid_cached:
            logger.info(f"  [WebSearchCache] Hit cache for topic='{topic}', difficulty='{diff_clean}': returning all {len(valid_cached)} cached questions")
            return valid_cached

    # 2. Live web search API call - request a larger pool (e.g. 15 items) to store in cache
    pool_size = max(count, getattr(s, "WEB_SEARCH_CACHE_POOL_SIZE", 15))
    prompt = _build_web_search_prompt(topic, pool_size, diff_clean, existing_questions)
    client = _get_raw_client()

    tool_variants = [{"type": "web_search"}, {"type": "web_search_preview"}]

    for tool in tool_variants:
        for attempt in range(1):
            try:
                logger.info(f"  [WebSearch] Attempt {attempt + 1} with tool={tool['type']}: requesting {pool_size} web-grounded questions pool for '{topic}' (difficulty: {diff_clean})")
                response = client.responses.create(
                    model=settings.OPENAI_MODEL,
                    tools=[tool],
                    input=prompt,
                    max_output_tokens=3072,
                )
                record_llm_usage("question_generation_web_search", response)
                content = getattr(response, "output_text", None) or str(response)
                parsed = _extract_json(content)
                questions_data = parsed.get("questions", [])
                validated = []
                for q in questions_data:
                    if 'question' not in q or 'options' not in q or 'correct_answer' not in q:
                        continue
                    candidate = {
                        "question": _protect_code_in_text(str(q['question'])),
                        "options": [_protect_code_in_text(str(o)) for o in q['options']],
                        "correct_answer": _protect_code_in_text(str(q['correct_answer'])),
                        "expected_answer": str(q.get('expected_answer', '')),
                        "difficulty": str(q.get('difficulty', (diff_clean if diff_clean != 'mixed' else 'intermediate'))),
                        "source": "web_search",
                    }
                    if _validate_question(candidate, source='web_search'):
                        validated.append(candidate)
                if validated:
                    logger.info(f"  [WebSearch] Got {len(validated)} web-grounded questions using tool={tool['type']}")
                    save_cached_web_search_questions(topic, diff_clean, validated)
                    sample_size = min(count, len(validated))
                    logger.info(f"  [WebSearchCache] Saved pool of {len(validated)} questions; sampling {sample_size} for current request")
                    return random.sample(validated, sample_size)
                logger.warning(f"  [WebSearch] Attempt {attempt + 1} ({tool['type']}): parsed but 0 valid questions")
            except Exception as e:
                logger.warning(f"  [WebSearch] Attempt {attempt + 1} ({tool['type']}) failed: {e}")
                # If the tool name itself is rejected, no point retrying it again.
                if "tool" in str(e).lower() and ("not supported" in str(e).lower() or "not enabled" in str(e).lower() or "invalid" in str(e).lower()):
                    break

    logger.warning(f"  [WebSearch] All attempts failed for '{topic}'; falling back to pure LLM questions")
    return []


def _call_llm_chunk(topic: str, count: int, difficulties: str, existing_questions: List[str] = None) -> List[Dict]:
    """Call the LLM for a small chunk of questions (up to 6 items per call)."""
    prompt = _build_prompt(topic, count, difficulties, existing_questions)
    llm = _get_llm()
    for attempt in range(3):
        try:
            logger.info(f"  Chunk call attempt {attempt + 1} for {count} questions ({difficulties})")
            response = llm.invoke(prompt)
            record_llm_usage("question_generation", response)
            content = response.content if hasattr(response, 'content') else str(response)
            try:
                parsed = _extract_json(content)
            except Exception as parse_err:
                logger.error(f"  [JSON Parse Failure] Raw Content from LLM:\n{content[:300]}\n[Parse Error]: {parse_err}")
                raise parse_err

            questions_data = parsed.get("questions", [])
            if isinstance(questions_data, list) and len(questions_data) > 0:
                validated = []
                for q in questions_data:
                    if 'question' not in q or 'options' not in q or 'correct_answer' not in q:
                        continue
                    candidate = {
                        "question": _protect_code_in_text(str(q['question'])),
                        "options": [_protect_code_in_text(str(o)) for o in q['options']],
                        "correct_answer": _protect_code_in_text(str(q['correct_answer'])),
                        "expected_answer": str(q.get('expected_answer', '')),
                        "difficulty": str(q.get('difficulty', 'beginner')),
                        "source": "llm"
                    }
                    if _validate_question(candidate, source='llm'):
                        validated.append(candidate)
                if validated:
                    logger.info(f"  Attempt {attempt + 1} succeeded: {len(validated)} valid questions")
                    return validated
                logger.warning(f"  Attempt {attempt + 1}: parsed but 0 valid questions from {len(questions_data)} items")
        except Exception as e:
            logger.warning(f"  Attempt {attempt + 1} failed: {e}")
    return []


def _call_llm_once(topic: str, count: int, difficulties: str, existing_questions: List[str] = None) -> List[Dict]:
    """Call the LLM and return validated questions. Automatically sub-batches if count > 6 to keep response latency low and prevent malformed output."""
    CHUNK_SIZE = 6
    if count <= CHUNK_SIZE:
        return _call_llm_chunk(topic, count, difficulties, existing_questions)

    all_questions: List[Dict] = []
    seen = set(str(q).strip().lower() for q in (existing_questions or []))

    while len(all_questions) < count:
        needed = min(count - len(all_questions), CHUNK_SIZE)
        existing_list = [q["question"] for q in all_questions] + (existing_questions or [])
        chunk_qs = _call_llm_chunk(topic, needed, difficulties, existing_list)
        if not chunk_qs:
            break
        added = 0
        for q in chunk_qs:
            txt = str(q.get("question", "")).strip().lower()
            if txt and txt not in seen:
                seen.add(txt)
                all_questions.append(q)
                added += 1
        if added == 0:
            break

    return all_questions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _web_search_question_count(num_questions: int, difficulty: str = "mixed") -> int:
    """How many of the total questions should come from live web search,
    per settings.WEB_SEARCH_QUESTION_RATIO, clamped to the configured
    min/max and never exceeding the exam size.
    Returns 0 if difficulty is 'beginner' to ensure pure LLM generation."""
    s = get_settings()
    if not getattr(s, "ENABLE_WEB_SEARCH_QUESTIONS", True):
        return 0
    if (difficulty or "mixed").strip().lower() == "beginner":
        logger.info("[WebSearch] Skipping web search phase for 'beginner' difficulty (using pure LLM generation)")
        return 0
    if num_questions < 10:
        return 0  # not worth a search call for tiny exams
    ratio_count = round(num_questions * getattr(s, "WEB_SEARCH_QUESTION_RATIO", 0.2))
    lo = getattr(s, "WEB_SEARCH_MIN_QUESTIONS", 5)
    hi = getattr(s, "WEB_SEARCH_MAX_QUESTIONS", 8)
    return max(lo, min(hi, ratio_count, num_questions))


def generate_questions(topic: str, num_questions: int = 30, difficulty: str = "mixed") -> List[Dict]:
    """
    Generate exactly `num_questions` certification questions for a topic.

    Strategy:
      1. Ask the web-search LLM for a portion (WEB_SEARCH_QUESTION_RATIO) to
         ground questions in real, currently-circulating interview content.
      2. Fill the remaining quota with the regular LLM in one batch.
      3. If either source underdelivers (LLM returned 28 instead of 30,
         web search returned 8 instead of 10, etc.), run additional backfill
         calls — up to MAX_BACKFILL_ROUNDS — requesting only the deficit,
         so we reliably return exactly num_questions rather than silently
         returning fewer.
      4. Deduplicate across all sources using exact question text matching.
      5. _protect_code_in_text() is applied at ingestion time in _call_llm_once
         and _call_web_search_llm, so every question in the bank is safe to
         render through a Markdown renderer.
      6. _validate_question() ensures correct_answer is always present in
         options before a question enters the bank; invalid ones are discarded
         and compensated for by the backfill loop.
    """
    MAX_BACKFILL_ROUNDS = 3

    logger.info(f"Generating {num_questions} questions for '{topic}' (difficulty: {difficulty})...")

    diff_lower = (difficulty or "mixed").strip().lower()

    all_questions: List[Dict] = []
    seen_texts: set = set()

    def _add_unique(candidates: List[Dict]) -> int:
        """Add candidates that aren't already in all_questions. Returns count added."""
        added = 0
        for q in candidates:
            text = str(q.get("question", "")).strip().lower()
            if text and text not in seen_texts:
                seen_texts.add(text)
                all_questions.append(q)
                added += 1
        return added

    # ── Phase 1: web-search grounded questions ──────────────────────────────────
    web_count = _web_search_question_count(num_questions, difficulty=diff_lower)
    if web_count > 0:
        logger.info(f"Requesting {web_count}/{num_questions} questions grounded in live web search for '{topic}' (difficulty: {diff_lower})")
        web_qs = _call_web_search_llm(topic, web_count, difficulty=diff_lower)
        got = _add_unique(web_qs)
        logger.info(f"  Web search delivered {got}/{web_count} unique questions")

    # ── Phase 2: LLM fill for the remainder ────────────────────────────────────
    if len(all_questions) < num_questions:
        deficit = num_questions - len(all_questions)
        existing_titles = [q["question"] for q in all_questions]
        diff_str = (
            f"{deficit} {diff_lower} questions"
            if diff_lower != "mixed"
            else f"{deficit} mixed difficulty questions"
        )
        logger.info(f"  LLM fill: requesting {deficit} questions")
        llm_qs = _call_llm_once(topic, deficit, diff_str, existing_titles)
        got = _add_unique(llm_qs)
        logger.info(f"  LLM fill delivered {got}/{deficit} unique questions (total so far: {len(all_questions)})")

    # ── Phase 3: backfill loop if still short ───────────────────────────────────
    for backfill_round in range(1, MAX_BACKFILL_ROUNDS + 1):
        if len(all_questions) >= num_questions:
            break

        deficit = num_questions - len(all_questions)
        logger.warning(
            f"  [Backfill {backfill_round}/{MAX_BACKFILL_ROUNDS}] "
            f"Still {deficit} question(s) short — requesting more from LLM"
        )
        existing_titles = [q["question"] for q in all_questions]
        diff_str = (
            f"{deficit} {diff_lower} questions"
            if diff_lower != "mixed"
            else f"{deficit} mixed difficulty questions"
        )
        llm_qs = _call_llm_once(topic, deficit, diff_str, existing_titles)
        got = _add_unique(llm_qs)
        logger.info(f"  Backfill {backfill_round} added {got} questions (total: {len(all_questions)})")

    # ── Final result ────────────────────────────────────────────────────────────
    final = all_questions[:num_questions]
    if len(final) < num_questions:
        logger.error(
            f"[FAIL] Could only generate {len(final)}/{num_questions} questions for '{topic}' "
            f"after {MAX_BACKFILL_ROUNDS} backfill rounds."
        )
        raise RuntimeError(
            f"Failed to generate {num_questions} questions for topic '{topic}' "
            f"(got {len(final)} after backfill)."
        )

    # Shuffle so web search questions do not all cluster at the start
    random.shuffle(final)

    logger.info(
        f"[OK] Generated exactly {len(final)} questions for '{topic}' "
        f"({sum(1 for q in final if q.get('source') == 'web_search')} web-grounded, "
        f"{sum(1 for q in final if q.get('source') != 'web_search')} LLM)."
    )
    return final

import json
import re
import logging
import time
import random
import difflib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import List, Dict, Iterable, Optional

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

    Fenced code blocks (```python ... ```) are already rendered verbatim by
    the frontend, so they are left untouched — wrapping tokens inside them
    would corrupt the snippet.
    """
    if not text:
        return text
    if "```" in text:
        parts = re.split(r'(```.*?```)', text, flags=re.DOTALL)
        return "".join(p if p.startswith("```") else _protect_inline_code(p) for p in parts)
    return _protect_inline_code(text)


def _protect_inline_code(text: str) -> str:
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

    Every question produced by this generator is meant to be a 4-option MCQ
    (both prompts require "exactly 4 distinct options"), but a mangled LLM
    response that only survives via _repair_json_string / regex recovery can
    come out with an options array truncated to 1-3 items. Require exactly 4
    non-empty, distinct options, and correct_answer must appear verbatim
    among them. Logs a WARNING for every failure so we can monitor LLM
    quality drift over time; the caller's backfill loop regenerates whatever
    gets discarded here.
    """
    opts = [str(o).strip() for o in q.get('options', [])]
    ca = str(q.get('correct_answer', '')).strip()
    if len(opts) != 4 or any(not o for o in opts) or len(set(opts)) != len(opts):
        logger.warning(
            f"[QValidation] {source} expected exactly 4 distinct non-empty options, got "
            f"{opts!r} — discarding: {str(q.get('question', ''))[:80]!r}"
        )
        return False
    if ca not in opts:
        logger.warning(
            f"[QValidation] {source} correct_answer {ca!r} not in options "
            f"{opts!r} — discarding: {str(q.get('question', ''))[:80]!r}"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def normalize_question_text(text: str) -> str:
    """Canonical form of a question used for duplicate detection: lower-case,
    punctuation/markdown stripped, whitespace collapsed. Code inside the
    question is kept, so two different snippets are never merged."""
    clean = re.sub(r'[^a-z0-9]+', ' ', str(text or '').lower())
    return re.sub(r'\s+', ' ', clean).strip()


class QuestionDeduper:
    """Rejects questions that were already used — either earlier in the same
    exam or in one of the learner's previous exams.

    Exact matches are caught after normalisation. Longer questions are also
    compared fuzzily so light rephrasings ("What does X do?" vs "What does X
    do in Python?") are caught, but only when both carry the same numbers —
    otherwise "output of 2 ** 3" and "output of 3 ** 2" would be merged.
    """

    _FUZZY_MIN_LEN = 50
    _FUZZY_RATIO = 0.9

    def __init__(self, seed: Optional[Iterable[str]] = None):
        self._exact: set = set()
        self._fuzzy: List[tuple] = []
        for text in seed or []:
            self.add(text)

    def is_duplicate(self, text: str) -> bool:
        norm = normalize_question_text(text)
        if not norm:
            return True
        if norm in self._exact:
            return True
        if len(norm) < self._FUZZY_MIN_LEN:
            return False
        digits = re.findall(r'\d+', norm)
        for other, other_digits in self._fuzzy:
            if other_digits != digits:
                continue
            matcher = difflib.SequenceMatcher(None, norm, other, autojunk=False)
            if matcher.real_quick_ratio() >= self._FUZZY_RATIO and matcher.quick_ratio() >= self._FUZZY_RATIO \
                    and matcher.ratio() >= self._FUZZY_RATIO:
                return True
        return False

    def add(self, text: str) -> bool:
        """Record `text`; returns False (and records nothing) if it is a duplicate."""
        if self.is_duplicate(text):
            return False
        norm = normalize_question_text(text)
        self._exact.add(norm)
        if len(norm) >= self._FUZZY_MIN_LEN:
            self._fuzzy.append((norm, re.findall(r'\d+', norm)))
        return True


# ---------------------------------------------------------------------------
# Practical (hands-on) topics
# ---------------------------------------------------------------------------

_PRACTICAL_DATA_KEYWORDS = (
    "data science", "data analytic", "data analysis", "analytics", "data engineer",
    "data visuali", "data mining", "pandas", "numpy", "sql", "statistic",
    "power bi", "tableau", "excel", "big data",
)


def is_practical_data_topic(topic: str) -> bool:
    """Data Science / Data Analytics style topics must be tested hands-on,
    not only with theory questions."""
    t = (topic or "").lower()
    return any(k in t for k in _PRACTICAL_DATA_KEYWORDS)


# Each parallel batch is steered to a different area so batches generated at
# the same time do not converge on the same handful of questions.
_GENERAL_FOCUS_AREAS = [
    "core concepts and definitions",
    "practical usage and common patterns",
    "debugging and troubleshooting scenarios",
    "best practices, performance and security",
    "real-world problem-solving scenarios",
    "edge cases and commonly misunderstood behaviour",
    "tools, libraries and ecosystem",
    "architecture and design decisions",
]

_DATA_FOCUS_AREAS = [
    "pandas data manipulation code — ask for the output/result of a short snippet",
    "SQL queries on a small inline table — ask for the result of the query",
    "statistics calculations on a small inline dataset (mean, median, std, percentiles, correlation)",
    "data cleaning in code — missing values, duplicates, type conversion, outliers",
    "NumPy / vectorised operations — ask for array shapes, values or the correct one-line code",
    "exploratory analysis and visualisation choices for a concrete business dataset",
    "aggregation, group-by, pivot and join problems with a concrete expected result",
    "core theory and concepts (keep this batch conceptual)",
]


def _focus_for(topic: str, index: int) -> str:
    areas = _DATA_FOCUS_AREAS if is_practical_data_topic(topic) else _GENERAL_FOCUS_AREAS
    return areas[index % len(areas)]


def _practical_instructions(topic: str, count: int) -> str:
    if not is_practical_data_topic(topic):
        return ""
    practical = max(1, (count + 1) // 2)
    return f"""

PRACTICAL REQUIREMENT (hands-on topic): at least {practical} of these {count} questions must be practical, not theory:
- Code-reading questions that include a short, self-contained Python (pandas / NumPy) or SQL snippet of 3-8 lines inside the question text as a fenced code block, e.g. "What is the output of the following code?\\n```python\\nimport pandas as pd\\ndf = pd.DataFrame({{'a': [1, 2, 3]}})\\nprint(df['a'].sum())\\n```". Ask for the output, the resulting shape/value, or which line causes an error.
- Code-writing questions ("Which code correctly ...?") where every option is ONE line of code wrapped in single backticks.
- Small data problems with a tiny inline dataset or table that require a calculation (average, growth %, group-by totals, rows after a join, etc.).
Rules for practical questions: snippets must be deterministic and runnable as written; the correct answer must be exactly what the code/data produces; inside JSON strings encode code line breaks as \\n; options must stay on a single line."""


def _trim_avoid_list(existing_questions: Optional[List[str]], limit: int = 40) -> List[str]:
    """Keep avoid-lists short: very long prompts slow generation down a lot,
    and uniqueness is enforced by QuestionDeduper afterwards anyway."""
    if not existing_questions:
        return []
    trimmed = []
    for q in list(existing_questions)[-limit:]:
        first_line = str(q).strip().split("\n", 1)[0]
        trimmed.append(first_line[:140])
    return trimmed


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_prompt(topic: str, count: int, difficulties: str, existing_questions: List[str] = None, focus: str = "") -> str:
    """Build a single-batch question generation prompt."""
    avoid_str = ""
    if existing_questions:
        avoid_str = "\n\nCRITICAL: To ensure high quality, do NOT generate questions about these exact topics or questions (avoid duplication):\n" + "\n".join(f"- {q}" for q in existing_questions)
    focus_str = f"\nFocus this batch on: {focus}." if focus else ""

    return f"""You are an expert certification exam creator.
Generate exactly {count} multiple-choice certification questions about "{topic}".

Distribution: {difficulties}{focus_str}{_practical_instructions(topic, count)}

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
verbatim from any page). {diff_instruction}{_practical_instructions(topic, count)}

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
        # The cache is shared by all learners, so drop anything this learner
        # has already been asked before sampling from it.
        seen = QuestionDeduper(existing_questions or [])
        valid_cached = [q for q in cached if not seen.is_duplicate(str(q.get("question", "")))]
        if len(valid_cached) >= count:
            logger.info(f"  [WebSearchCache] Hit cache for topic='{topic}', difficulty='{diff_clean}': returning {count} questions from pool of {len(valid_cached)}")
            return random.sample(valid_cached, count)
        elif valid_cached:
            logger.info(f"  [WebSearchCache] Hit cache for topic='{topic}', difficulty='{diff_clean}': returning all {len(valid_cached)} cached questions")
            return valid_cached

    # 2. Live web search API call - request a larger pool (e.g. 15 items) to store in cache
    pool_size = max(count, getattr(s, "WEB_SEARCH_CACHE_POOL_SIZE", 15))
    prompt = _build_web_search_prompt(topic, pool_size, diff_clean, _trim_avoid_list(existing_questions))
    client = _get_raw_client()
    # A hung web search must never hold the exam hostage.
    if hasattr(client, "with_options"):
        try:
            client = client.with_options(timeout=getattr(s, "WEB_SEARCH_TIMEOUT_SECONDS", 60))
        except Exception:
            pass

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
                    seen = QuestionDeduper(existing_questions or [])
                    validated = [q for q in validated if not seen.is_duplicate(q["question"])]
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


def _call_llm_chunk(topic: str, count: int, difficulties: str, existing_questions: List[str] = None, focus: str = "") -> List[Dict]:
    """Call the LLM for a small chunk of questions (up to 6 items per call)."""
    prompt = _build_prompt(topic, count, difficulties, existing_questions, focus)
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


_LLM_CHUNK_SIZE = 6
_MAX_PARALLEL_CHUNKS = 8


def _call_llm_once(topic: str, count: int, difficulties: str, existing_questions: List[str] = None, focus_offset: int = 0) -> List[Dict]:
    """Call the LLM and return validated, de-duplicated questions.

    Requests are split into chunks of 6 (keeps each response small and well
    formed) and the chunks run IN PARALLEL. Previously they ran one after
    another, so a 30-question exam waited for 5+ sequential LLM calls. Each
    parallel chunk is steered to a different focus area so they do not
    produce the same questions, and QuestionDeduper removes any overlap.
    """
    avoid = _trim_avoid_list(existing_questions)
    if count <= _LLM_CHUNK_SIZE:
        chunk_qs = _call_llm_chunk(topic, count, difficulties, avoid, _focus_for(topic, focus_offset))
        seen = QuestionDeduper(existing_questions or [])
        return [q for q in chunk_qs if seen.add(q.get("question", ""))]

    sizes = [_LLM_CHUNK_SIZE] * (count // _LLM_CHUNK_SIZE)
    if count % _LLM_CHUNK_SIZE:
        sizes.append(count % _LLM_CHUNK_SIZE)

    _get_llm()  # initialise the shared client once, before the worker threads start
    with ThreadPoolExecutor(max_workers=min(len(sizes), _MAX_PARALLEL_CHUNKS)) as pool:
        futures = [
            pool.submit(_call_llm_chunk, topic, size, difficulties, avoid, _focus_for(topic, focus_offset + i))
            for i, size in enumerate(sizes)
        ]
        chunk_results = []
        for future in futures:
            try:
                chunk_results.append(future.result())
            except Exception as e:
                logger.warning(f"  Parallel chunk failed: {e}")
                chunk_results.append([])

    seen = QuestionDeduper(existing_questions or [])
    all_questions: List[Dict] = []
    for chunk_qs in chunk_results:
        for q in chunk_qs:
            if seen.add(q.get("question", "")):
                all_questions.append(q)
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


_WEB_SEARCH_WAIT_SECONDS = 30


def _difficulty_label(diff_lower: str) -> str:
    if diff_lower == "mixed":
        return "mixed difficulty (a balance of beginner, intermediate and advanced)"
    return f"all questions at {diff_lower} level"


def generate_questions(
    topic: str,
    num_questions: int = 30,
    difficulty: str = "mixed",
    exclude_questions: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Generate exactly `num_questions` unique certification questions for a topic.

    Strategy:
      1. Start the web-search grounded request (WEB_SEARCH_QUESTION_RATIO of
         the exam) and the regular LLM fill AT THE SAME TIME. The LLM fill is
         itself split into parallel chunks, so total latency is roughly one
         LLM call instead of the sum of all calls.
      2. The LLM fill asks for a small buffer on top of the deficit so that
         questions dropped by validation/de-duplication rarely require a
         further round trip.
      3. Web-search results are waited for only for a bounded time; if the
         search is slow or fails, the backfill loop covers the deficit.
      4. `exclude_questions` holds questions this learner has already been
         asked in earlier exams. Every source is filtered against it (and
         against the questions already in this exam) with QuestionDeduper,
         so a learner never gets a repeated question.
      5. _protect_code_in_text() / _validate_question() are applied at
         ingestion time in the callers, exactly as before.
    """
    MAX_BACKFILL_ROUNDS = 3
    started = time.monotonic()

    logger.info(f"Generating {num_questions} questions for '{topic}' (difficulty: {difficulty})...")

    diff_lower = (difficulty or "mixed").strip().lower()
    diff_str = _difficulty_label(diff_lower)
    excluded = [str(q) for q in (exclude_questions or []) if str(q).strip()]

    all_questions: List[Dict] = []
    deduper = QuestionDeduper(excluded)

    def _add_unique(candidates: List[Dict]) -> int:
        """Add candidates that were not asked before and are not already in this exam."""
        added = 0
        for q in candidates:
            if len(all_questions) >= num_questions:
                break
            if deduper.add(str(q.get("question", ""))):
                all_questions.append(q)
                added += 1
        return added

    def _buffer(n: int) -> int:
        return n + max(2, (n + 5) // 6)

    web_count = _web_search_question_count(num_questions, difficulty=diff_lower)
    web_pool = None
    web_future = None
    if web_count > 0:
        logger.info(f"Requesting {web_count}/{num_questions} questions grounded in live web search for '{topic}' (difficulty: {diff_lower})")
        # Not a context manager: exiting one would block on the web-search
        # thread and remove the whole point of the bounded wait below.
        web_pool = ThreadPoolExecutor(max_workers=1)
        web_future = web_pool.submit(_call_web_search_llm, topic, web_count, diff_lower, excluded)

    try:
        # ── Phase 1: LLM fill (runs while the web search is in flight) ───────────
        llm_target = num_questions - web_count
        llm_qs: List[Dict] = []
        if llm_target > 0:
            logger.info(f"  LLM fill: requesting {llm_target} questions (+buffer) in parallel")
            llm_qs = _call_llm_once(topic, _buffer(llm_target), diff_str, excluded)

        # ── Phase 2: collect web-search questions (bounded wait) ──────────────────
        if web_future is not None:
            remaining = max(1.0, _WEB_SEARCH_WAIT_SECONDS - (time.monotonic() - started))
            try:
                web_qs = web_future.result(timeout=remaining)
            except FutureTimeoutError:
                logger.warning(f"  Web search still running after {_WEB_SEARCH_WAIT_SECONDS}s — continuing with LLM questions")
                web_qs = []
            except Exception as e:
                logger.warning(f"  Web search failed: {e}")
                web_qs = []
            got = _add_unique(web_qs)
            logger.info(f"  Web search delivered {got}/{web_count} unique questions")

        got = _add_unique(llm_qs)
        logger.info(f"  LLM fill delivered {got} unique questions (total so far: {len(all_questions)})")
    finally:
        if web_pool is not None:
            web_pool.shutdown(wait=False)

    # ── Phase 3: backfill loop if still short ───────────────────────────────────
    for backfill_round in range(1, MAX_BACKFILL_ROUNDS + 1):
        if len(all_questions) >= num_questions:
            break

        deficit = num_questions - len(all_questions)
        logger.warning(
            f"  [Backfill {backfill_round}/{MAX_BACKFILL_ROUNDS}] "
            f"Still {deficit} question(s) short — requesting more from LLM"
        )
        existing_titles = excluded + [q["question"] for q in all_questions]
        llm_qs = _call_llm_once(topic, _buffer(deficit), diff_str, existing_titles, focus_offset=backfill_round * 3)
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
        f"[OK] Generated exactly {len(final)} questions for '{topic}' in {time.monotonic() - started:.1f}s "
        f"({sum(1 for q in final if q.get('source') == 'web_search')} web-grounded, "
        f"{sum(1 for q in final if q.get('source') != 'web_search')} LLM)."
    )
    return final

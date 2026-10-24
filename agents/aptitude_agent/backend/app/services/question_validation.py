import hashlib
import re
from difflib import SequenceMatcher
from collections import Counter
from decimal import Decimal, InvalidOperation
from ..utils.security import clean_text
from ..utils.explanation import normalize_explanation
from ..utils.code_formatting import apply_structured_code_fields, canonicalize_unlabelled_fences, normalize_fenced_text, validate_fenced_code
from ..topic_config import CATEGORY_PRACTICE_TOPICS
from .role_topics import SKILL_TOPIC_RULES


INTERNAL_TOKEN_PATTERN=re.compile(
    r"\b(?:scenario[_\s-]?seed|variation[_\s-]?seed|batch[_\s-]?id|prompt[_\s-]?version)\b",
    re.IGNORECASE,
)
NUMBER_PATTERN=re.compile(
    r"(?<!\w)(?P<number>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*(?P<percent>%?)(?!\w)"
)


LOCAL_SUFFIX_PATTERN=re.compile(r"\s*\(\s*(?:local\s+practice|local\s+question)\s+[a-z0-9-]{4,}\s*\)\s*$",re.IGNORECASE)
UUID_SUFFIX_PATTERN=re.compile(r"\s*\(?[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\)?\s*$",re.IGNORECASE)
STOP_WORDS={"a","an","the","is","are","what","which","does","do","of","for","in","on","to","with","and","or","while","when","how","can","be","this","that","it","its","as","from","by"}
CONCEPT_PATTERNS={
    "ram":re.compile(r"\b(?:ram|random access memory)\b",re.IGNORECASE),
    "cpu-scheduling":re.compile(r"\b(?:cpu scheduling|cpu scheduler|process scheduling|time quantum)\b",re.IGNORECASE),
    "kernel":re.compile(r"\bkernel\b",re.IGNORECASE),
    "fifo-queue":re.compile(r"\b(?:first in first out|fifo|queue)\b",re.IGNORECASE),
}


CONCEPT_MAX_CONTENT_WORDS=8

_PLACEHOLDER_PATTERN = re.compile(
    r"(?:\[\s*(?:x|y|z|value|number|blank)\s*\]|\.{3,}|\?{2,}|\b(?:something|somebody|etc\.?|as follows)\b)",
    re.IGNORECASE,
)
_TOPIC_IDENTIFICATION_PLACEHOLDER = re.compile(
    r"\b(?:practice\s+item|assigned\s+topic|configured\s+topic|which\s+response\s+correctly\s+identifies|"
    r"assessment\s+dataset|in\s+slot\s+\d+|best\s+applies\s+to\s+.+\s+here)\b",
    re.IGNORECASE,
)
_QUESTION_START_PATTERN = re.compile(
    r"^(?:what|which|who|whom|where|when|why|how|is|are|does|do|can|could|should|find|choose|select|identify|determine|complete|calculate|consider|given)\b",
    re.IGNORECASE,
)
_ASSUMPTION_WORDS = re.compile(
    r"\b(?:average[- ]case|worst[- ]case|best[- ]case|amortized|undirected|directed|"
    r"one[- ]way|two[- ]way|per pair|only|without|assuming|when|under|given|"
    r"in this scenario|all other|relative order|search structure|index on)\b",
    re.IGNORECASE,
)


def _option_key(value):
    """Normalize an option enough to catch equivalent distractors."""
    normalized = _normalized_words(str(value or ""))
    # Numeric options such as ``50`` and ``50.0`` are the same answer.
    numeric = re.fullmatch(r"[-+]?\d+(?:\.\d+)?", normalized)
    if numeric:
        try:
            return f"number:{Decimal(numeric.group()).normalize():f}"
        except InvalidOperation:
            pass
    return normalized


def _validate_question_clarity(question, options, category):
    words = re.findall(r"[A-Za-z0-9]+", question)
    if len(words) < 5:
        raise ValueError("question is incomplete or too short")
    if _PLACEHOLDER_PATTERN.search(question):
        raise ValueError("question contains an unspecified placeholder or condition")
    if _TOPIC_IDENTIFICATION_PLACEHOLDER.search(question):
        raise ValueError("question is a topic-identification placeholder")
    if "?" not in question and not _QUESTION_START_PATTERN.search(question.strip()):
        raise ValueError("question is not a complete question")
    if any(_normalized_words(question) == _normalized_words(value) for value in options.values()):
        raise ValueError("question duplicates an answer option")


def _validate_saved_skill_alignment(question, options, explanation, slot):
    skill = str(slot.get("technical_skill") or "").strip()
    if not skill or slot.get("category") != "Technical Aptitude":
        return
    content = " ".join((question, *(str(value) for value in options.values()), explanation)).casefold()
    # Only aliases of the assigned skill are evidence.  Treating every saved
    # skill in technical_role_terms as evidence let a Power BI question pass a
    # Machine Learning slot merely because both skills belonged to the same
    # learner profile.
    aliases = (skill, *SKILL_TOPIC_RULES.get(skill.casefold(), ()))
    for term in aliases:
        if len(str(term).strip()) < 3:
            continue
        alias = re.escape(term.casefold()).replace(r"\ ", r"\s+")
        if re.search(rf"(?<![a-z0-9]){alias}(?![a-z0-9])", content):
            return
    raise ValueError("question does not explicitly assess its saved technical skill")


def _validate_assumptions_and_scope(question, options, category, topic):
    """Reject stems whose answer changes with an unstated interpretation."""
    text = question.casefold()
    assumptions = _ASSUMPTION_WORDS.search(question)
    topic_text = str(topic or "").casefold()
    option_text = " ".join(str(value) for value in options.values()).casefold()

    # Deterministic topic guardrails catch common model routing mistakes before
    # an item is accepted.  They are intentionally limited to strong signals;
    # broad conceptual questions still go through the normal prompt/schema
    # checks without being rejected for a shared keyword.
    strong_signals = {
        "oop": r"\b(?:class(?:es)?|object(?:s)?|inheritance|encapsulation|polymorphism|abstraction)\b",
        "testing": r"\b(?:unit test(?:ing)?|test case|assert(?:ion)?s?|regression test|test suite|mock(?:ing)?)\b",
        "loops": r"\b(?:for loop|while loop|loop iteration|iterate(?:s|d)? over)\b",
        "variables": r"\b(?:variable declaration|assign(?:s|ed)? a variable|data type of|mutable variable)\b",
    }
    topic_family = None
    if re.search(r"\b(?:oop|object[- ]oriented|four pillars)\b", topic_text): topic_family = "oop"
    elif re.search(r"\b(?:testing|debugging)\b", topic_text): topic_family = "testing"
    elif re.search(r"\b(?:loop|loops)\b", topic_text): topic_family = "loops"
    elif re.search(r"\b(?:variable|variables|data types)\b", topic_text): topic_family = "variables"
    if topic_family:
        conflicting = [name for name, pattern in strong_signals.items() if name != topic_family and re.search(pattern, question, re.IGNORECASE)]
        if conflicting:
            raise ValueError("question content does not match its configured topic")

    if ("improve database query performance" in text or "method to improve database" in text) and not re.search(
        r"\b(?:index|search structure|partition|normaliz|denormaliz)\b", text
    ):
        raise ValueError("database-performance question needs a specified mechanism")
    if re.search(r"\bwhich database query is faster\b", text) and not assumptions:
        raise ValueError("database-performance question needs a specified mechanism")
    if re.search(r"\b(?:beats|overtakes|passes)\b", text) and not re.search(
        r"\b(?:only|without|not\s+(?:also\s+)?\w+|all other|relative)\b", text
    ):
        raise ValueError("ranking question does not state which relative positions change")
    if "primary benefit" in text and not assumptions:
        raise ValueError("primary-benefit question needs a scenario or criterion")
    if "time complexity" in text and "hash table" in text and not re.search(
        r"\b(?:average|worst|best|amortized|collision|load factor)\b", text
    ):
        raise ValueError("hash-table complexity question needs a case or assumption")
    if "communicate with every other" in text and not re.search(
        r"\b(?:undirected|directed|one[- ]way|two[- ]way|pair|connection between)\b", text
    ):
        raise ValueError("connection-count question needs a directed or undirected model")
    if re.search(r"\bedges?\b", text) and re.search(r"\bgraph\b", text) and re.search(
        r"\bvertices?\b", text
    ) and not re.search(r"\b(?:complete|simple|undirected|directed|connected|tree|cycle|degree)\b", text):
        raise ValueError("graph edge question needs a specified graph structure")
    if "____" in question and re.search(r"\b(?:very|was|were|is|are)\b", text) and not assumptions:
        raise ValueError("fill-in-the-blank wording question lacks a distinguishing condition")

    # Topic labels are not enough: obvious domain signals must agree with the
    # configured topic. This catches SQL retrieval questions mislabeled as
    # graph or array questions while leaving broad conceptual questions alone.
    sql_signal = re.search(
        r"(?:\b(?:select|insert|update|delete|join|sql|query|table|database)\b|\bselect\b[\s\S]*\bfrom\b)",
        text,
    )
    if sql_signal and not re.search(r"\b(?:sql|database|query|relational|join|normaliz|transaction|index)\b", topic_text):
        raise ValueError("question content does not match its configured topic")
    graph_topic = re.search(r"\b(?:graph algorithms?|graph theory|graphs? traversal|graph data structures?)\b", topic_text)
    if graph_topic and not re.search(r"\b(?:graph|vertex|vertices|edge|path|travers|node)\b", text):
        raise ValueError("question content does not match its graph topic")
    if re.search(r"\barray", topic_text) and not re.search(
        r"\b(?:arrays?|lists?|indices|indexes?|elements?)\b", text
    ):
        raise ValueError("question content does not match its array topic")

    # Strong cross-domain signals must not be accepted under a different
    # saved-skill topic.  This catches the common provider drift seen in live
    # batches: a Power BI visualization question labelled Machine Learning.
    ml_topic = re.search(r"\b(?:machine learning|ml|model training|classification|regression)\b", topic_text)
    power_bi_topic = re.search(r"\b(?:power bi|data visualization|business intelligence)\b", topic_text)
    ml_signal = re.search(
        r"\b(?:machine learning|ml model|training dataset|test dataset|overfitting|classification|regression|"
        r"feature engineering|prediction|precision|recall|f1 score|clustering)\b", text,
    )
    power_bi_signal = re.search(
        r"\b(?:power bi|dashboard|slicer|dax|visualization|bar chart|line chart|report page)\b", text,
    )
    if ml_topic and power_bi_signal and not ml_signal:
        raise ValueError("question content does not match its configured topic")
    if power_bi_topic and ml_signal and not power_bi_signal:
        raise ValueError("question content does not match its configured topic")

    # A spelling polarity question must not mark a correctly spelled word as
    # the misspelling. The deterministic dictionary is intentionally small and
    # conservative; uncertain spelling items are rejected for regeneration.
    if "misspelled" in text or "incorrectly spelled" in text:
        known = {"receive", "separate", "necessary", "definitely", "accommodate", "embarrass", "occurrence", "recommend"}
        normalized = [re.sub(r"[^a-z]", "", value.casefold()) for value in options.values()]
        known_count = sum(value in known for value in normalized)
        verified = next((value for value in normalized if value in known), None)
        typo_count = sum(
            1 for value in normalized
            if verified and SequenceMatcher(None, value, verified).ratio() >= 0.65
        )
        if verified and typo_count != 1:
            raise ValueError("spelling question does not have exactly one verified misspelling")


def _validate_slot_metadata(item, slot):
    """Do not silently accept a model item for the wrong configured slot."""
    for field in ("category", "topic", "difficulty"):
        if field not in item or item[field] in (None, ""):
            continue
        actual = str(item[field]).strip()
        expected = str(slot[field]).strip()
        if actual.casefold() != expected.casefold():
            raise ValueError(f"generated {field} does not match the requested slot")
    category = str(slot.get("category") or "").strip()
    topic = str(slot.get("topic") or "").strip().casefold()
    configured = CATEGORY_PRACTICE_TOPICS.get(category)
    if configured is not None:
        known = {str(name).strip().casefold() for names in configured.values() for name in names}
        if topic not in known:
            raise ValueError("generated topic is not configured for the requested category")


def normalize_question_text(text):
    """Return a stable learner-facing representation used for duplicate checks."""
    value=(text or "").replace("\r", " ").replace("\n", " ")
    value=LOCAL_SUFFIX_PATTERN.sub("",value)
    value=UUID_SUFFIX_PATTERN.sub("",value)
    value=value.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    value=re.sub(r"[^\w\s]", " ", value.casefold(), flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def content_hash(text):
    return hashlib.sha256(normalize_question_text(text).encode()).hexdigest()


def questions_are_near_duplicates(left,right,threshold=.86):
    """Detect wording and common concept paraphrases without a heavy ML dependency."""
    first,second=normalize_question_text(left),normalize_question_text(right)
    if not first or not second:return False
    if first==second:return True
    if SequenceMatcher(None,first,second).ratio()>=threshold:return True
    first_words={word for word in first.split() if word not in STOP_WORDS}
    second_words={word for word in second.split() if word not in STOP_WORDS}
    if first_words and second_words and len(first_words&second_words)>=3:
        if len(first_words&second_words)/min(len(first_words),len(second_words))>=.75:return True
    # A concept match means "two definitional questions about the same thing"
    # (e.g. "What is the purpose of RAM?" / "What function does RAM perform?").
    # It used to fire for any two questions that merely mentioned a keyword
    # such as "queue" or "kernel", so long scenario questions rejected each
    # other. Only treat short questions as concept duplicates.
    if len(first_words)<=CONCEPT_MAX_CONTENT_WORDS and len(second_words)<=CONCEPT_MAX_CONTENT_WORDS:
        return any(pattern.search(first) and pattern.search(second) for pattern in CONCEPT_PATTERNS.values())
    return False


def numeric_pattern(text):
    """Return a stable multiset of typed numeric values used by a question."""
    values=[]
    for match in NUMBER_PATTERN.finditer(text or ""):
        raw=match.group("number").replace(",","")
        try:
            number=format(Decimal(raw).normalize(),"f")
        except InvalidOperation:
            number=raw
        if number in {"-0","-0.0"}:number="0"
        kind="percent" if match.group("percent") else "number"
        values.append(f"{kind}:{number}")
    return sorted(values)


def structural_hash(text,category,topic):
    """Fingerprint a numeric scenario without conflating unrelated categories/topics."""
    numbers=numeric_pattern(text)
    if len(numbers)<2:return None
    signature="|".join((category.casefold().strip(),topic.casefold().strip(),*numbers))
    return hashlib.sha256(signature.encode()).hexdigest()


def _normalized_words(value):
    return re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).strip()


def _states_correct_answer(explanation, option_text, answer_key):
    """Accept the option text itself or an explicit, matching option conclusion."""
    conclusion = explanation[-180:]
    explicit_correct_option=re.search(r"\b(?:option|choice)\s*([A-D])\s+is\s+correct\b",conclusion,re.IGNORECASE)
    if explicit_correct_option:return explicit_correct_option.group(1).upper()==answer_key
    # Treat A-D as an answer key only when it is the complete conclusion.
    # Values such as "A stack" and "C++" are option text, not bare keys.
    normalized_option = _normalized_words(option_text)
    explicit_key = re.search(
        r"\b(?:answer|correct\s+(?:answer|option|choice))\s*(?:is|=|:)?\s*(?:option\s*)?([A-D])\s*[.!]?\s*$",
        conclusion,re.IGNORECASE,
    )
    if explicit_key:
        concluded=explicit_key.group(1).upper()
        # Seating/ordering puzzles often label entities A-D as the option
        # *content* itself (e.g. correct_answer="B", options={"B": "A", ...}
        # -- "the answer is entity A"). A bare trailing letter is then the
        # concluded entity, not a selected option key, so it must be checked
        # against the option's own single-letter text, not just answer_key.
        if len(normalized_option)==1 and normalized_option in "abcd":
            return concluded==normalized_option.upper() or concluded==answer_key
        return concluded==answer_key
    normalized_explanation = _normalized_words(explanation)
    if normalized_option and re.search(rf"(?<!\w){re.escape(normalized_option)}(?!\w)", normalized_explanation):
        return True
    option_words=[word for word in normalized_option.split() if len(word)>=3 and word not in {"the","and","for","with","from","that","this","none"}]
    explanation_words=set(normalized_explanation.split())
    if option_words and len(set(option_words)&explanation_words)>=max(1,(len(set(option_words))+2)//3):return True
    acronym="".join(word[0] for word in option_words)
    if 2<=len(acronym)<=8 and re.search(rf"(?<!\w){re.escape(acronym)}(?!\w)",normalized_explanation):return True
    cue = re.search(r"\b(?:answer|correct\s+(?:answer|option|choice)|therefore|thus|hence|so)\b",conclusion,re.IGNORECASE)
    if not cue:return False
    option_numbers=set(re.findall(r"-?\d+(?:[.,]\d+)?%?",option_text))
    conclusion_numbers=set(re.findall(r"-?\d+(?:[.,]\d+)?%?",conclusion))
    if option_numbers:return option_numbers.issubset(conclusion_numbers)
    return True


def _has_redundant_repetition(explanation):
    """Catch repeated recalculations without trying to solve the question."""
    segments = [
        re.sub(r"^(?:step\s*)?\d+\s*[:.)-]\s*", "", part, flags=re.IGNORECASE).strip()
        for part in re.split(r"(?<=[.!?])\s+|(?=\bStep\s+\d+\s*:)", explanation, flags=re.IGNORECASE)
    ]
    segments = [segment for segment in segments if segment]
    normalized_segments = [_normalized_words(segment) for segment in segments]
    if any(count >= 3 for phrase, count in Counter(normalized_segments).items() if len(phrase) >= 12):
        return True

    words = _normalized_words(explanation).split()
    repeated_phrases = Counter(tuple(words[index:index + 5]) for index in range(max(0, len(words) - 4)))
    return any(count >= 3 for count in repeated_phrases.values())


def _has_self_correction(explanation):
    return bool(re.search(
        r"\b(?:however|on second thought|actual calculation|precise calculation|not (?:among|one of) the options|closest (?:given )?option|recalculat(?:e|ed|ing))\b",
        explanation,
        re.IGNORECASE,
    ))


_NUM=r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
# (left-operand pattern, right-operand pattern, op) for each supported phrasing,
# in the order (a, b) -> a OP b as written. Symbols and "plus/minus/..." read
# left-to-right; the imperative/passive forms ("Subtract A from B", "B minus
# A" said as "A subtracted from B") reorder the operands to match.
_ARITHMETIC_PATTERNS=(
    (re.compile(rf"({_NUM})\s*%\s*of\s*({_NUM})",re.IGNORECASE),lambda a,b:a/100*b),
    (re.compile(rf"({_NUM})\s*[+]\s*({_NUM})"),lambda a,b:a+b),
    (re.compile(rf"({_NUM})\s*plus\s*({_NUM})",re.IGNORECASE),lambda a,b:a+b),
    (re.compile(rf"({_NUM})\s*added\s+to\s*({_NUM})",re.IGNORECASE),lambda a,b:a+b),
    (re.compile(rf"add\s*({_NUM})\s*to\s*({_NUM})",re.IGNORECASE),lambda a,b:a+b),
    (re.compile(rf"({_NUM})\s*[-−]\s*({_NUM})"),lambda a,b:a-b),
    (re.compile(rf"({_NUM})\s*minus\s*({_NUM})",re.IGNORECASE),lambda a,b:a-b),
    (re.compile(rf"({_NUM})\s*subtracted\s+from\s*({_NUM})",re.IGNORECASE),lambda a,b:b-a),
    (re.compile(rf"subtract\s*({_NUM})\s*from\s*({_NUM})",re.IGNORECASE),lambda a,b:b-a),
    (re.compile(rf"({_NUM})\s*[*×xX]\s*({_NUM})"),lambda a,b:a*b),
    (re.compile(rf"({_NUM})\s*times\s*({_NUM})",re.IGNORECASE),lambda a,b:a*b),
    (re.compile(rf"({_NUM})\s*multiplied\s+by\s*({_NUM})",re.IGNORECASE),lambda a,b:a*b),
    (re.compile(rf"multiply\s*({_NUM})\s*by\s*({_NUM})",re.IGNORECASE),lambda a,b:a*b),
    (re.compile(rf"({_NUM})\s*[/÷]\s*({_NUM})"),lambda a,b:a/b if b else None),
    (re.compile(rf"({_NUM})\s*divided\s+by\s*({_NUM})",re.IGNORECASE),lambda a,b:a/b if b else None),
    (re.compile(rf"divide\s*({_NUM})\s*by\s*({_NUM})",re.IGNORECASE),lambda a,b:a/b if b else None),
)


def _derived_numbers(text):
    """Numbers actually reachable by evaluating the arithmetic written in
    `text` (e.g. `250 - 50` or the imperative `Subtract 50 from 250` both
    yield 200), in the same `numeric_pattern` format ("number:200").

    Real model output often narrates its last step in words instead of
    digits ("Subtract 50 from 250. Answer = 200") and never repeats the
    literal result before the answer line. Evaluating what the words say
    confirms that specific result was actually derived -- unlike merely
    checking that *some* calculation appears somewhere, this can't be
    fooled by an unrelated computation elsewhere in the explanation.
    """
    results=set()
    for pattern,op in _ARITHMETIC_PATTERNS:
        for match in pattern.finditer(text):
            try:
                a,b=(Decimal(group.replace(",","")) for group in match.groups())
                value=op(a,b)
            except (InvalidOperation,ZeroDivisionError):
                continue
            if value is None:continue
            results.add(f"number:{format(value.normalize(),'f')}")
    return results


_LOOSE_NUMBER=re.compile(
    r"(?<![\w.])(?P<number>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?:\s*%|[A-Za-z°²³]{1,6}(?![A-Za-z]))?"
)


def _plain_numbers(text):
    """Numeric values in `text` ignoring type: "40m", "40 m", "40" and "40%" all
    give "40". Used only to decide whether an answer's value was derived, where
    a unit or percent sign written on the option but not in the working
    (or the reverse) must not make a correct derivation look wrong."""
    values=set()
    for match in _LOOSE_NUMBER.finditer(text or ""):
        try:
            number=Decimal(match.group("number").replace(",",""))
        except InvalidOperation:
            continue
        values.add(format(number.normalize(),"f"))
    return values


def _has_matching_math_conclusion(explanation, option_text):
    steps=list(re.finditer(r"\bStep\s+\d+\s*:",explanation,re.IGNORECASE))
    if len(steps)<2:return False
    final_step=explanation[steps[-1].start():]
    # OpenAI follows the requested "Answer = …" format most of the time, but
    # a mathematically sound final step can also say "Therefore, the answer
    # is …" or "Thus, the correct answer is …".  Accept those equivalent
    # endings while still requiring the exact selected option and an earlier
    # derivation of its value.
    match=re.search(
        r"\b(?:answer|correct\s+answer|therefore|thus|hence|so)\b\s*(?:,?\s*(?:the\s+)?(?:correct\s+)?answer)?\s*(?:=|:|is)?\s*(.+?)\s*[.!]?$",
        final_step,
        re.IGNORECASE,
    )
    if not match:return False
    normalized_answer=_normalized_words(match.group(1))
    normalized_option=_normalized_words(option_text)
    if not (normalized_option and re.search(rf"(?<!\w){re.escape(normalized_option)}(?!\w)",normalized_answer)):return False
    # The model may put the last calculation immediately before "Answer ="
    # in the same numbered step. That is still a real derivation, so include
    # the part of the final step before the answer marker. Normalize numeric
    # formatting as well (for example, 1,250 and 1250 are the same value).
    preceding_steps=explanation[:steps[-1].start()]
    derivation_text=f"{preceding_steps} {final_step[:match.start()]}"
    option_numbers=set(numeric_pattern(option_text))
    known_numbers=set(numeric_pattern(derivation_text))|_derived_numbers(derivation_text)
    if option_numbers and option_numbers.issubset(known_numbers):return True
    option_values=_plain_numbers(option_text)
    if option_values:
        known_values={value.split(":",1)[1] for value in known_numbers}|_plain_numbers(derivation_text)
        return option_values.issubset(known_values)
    return bool(re.search(rf"(?<!\w){re.escape(normalized_option)}(?!\w)",_normalized_words(derivation_text)))


def _question_arithmetic_result(question):
    """Solve the small, explicit arithmetic stems commonly produced for MCQs.

    This is deliberately conservative: returning ``None`` means the stem is
    left to the normal explanation and model validation rather than guessed by
    the application.
    """
    text = str(question or "")
    number = r"(-?\d+(?:\.\d+)?)"
    patterns = (
        (rf"{number}\s*%\s*of\s*{number}", lambda a, b: a / 100 * b),
        (rf"{number}\s*\+\s*{number}", lambda a, b: a + b),
        (rf"{number}\s+plus\s+{number}", lambda a, b: a + b),
        (rf"{number}\s*-\s*{number}", lambda a, b: a - b),
        (rf"{number}\s+minus\s+{number}", lambda a, b: a - b),
        (rf"subtract\s+{number}\s+from\s+{number}", lambda a, b: b - a),
        (rf"{number}\s+times\s+{number}", lambda a, b: a * b),
        (rf"{number}\s*[x×]\s*{number}", lambda a, b: a * b),
        (rf"{number}\s+divided\s+by\s+{number}", lambda a, b: a / b if b else None),
    )
    for pattern, operation in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        try:
            value = operation(Decimal(match.group(1)), Decimal(match.group(2)))
        except (InvalidOperation, ZeroDivisionError):
            return None
        if value is not None:
            return value.normalize()
    return None


def _validate_explicit_arithmetic_answer(question, options, answer):
    expected = _question_arithmetic_result(question)
    if expected is None:
        return
    matching = []
    for key, value in options.items():
        candidate = re.search(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", str(value))
        if not candidate:
            continue
        try:
            if Decimal(candidate.group()).normalize() == expected:
                matching.append(key)
        except InvalidOperation:
            continue
    # A stem with exactly one numeric option has an independently verifiable
    # key. Reject both wrong keys and ambiguous duplicate numeric answers.
    if not matching:
        raise ValueError("question has no option matching its calculable result")
    if len(matching) == 1 and matching[0] != answer:
        raise ValueError("answer key does not match the calculable question result")
    if len(matching) > 1:
        raise ValueError("question has multiple options matching its calculable result")


def validate_generated_item(item, slot, internal_values=()):
    selected_language=str(slot.get("technical_language") or "python").lower()
    if not isinstance(item, dict):
        raise ValueError("generated question must be an object")
    _validate_slot_metadata(item, slot)
    item=apply_structured_code_fields(item,slot["category"],selected_language)
    required = {"question","options","correct_answer","explanation","category","topic","difficulty"}
    if not isinstance(item, dict) or not required.issubset(item): raise ValueError("missing required fields")
    options = item["options"]
    if not isinstance(options, dict) or set(options) != {"A","B","C","D"}: raise ValueError("options must be A-D")
    technical=slot["category"]=="Technical Aptitude"
    if technical:
        # Validate before prose normalization: clean_text folds newlines and
        # can otherwise hide an unfenced multi-line program.
        for value in (item["question"],*options.values(),item["explanation"]):
            validate_fenced_code(canonicalize_unlabelled_fences(value,selected_language),selected_language)
    options = {
        key:(normalize_fenced_text(canonicalize_unlabelled_fences(value,selected_language),500) if technical else clean_text(value,500))
        for key,value in options.items()
    }
    option_keys = [_option_key(value) for value in options.values()]
    if any(not value for value in options.values()) or len(set(option_keys)) != 4: raise ValueError("options must be unique and non-empty")
    answer = clean_text(item["correct_answer"],1).upper()
    if answer not in options: raise ValueError("invalid answer key")
    question = normalize_fenced_text(canonicalize_unlabelled_fences(item["question"],selected_language),2000) if technical else clean_text(item["question"],2000)
    explanation = (
        normalize_fenced_text(canonicalize_unlabelled_fences(item["explanation"],selected_language),3000,normalize_explanation)
        if technical else normalize_explanation(item["explanation"],3000)
    )
    if technical:
        for value in (question,*options.values(),explanation):
            validate_fenced_code(value,selected_language)
    public_text="\n".join((question,*options.values(),explanation))
    if INTERNAL_TOKEN_PATTERN.search(public_text):raise ValueError("generated content exposes an internal prompt token")
    exposed_values=[str(value).strip() for value in internal_values if len(str(value).strip())>=4]
    if any(value.casefold() in public_text.casefold() for value in exposed_values):raise ValueError("generated content exposes an internal seed value")
    _validate_question_clarity(question, options, slot["category"])
    _validate_saved_skill_alignment(question, options, explanation, slot)
    _validate_assumptions_and_scope(question, options, slot["category"], slot.get("topic"))
    if len(question) < 12 or len(explanation) < 10: raise ValueError("question or explanation too short")
    if len(explanation) > 600: raise ValueError("explanation exceeds 600 characters")
    # "Answer = $5.00." alone (an empty reason from the model) taught nothing
    # and printed as the whole explanation in the PDF. Everything before the
    # final "Answer =" must actually say why.
    reasoning=re.sub(r"\bAnswer\s*=.*$","",explanation,flags=re.IGNORECASE|re.DOTALL)
    # A shown calculation ("Males = 60% of 200 = 120") also explains a numeric
    # caselet or chart answer, even in fewer words. It must be a real operation
    # between numbers, not just "= 120" restating the answer.
    shows_calculation=bool(re.search(r"\d\s*(?:[-+*/×÷x]|%\s*of)\s*\$?\d",reasoning))
    words=len(re.findall(r"[A-Za-z]{2,}",reasoning))
    if slot["category"]!="Quantitative Aptitude" and words<6 and not shows_calculation: raise ValueError("explanation must explain why the answer is correct, not only state the answer")
    if _has_self_correction(explanation): raise ValueError("explanation contains self-correction or option guessing")
    if _has_redundant_repetition(explanation): raise ValueError("explanation redundantly repeats a calculation or phrase")
    if not _states_correct_answer(explanation,options[answer],answer): raise ValueError("explanation does not support the correct answer")
    _validate_explicit_arithmetic_answer(question, options, answer)
    option_has_number=bool(re.search(r"-?\d+(?:[.,]\d+)?%?",options[answer]))
    uses_steps=bool(re.search(r"\bStep\s+\d+\s*:",explanation,re.IGNORECASE))
    # Only quantitative questions require a formal calculated conclusion.
    # Reasoning questions can legitimately use numbered logic steps and a
    # numeric option without being a mathematical derivation.
    if slot["category"]=="Quantitative Aptitude" and not _has_matching_math_conclusion(explanation,options[answer]): raise ValueError("structured explanation must derive and end with the matching answer")
    return {**slot,"question":question,"options":options,"correct_answer":answer,"explanation":explanation,"content_hash":content_hash(question),"structural_hash":structural_hash(question,slot["category"],slot["topic"])}

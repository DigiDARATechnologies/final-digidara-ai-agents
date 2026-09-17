import hashlib
import re
from difflib import SequenceMatcher
from collections import Counter
from decimal import Decimal, InvalidOperation
from ..utils.security import clean_text
from ..utils.explanation import normalize_explanation
from ..utils.code_formatting import apply_structured_code_fields, canonicalize_unlabelled_fences, normalize_fenced_text, validate_fenced_code


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
    return any(pattern.search(first) and pattern.search(second) for pattern in CONCEPT_PATTERNS.values())


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
    explicit_key = re.search(
        r"\b(?:answer|correct\s+(?:answer|option|choice))\s*(?:is|=|:)?\s*(?:option\s*)?([A-D])\s*[.!]?\s*$",
        conclusion,re.IGNORECASE,
    )
    if explicit_key:return explicit_key.group(1).upper()==answer_key
    normalized_explanation = _normalized_words(explanation)
    normalized_option = _normalized_words(option_text)
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
    preceding_numbers=set(numeric_pattern(derivation_text))
    if option_numbers:return option_numbers.issubset(preceding_numbers)
    return bool(re.search(rf"(?<!\w){re.escape(normalized_option)}(?!\w)",_normalized_words(derivation_text)))


def validate_generated_item(item, slot, internal_values=()):
    selected_language=str(slot.get("technical_language") or "python").lower()
    item=apply_structured_code_fields(item,slot["category"],selected_language)
    required = {"question","options","correct_answer","explanation","category","topic","difficulty"}
    if not isinstance(item, dict) or not required.issubset(item): raise ValueError("missing required fields")
    options = item["options"]
    if not isinstance(options, dict) or set(options) != {"A","B","C","D"}: raise ValueError("options must be A-D")
    technical=slot["category"]=="Technical Aptitude"
    options = {
        key:(normalize_fenced_text(canonicalize_unlabelled_fences(value,selected_language),500) if technical else clean_text(value,500))
        for key,value in options.items()
    }
    if any(not value for value in options.values()) or len({value.casefold() for value in options.values()}) != 4: raise ValueError("options must be unique and non-empty")
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
    if len(question) < 12 or len(explanation) < 10: raise ValueError("question or explanation too short")
    if len(explanation) > 600: raise ValueError("explanation exceeds 600 characters")
    if _has_self_correction(explanation): raise ValueError("explanation contains self-correction or option guessing")
    if _has_redundant_repetition(explanation): raise ValueError("explanation redundantly repeats a calculation or phrase")
    if not _states_correct_answer(explanation,options[answer],answer): raise ValueError("explanation does not support the correct answer")
    option_has_number=bool(re.search(r"-?\d+(?:[.,]\d+)?%?",options[answer]))
    uses_steps=bool(re.search(r"\bStep\s+\d+\s*:",explanation,re.IGNORECASE))
    # Only quantitative questions require a formal calculated conclusion.
    # Reasoning questions can legitimately use numbered logic steps and a
    # numeric option without being a mathematical derivation.
    if slot["category"]=="Quantitative Aptitude" and not _has_matching_math_conclusion(explanation,options[answer]): raise ValueError("structured explanation must derive and end with the matching answer")
    return {**slot,"question":question,"options":options,"correct_answer":answer,"explanation":explanation,"content_hash":content_hash(question),"structural_hash":structural_hash(question,slot["category"],slot["topic"])}

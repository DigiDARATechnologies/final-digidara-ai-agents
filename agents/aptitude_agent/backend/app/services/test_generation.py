import json
import random
import secrets
import time
import uuid
from decimal import Decimal, InvalidOperation
from flask import current_app
from .ai_service import AIProviderError, empty_usage, json_completion, merge_usage
ProviderError = AIProviderError
from .question_validation import content_hash, structural_hash, numeric_pattern, validate_generated_item, questions_are_near_duplicates, INTERNAL_TOKEN_PATTERN
from ..utils.security import clean_text
from ..utils.explanation import normalize_explanation
from ..utils.code_formatting import apply_structured_code_fields, canonicalize_unlabelled_fences, normalize_fenced_text, validate_fenced_code
from ..topic_config import (
    CATEGORY_TOPIC_CONFIG,select_rotating_topic_names,
    select_weighted_topic_names,topic_definitions_for,
)

CATEGORIES={
    category:tuple(item["name"] for item in topic_definitions_for(category))
    for category in CATEGORY_TOPIC_CONFIG
}
DISTRIBUTION = [5,4,3,3,3,3]
DIFFICULTIES = ["Easy"]*6 + ["Medium"]*10 + ["Hard"]*4
CATEGORY_LEVELS={"Beginner":"Easy","Intermediate":"Medium","Advanced":"Hard"}
CATEGORY_PRACTICE_QUESTION_COUNT=10
TECHNICAL_LANGUAGES=("C","Java","Python","SQL")
DEFAULT_TECHNICAL_LANGUAGE="Python"

RETRY_VARIATION_DIRECTIONS = (
    "Use a different real-world setting, different entities, and a different question structure.",
    "Test a different facet of the assigned topic and use a new scenario with different relationships.",
    "Use a different representation or reasoning path; for numeric questions also use a different numeric range.",
)


def _normalized_exclusions(questions):
    """Build the single exclusion set shared by the prompt and validator."""
    normalized=[]
    seen=set()
    for question in questions or []:
        value=clean_text(question,360)
        key=value.casefold()
        if value and key not in seen:
            normalized.append(value)
            seen.add(key)
    return normalized


def _candidate_question_texts(items):
    questions=[]
    for item in items if isinstance(items,list) else []:
        if not isinstance(item,dict):
            continue
        question=clean_text(item.get("question"),360)
        if question and question.casefold() not in {row.casefold() for row in questions}:
            questions.append(question)
    return questions


def _extract_question_items(payload,expected_count):
    """Canonicalize common JSON wrappers without relaxing item validation.

    Provider JSON mode guarantees a JSON object, but it does not guarantee the
    application-level wrapper. In particular, a one-question request may be
    returned as ``{"question": {...}}``, ``{"questions": {...}}``, or as
    the question object itself. Accept those singleton shapes and let the
    existing strict question validator remain authoritative.
    """
    if not isinstance(payload,dict):
        return [],"non_object"
    questions=payload.get("questions")
    if isinstance(questions,list):
        return questions,"questions_array"
    if expected_count==1:
        if isinstance(questions,dict):
            return [questions],"questions_object"
        question=payload.get("question")
        if isinstance(question,dict):
            return [question],"question_object"
        required={"question","options","correct_answer","explanation","category","topic","difficulty"}
        if required.issubset(payload):
            return [payload],"bare_question_object"
    return [],"unsupported_wrapper"


def _retry_context(base_prompt,error,rejected_questions,attempt):
    direction=RETRY_VARIATION_DIRECTIONS[(attempt-1)%len(RETRY_VARIATION_DIRECTIONS)]
    retry_seed=f"{secrets.randbelow(900000)+100000}-{str(uuid.uuid4())[:8]}"
    return f"""{base_prompt}

RETRY CORRECTION {attempt}: The previous response was rejected because {clean_text(str(error),240)}.
Return the complete exact-count array again. Use a {direction} variation and private retry seed {retry_seed}.
Never mention the retry, rejected output, or seed."""


def _batch_response_schema(slots):
    """Strict response shape; exact array size prevents partial batches."""
    count=len(slots)
    option={"type":"string","minLength":1,"maxLength":140}
    code_value={"anyOf":[
        {"type":"object","properties":{"language":{"type":"string","enum":["c","java","python","sql"]},"code":{"type":"string","minLength":1,"maxLength":500}},"required":["language","code"],"additionalProperties":False},
        {"type":"null"},
    ]}
    return {
        "type":"object",
        "properties":{
            "questions":{
                "type":"array","minItems":count,"maxItems":count,
                "items":{
                    "type":"object",
                    "properties":{
                        "question":{"type":"string","minLength":12,"maxLength":280,"description":"A concise self-contained MCQ stem. Quantitative stems must ask a directly calculable value."},
                        "correct_option":{**option,"description":"The complete text of the one correct option."},
                        "distractors":{"type":"array","minItems":3,"maxItems":3,"items":option,"description":"Exactly three distinct incorrect options."},
                        "reason":{"type":"string","maxLength":220,"description":"For non-quantitative questions, one concise reason supporting correct_option. Empty for quantitative questions."},
                        "calculation_step_1":{"type":"string","maxLength":140,"description":"For quantitative questions, show the first numeric calculation with digits. Empty otherwise."},
                        "calculation_step_2":{"type":"string","minLength":1,"maxLength":140,"description":"For quantitative questions, explicitly calculate the final numeric value and include the exact digits and formatting of correct_option. Example correct_option 50: `20% of 250 = 50`. Empty otherwise."},
                        "question_code":{**code_value,"description":"Raw source code for a Technical Aptitude stem, or null. Never include Markdown fences."},
                        "correct_option_code":{**code_value,"description":"Raw source code for correct_option, or null."},
                        "distractor_codes":{"type":"array","minItems":3,"maxItems":3,"items":code_value,"description":"Code matching each distractor, normally three null values."},
                        "category":{"type":"string","enum":list(dict.fromkeys(slot["category"] for slot in slots))},
                        "topic":{"type":"string","enum":list(dict.fromkeys(slot["topic"] for slot in slots))},
                        "difficulty":{"type":"string","enum":["Easy","Medium","Hard"]},
                    },
                    "required":["question","correct_option","distractors","reason","calculation_step_1","calculation_step_2","question_code","correct_option_code","distractor_codes","category","topic","difficulty"],
                    "additionalProperties":False,
                },
            },
        },
        "required":["questions"],"additionalProperties":False,
    }


def _canonicalize_batch_item(item,slot):
    """Build the public A-D shape while preserving strict answer validation."""
    if isinstance(item,dict) and {"options","correct_answer","explanation"}.issubset(item):
        return item
    if not isinstance(item,dict):
        raise ValueError("question item must be an object")
    correct=clean_text(item.get("correct_option"),140)
    distractors=item.get("distractors")
    if not correct or not isinstance(distractors,list) or len(distractors)!=3:
        raise ValueError("correct option and exactly three distractors are required")
    choices=[correct,*[clean_text(value,140) for value in distractors]]
    if any(not value for value in choices) or len({value.casefold() for value in choices})!=4:
        raise ValueError("correct option and distractors must be distinct and non-empty")
    question=clean_text(item.get("question"),280)
    offset=int(content_hash(question)[:2],16)%4
    ordered=choices[1:]
    ordered.insert(offset,correct)
    options=dict(zip("ABCD",ordered))
    answer="ABCD"[offset]
    distractor_codes=item.get("distractor_codes")
    if not isinstance(distractor_codes,list) or len(distractor_codes)!=3:
        raise ValueError("exactly three distractor code values are required")
    ordered_codes=list(distractor_codes)
    ordered_codes.insert(offset,item.get("correct_option_code"))
    option_code={key:value for key,value in zip("ABCD",ordered_codes) if value is not None}
    if slot["category"]=="Quantitative Aptitude":
        step_1=clean_text(item.get("calculation_step_1"),140)
        step_2=clean_text(item.get("calculation_step_2"),140)
        derived_numbers=set(numeric_pattern(f"{step_1} {step_2}"))
        option_numbers=set(numeric_pattern(correct))
        # Allow harmless formatting differences such as 50 versus 50.0 while
        # still requiring the same numeric value and percent/absolute kind.
        def numeric_key(token):
            kind,value=token.split(":",1)
            try:
                return kind,format(Decimal(value).normalize(),"f")
            except InvalidOperation:
                return token
        derived_keys={numeric_key(value) for value in derived_numbers}
        option_keys={numeric_key(value) for value in option_numbers}
        if option_numbers and not option_keys.issubset(derived_keys):
            raise ValueError("quantitative calculation does not derive correct option")
        step_2_keys={numeric_key(value) for value in numeric_pattern(step_2)}
        if option_numbers and not option_keys.issubset(step_2_keys):
            step_2=f"{step_2.rstrip('.')} = {correct}."
        explanation=f"Step 1: {step_1}\nStep 2: {step_2}\nStep 3: Answer = {correct}."
    else:
        reason=clean_text(item.get("reason"),220)
        explanation=f"{reason} Answer = {correct}."
    return {**item,"question":question,"options":options,"correct_answer":answer,"explanation":explanation,"option_code":option_code}


def _topic_sequence(topics,count,rng):
    """Return a shuffled topic sequence, repeating only when unavoidable."""
    available=list(dict.fromkeys(topics))
    if not available:raise ValueError("Choose at least one aptitude topic")
    if len(available)>=count:return rng.sample(available,count)
    selected=[]
    while len(selected)<count:
        cycle=list(available);rng.shuffle(cycle)
        if len(cycle)>1 and selected and cycle[0]==selected[-1]:
            cycle[0],cycle[1]=cycle[1],cycle[0]
        selected.extend(cycle)
    return selected[:count]


def _topic_rng(seed=None):
    # SystemRandom varies standalone calls. A test-id seed lets the live
    # question flow reconstruct one stable schedule throughout an attempt.
    return random.SystemRandom() if seed is None else random.Random(str(seed))


def _slot(category,topic,difficulty,technical_language=None):
    row={"category":category,"topic":topic,"difficulty":difficulty}
    if category=="Technical Aptitude":
        row["technical_language"]=technical_language or DEFAULT_TECHNICAL_LANGUAGE
    return row


def build_slots(category=None,seed=None,category_counts=None,technical_language=None,topics_by_category=None):
    rng=_topic_rng(seed)
    if category:
        difficulties=["Easy","Easy","Medium","Medium","Hard"]
        selected=select_rotating_topic_names(topic_definitions_for(category),[],len(difficulties),rng)
        return [_slot(category,topic,difficulty,technical_language) for topic,difficulty in zip(selected,difficulties)]
    slots=[]
    configured_counts=(
        [int(category_counts.get(name,0)) for name in CATEGORIES]
        if category_counts is not None else DISTRIBUTION
    )
    if category_counts is not None and any(count < 3 or count > 10 for count in configured_counts):
        raise ValueError("Every Mixed Test category must have between 3 and 10 questions")
    for category,count in zip(CATEGORIES,configured_counts):
        supplied=(topics_by_category or {}).get(category)
        if supplied is not None:
            selected=list(supplied[:count])
            if len(selected)!=count or len({topic.casefold() for topic in selected})!=count:
                raise ValueError(f"Mixed Test topic schedule is invalid for {category}")
        else:
            selected=select_rotating_topic_names(topic_definitions_for(category),[],count,rng)
        for topic in selected:slots.append(_slot(category,topic,None,technical_language))
    slots.sort(key=lambda row:len(row["topic"])%7)
    for i,slot in enumerate(slots):slot["difficulty"]=DIFFICULTIES[i%len(DIFFICULTIES)]
    return slots


def build_category_slots(category,level,topics=None,seed=None,technical_language=None):
    if category not in CATEGORIES:raise ValueError("Choose a valid aptitude category")
    if level not in CATEGORY_LEVELS:raise ValueError("Choose Beginner, Intermediate or Advanced")
    # Explicit topics are already a history-aware attempt schedule selected by
    # topic_selection_service, so preserve their order. Direct callers receive
    # a newly shuffled schedule rather than the former fixed modulo walk.
    topics=(list(topics) if topics is not None else select_weighted_topic_names(
        topic_definitions_for(category),[],CATEGORY_PRACTICE_QUESTION_COUNT,_topic_rng(seed),
    ))
    if not topics:raise ValueError("Choose at least one Category Practice topic")
    difficulty=CATEGORY_LEVELS[level]
    return [_slot(category,topics[index%len(topics)],difficulty,technical_language) for index in range(CATEGORY_PRACTICE_QUESTION_COUNT)]


def _minimal_safe_item(item,slot,internal_values=()):
    """Return a structurally safe last candidate for a deadline fallback.

    Full validation remains authoritative. This deliberately narrow fallback
    is used only after the learner-facing deadline expires and still rejects
    malformed options, metadata leaks, and slot mismatches.
    """
    selected_language=str(slot.get("technical_language") or "python").lower()
    try:item=apply_structured_code_fields(item,slot["category"],selected_language)
    except ValueError:return None
    required={"question","options","correct_answer","explanation","category","topic","difficulty"}
    if not isinstance(item,dict) or not required.issubset(item):return None
    options=item.get("options")
    if not isinstance(options,dict) or set(options)!={"A","B","C","D"}:return None
    technical=slot["category"]=="Technical Aptitude"
    options={key:(normalize_fenced_text(canonicalize_unlabelled_fences(value,selected_language),500) if technical else clean_text(value,500)) for key,value in options.items()}
    answer=clean_text(item.get("correct_answer"),1).upper()
    question=normalize_fenced_text(canonicalize_unlabelled_fences(item.get("question"),selected_language),2000) if technical else clean_text(item.get("question"),2000)
    explanation=(normalize_fenced_text(canonicalize_unlabelled_fences(item.get("explanation"),selected_language),3000,normalize_explanation) if technical else normalize_explanation(item.get("explanation"),3000))
    if technical:
        try:
            for value in (question,*options.values(),explanation):validate_fenced_code(value,selected_language)
        except ValueError:
            return None
    if answer not in options or any(not value for value in options.values()):return None
    if len({value.casefold() for value in options.values()})!=4 or len(question)<12 or len(explanation)<10:return None
    if clean_text(item.get("category"),80)!=slot["category"]:return None
    if clean_text(item.get("topic"),100).casefold()!=slot["topic"].casefold():return None
    if clean_text(item.get("difficulty"),10).casefold()!=slot["difficulty"].casefold():return None
    public_text="\n".join((question,*options.values(),explanation))
    if INTERNAL_TOKEN_PATTERN.search(public_text):return None
    if any(str(value).strip().casefold() in public_text.casefold() for value in internal_values if len(str(value).strip())>=4):return None
    return {**slot,"question":question,"options":options,"correct_answer":answer,"explanation":explanation,"content_hash":content_hash(question),"structural_hash":structural_hash(question,slot["category"],slot["topic"])}


def generate_questions(slots, avoid_questions=None, avoid_number_patterns=None, allow_demo_fallback=True, *, deadline=None, max_validation_attempts=3, background=False, request_timeout=None):
    total_started=time.perf_counter()
    if not current_app.config.get("OPENAI_API_KEY"):
        if allow_demo_fallback and current_app.config["ALLOW_DEMO_QUESTIONS"]: return demo_questions(slots,avoid_questions), "demo-fixture", empty_usage()
        raise RuntimeError("OpenAI question generation is unavailable")
    prompt_slots=[{**slot,"variation_seed":secrets.randbelow(900000)+100000,"scenario_seed":str(uuid.uuid4())[:8]} for slot in slots]
    batch_id=str(uuid.uuid4())
    # Normalize once, then use this exact full set in both the prompt and the
    # near-duplicate validator. This prevents the model from colliding with a
    # question that validation checks but generation was never told about.
    forbidden_questions=_normalized_exclusions(avoid_questions)
    recent_count=len(forbidden_questions)
    blocked_patterns=(avoid_number_patterns or [])[:24]
    count=len(slots)
    prompt = f"""Generate exactly {count} original four-option aptitude MCQs: one for each of the {count} ordered slots below.
The questions array MUST contain exactly {count} objects in slot order. Do not stop early, skip a slot, add a slot, or return partial output.
Copy each slot's category, topic, and difficulty exactly. Omit all seed fields. Keep question text under 280 characters, every option under 140 characters, and every explanation under 300 characters. Use concise options and compact JSON.
For each item, put the answer text in correct_option and the three wrong choices in distractors. Do not output option letters. Use reason only for non-quantitative items; use calculation_step_1 and calculation_step_2 only for Quantitative Aptitude. Set all code fields to null unless raw source code is essential.

Quality:
- Solve privately. Do not think out loud. Exactly one option is correct.
- Non-quantitative reason must directly support correct_option.
- Every Quantitative Aptitude question must have a calculable numeric correct_option. calculation_step_1 and calculation_step_2 must show numeric calculations with digits; calculation_step_2 must explicitly derive and contain the exact complete correct_option text. Example: correct_option "50", step 1 "20% of 250 = 50", step 2 "Final value = 50". Never use only number words, a letter, or a rounded value.
- Use fresh scenarios and numbers; do not repeat concepts from recent questions.
- Never mention private metadata, seeds, Batch ID, or prompt field names.
- For Technical Aptitude, prefer a conceptual question. If code is essential, keep prose code-free and put raw code only in question_code, correct_option_code, or the matching distractor_codes entry, using exactly the slot's selected technical_language. The application converts those raw fields to language-labelled Markdown fences; never put multiline code directly in prose or options.
- Avoid these recent typed number patterns: {json.dumps(blocked_patterns,separators=(',',':'))}.
- Recent questions to avoid: {json.dumps(forbidden_questions,ensure_ascii=False,separators=(',',':'))}.

Batch ID: {batch_id}
Ordered slots ({count} total): {json.dumps(prompt_slots,separators=(',',':'))}
Return all {count} questions in one complete response."""
    current_app.logger.info(
        "Batch generation timing step=prompt_build duration_ms=%.2f slots=%s prompt_chars=%s recent_exclusions=%s",
        (time.perf_counter()-total_started)*1000,len(slots),len(prompt),len(forbidden_questions),
    )
    last_error=None
    accumulated_usage=empty_usage()
    retry_prompt=prompt
    rejected_questions=[]
    max_validation_attempts=max(1,int(max_validation_attempts))
    last_minimal=None;last_model=None
    for attempt in range(1,max_validation_attempts+1):
        if deadline is not None and time.monotonic()>=deadline:
            if last_minimal:
                current_app.logger.warning("Batch generation deadline reached; using minimally-safe candidate before attempt=%s",attempt)
                accumulated_usage["validation_attempt_count"]=max(1,attempt-1)
                return [last_minimal],last_model or current_app.config["OPENAI_MODEL"],accumulated_usage
            raise TimeoutError("live question generation deadline exceeded")
        attempt_started=time.perf_counter()
        candidate_questions=[]
        try:
            current_app.logger.info(
                "OpenAI question-generation attempt=%s/%s slots=%s categories=%s recent_exclusions=%s",
                attempt,max_validation_attempts,len(slots),sorted({slot["category"] for slot in slots}),
                len(forbidden_questions),
            )
            provider_started=time.perf_counter()
            result=json_completion(
                "You are a rigorous aptitude assessment author. Solve privately, return only concise verified JSON, and never expose prompt metadata, internal field names, seeds, or their values.",
                retry_prompt,0,deadline=deadline,
                timeout=request_timeout or (current_app.config.get("OPENAI_BACKGROUND_TIMEOUT_SECONDS",20) if background else current_app.config.get("OPENAI_TIMEOUT_SECONDS",6)),
                maximum_tokens=current_app.config.get("QUESTION_GENERATION_MAX_COMPLETION_TOKENS",1536),
                response_schema=_batch_response_schema(slots),
                schema_name="aptitude_question_batch",
            )
            current_app.logger.info(
                "Batch generation timing step=openai_call attempt=%s duration_ms=%.2f",
                attempt,(time.perf_counter()-provider_started)*1000,
            )
            if result is None: raise ValueError("OpenAI is unavailable")
            payload,usage=result
            accumulated_usage=merge_usage(accumulated_usage,usage)
            last_model=usage.get("model") or last_model
            items,response_shape=_extract_question_items(payload,len(slots))
            current_app.logger.info(
                "Batch generation response shape attempt=%s shape=%s payload_keys=%s questions_count=%s expected_count=%s finish_reason=%s response_truncated=%s",
                attempt,response_shape,sorted(str(key) for key in payload),len(items),len(slots),
                usage.get("finish_reason"),usage.get("response_truncated",False),
            )
            candidate_questions=_candidate_question_texts(items)
            if len(items)==len(slots):
                canonical_items=[_canonicalize_batch_item(item,slot) for item,slot in zip(items,slots)]
                minimal=[_minimal_safe_item(item,slot,(prompt_slot["variation_seed"],prompt_slot["scenario_seed"],batch_id)) for item,slot,prompt_slot in zip(canonical_items,slots,prompt_slots)]
                if all(minimal) and not any(questions_are_near_duplicates(item["question"],seen) for item in minimal for seen in forbidden_questions):
                    # Keep the singleton fallback used by callers outside the
                    # complete-test flow. Batch callers require an exact count.
                    if len(minimal)==1:last_minimal=minimal[0]
            if len(items)!=len(slots): raise ValueError(f"expected {len(slots)} questions")
            validation_started=time.perf_counter()
            validated=[]
            for item_index,(item,slot,prompt_slot) in enumerate(zip(canonical_items,slots,prompt_slots),start=1):
                try:
                    validated.append(validate_generated_item(
                    # category/topic/difficulty (and technical_language) are
                    # already known server-side from `slot` — the model is
                    # asked to echo them back, but that's an unforced,
                    # sometimes-dropped field rather than real content, so
                    # `slot` always wins on overlap instead of failing
                    # validation when the model omits or restates them.
                    # Matches the same precedent already used by
                    # `_minimal_safe_item` above.
                    {**item,**slot},slot,
                        internal_values=(prompt_slot["variation_seed"],prompt_slot["scenario_seed"],batch_id),
                    ))
                except ValueError as exc:
                    # validate_generated_item's messages are fixed strings shared
                    # by several different checks (e.g. one "structured
                    # explanation must derive..." message covers every way that
                    # check can fail), so the message alone can't diagnose a
                    # recurrence -- log the actual generated content once here,
                    # the single choke point for every validation failure,
                    # instead of at each of validate_generated_item's many
                    # raise sites. No learner data: these are AI-generated
                    # aptitude questions, not user input.
                    current_app.logger.error(
                        "Question validation failed reason=%s attempt=%s item_index=%s category=%s topic=%s "
                        "explanation=%r correct_answer=%r options=%r",
                        str(exc),attempt,item_index,slot.get("category"),slot.get("topic"),
                        str(item.get("explanation",""))[:400],item.get("correct_answer"),item.get("options"),
                    )
                    raise ValueError(f"question {item_index}: {exc}") from exc
            content_hashes=[item["content_hash"] for item in validated]
            structural_hashes=[item["structural_hash"] for item in validated if item["structural_hash"]]
            if len(content_hashes)!=len(set(content_hashes)):raise ValueError("response contains duplicate question wording")
            if len(structural_hashes)!=len(set(structural_hashes)):raise ValueError("response contains structurally duplicate numeric questions")
            if any(
                questions_are_near_duplicates(item["question"], previous["question"])
                for index, item in enumerate(validated)
                for previous in validated[:index]
            ):
                raise ValueError("response contains near-duplicate question concepts")
            if any(questions_are_near_duplicates(item["question"],seen) for item in validated for seen in forbidden_questions):
                raise ValueError("response repeats a recent or in-test question concept")
            current_app.logger.info(
                "Batch generation timing step=parse_validate attempt=%s duration_ms=%.2f items=%s",
                attempt,(time.perf_counter()-validation_started)*1000,len(validated),
            )
            current_app.logger.info(
                "Batch generation timing step=total duration_ms=%.2f successful_attempt=%s",
                (time.perf_counter()-total_started)*1000,attempt,
            )
            accepted_model=usage.get("model") or current_app.config["OPENAI_MODEL"]
            accumulated_usage["validation_attempt_count"]=attempt
            return validated,accepted_model,accumulated_usage
        except ProviderError as exc:
            # A provider outage or quota response cannot be fixed by asking
            # for another wording variation. Preserve it for the route so the
            # learner receives the real retryable reason.
            if exc.kind=="deadline_exceeded" and last_minimal:
                current_app.logger.warning("Batch generation provider deadline reached; using minimally-safe candidate")
                accumulated_usage["validation_attempt_count"]=attempt
                return [last_minimal],last_model or current_app.config["OPENAI_MODEL"],accumulated_usage
            if allow_demo_fallback and current_app.config["ALLOW_DEMO_QUESTIONS"]:
                current_app.logger.warning(
                    "OpenAI provider unavailable; using local development fixture kind=%s status_code=%s error=%s",
                    exc.kind,exc.status_code,str(exc)[:240],
                )
                accumulated_usage["validation_attempt_count"]=attempt
                return demo_questions(slots,avoid_questions),"demo-fixture-provider-fallback",accumulated_usage
            raise
        except Exception as exc:
            last_error=exc
            for question in candidate_questions:
                if question.casefold() not in {row.casefold() for row in rejected_questions}:
                    rejected_questions.append(question)
            current_app.logger.info(
                "Batch generation timing step=failed_attempt attempt=%s duration_ms=%.2f error_type=%s",
                attempt,(time.perf_counter()-attempt_started)*1000,type(exc).__name__,
            )
            current_app.logger.warning("OpenAI question validation attempt %s/%s failed: %s",attempt,max_validation_attempts,str(exc)[:240])
            retry_prompt=_retry_context(prompt,exc,rejected_questions,attempt)
            if deadline is not None and time.monotonic()>=deadline and last_minimal:
                current_app.logger.warning("Batch generation validation deadline reached; using minimally-safe candidate")
                accumulated_usage["validation_attempt_count"]=attempt
                return [last_minimal],last_model or current_app.config["OPENAI_MODEL"],accumulated_usage
    if allow_demo_fallback and current_app.config["ALLOW_DEMO_QUESTIONS"]:
        current_app.logger.error(
            "OpenAI question validation exhausted; using the local development fixture: %s",
            str(last_error)[:240],
        )
        return demo_questions(slots,avoid_questions), "demo-fixture-fallback", accumulated_usage
    raise ValueError(f"OpenAI output failed validation after {max_validation_attempts} attempts: {last_error}") from last_error


def demo_questions(slots, avoid_questions=None):
    templates=[
      ("A shop marks an item at ₹800 and offers a 15% discount. What is the selling price?",{"A":"₹640","B":"₹680","C":"₹700","D":"₹720"},"B","Step 1: 15% of ₹800 = ₹120. Step 2: ₹800 - ₹120 = ₹680. Step 3: Answer = ₹680."),
      ("Choose the next number: 3, 8, 15, 24, 35, ?",{"A":"46","B":"47","C":"48","D":"49"},"C","The differences are 5, 7, 9, 11 and then 13, giving 48."),
      ("Choose the word closest in meaning to meticulous.",{"A":"Careless","B":"Precise","C":"Rapid","D":"Ordinary"},"B","Meticulous means showing great attention to detail, so precise is closest."),
      ("All analysts are readers. Which conclusion is guaranteed?",{"A":"All writers are analysts","B":"Some analysts are writers","C":"All analysts are readers","D":"No readers are analysts"},"C","The conclusion repeats the fact directly established by the premise."),
      ("Which operating system component manages CPU scheduling and memory?",{"A":"Browser","B":"Kernel","C":"Compiler","D":"Spreadsheet"},"B","The kernel manages core resources including CPU scheduling and memory."),
      ("Which data structure follows First In, First Out?",{"A":"Stack","B":"Tree","C":"Queue","D":"Graph"},"C","A queue removes elements in the same order they are inserted: FIFO."),
    ]
    template_by_category=dict(zip(CATEGORIES,templates))
    variants={
      "Quantitative Aptitude":[
        templates[0],
        ("A class has 18 boys and 12 girls. What is the ratio of boys to girls in simplest form?",{"A":"2:3","B":"3:2","C":"3:5","D":"5:3"},"B","Step 1: The ratio is 18:12. Step 2: Divide both values by 6 to get 3:2. Step 3: Answer = 3:2."),
        ("A worker completes a task in 6 days. What fraction of the task is completed in one day?",{"A":"1/3","B":"1/5","C":"1/6","D":"1/12"},"C","Step 1: One whole task is completed in 6 days. Step 2: One day completes 1 divided by 6. Step 3: Answer = 1/6."),
        ("What is the average of 14, 18, and 22?",{"A":"16","B":"18","C":"20","D":"54"},"B","Step 1: 14 + 18 + 22 = 54. Step 2: 54 divided by 3 = 18. Step 3: Answer = 18."),
        ("A bag contains 3 red and 2 blue balls. What is the probability of drawing a blue ball?",{"A":"2/5","B":"3/5","C":"1/2","D":"1/3"},"A","Step 1: Total balls = 3 + 2 = 5. Step 2: Blue balls = 2. Step 3: Answer = 2/5."),
      ],
      "Logical Reasoning":[
        templates[1],
        ("If CAT is coded as DBU, how is DOG coded using the same rule?",{"A":"EPF","B":"CNE","C":"DPG","D":"EPH"},"D","Each letter is shifted forward by one: D becomes E, O becomes P, and G becomes H. The matching encoded word is EPH."),
        ("Ravi walks 4 km north and then 3 km east. In which direction is he from the starting point?",{"A":"North-west","B":"North-east","C":"South-east","D":"South-west"},"B","Moving north and then east places Ravi to the north-east of his starting point."),
        ("All poets are readers. Some readers are teachers. Which statement must be true?",{"A":"All teachers are poets","B":"Some poets are teachers","C":"All poets are readers","D":"No reader is a teacher"},"C","The first statement directly guarantees that all poets are readers."),
        ("Find the next letter: B, E, H, K, ?",{"A":"L","B":"M","C":"N","D":"O"},"C","The sequence moves forward three letters each time: B, E, H, K, N."),
      ],
      "Verbal Ability":[
        templates[2],
        ("Choose the grammatically correct sentence.",{"A":"She have completed the work.","B":"She has completed the work.","C":"She completing the work.","D":"She had complete the work."},"B","With the singular subject 'She', the present perfect form is 'has completed'."),
        ("Choose the best word: The manager praised the team for its ____ effort.",{"A":"careless","B":"collective","C":"fragile","D":"silent"},"B","Collective means done by people acting together, which fits a team effort."),
        ("Which word is the opposite of scarce?",{"A":"Rare","B":"Limited","C":"Abundant","D":"Small"},"C","Abundant means available in large quantities, the opposite of scarce."),
        ("In the sentence 'Maya was reluctant to volunteer,' which word can replace reluctant without changing the meaning?",{"A":"Eager","B":"Unwilling","C":"Certain","D":"Cheerful"},"B","Reluctant means unwilling or hesitant to do something."),
      ],
      "Analytical Reasoning":[
        ("A report shows sales rising from 40 to 55 units. What is the increase?",{"A":"10","B":"15","C":"40","D":"95"},"B","The increase is found by subtracting 40 from 55, which gives 15."),
        ("If every project needs a plan and Project X is a project, what follows?",{"A":"Project X needs a plan","B":"Every plan is Project X","C":"Project X has no plan","D":"No projects need plans"},"A","Applying the stated rule to Project X shows that it needs a plan."),
        ("Which chart is most useful for comparing values across named categories?",{"A":"Bar chart","B":"Flowchart","C":"Map","D":"Timeline"},"A","A bar chart makes comparisons between named categories clear."),
        ("A process has steps A, B, and C, and B must occur after A. Which order is valid?",{"A":"B, A, C","B":"C, B, A","C":"A, B, C","D":"B, C, A"},"C","The only listed order that places A before B is A, B, C."),
        ("A pattern repeats circle, square, triangle. What comes after circle, square, triangle, circle?",{"A":"Circle","B":"Square","C":"Triangle","D":"Star"},"B","The three-shape pattern repeats, so after the next circle comes square."),
      ],
      "Computer Fundamentals":[
        templates[4],
        ("Which protocol automatically assigns IP addresses on a network?",{"A":"DNS","B":"DHCP","C":"HTTP","D":"FTP"},"B","DHCP automatically provides network configuration such as IP addresses."),
        ("What is the main purpose of a database index?",{"A":"Speed up data retrieval","B":"Encrypt every record","C":"Replace backups","D":"Format disks"},"A","A database index speeds up data retrieval by locating matching records more quickly."),
        ("Which component performs arithmetic and logical operations?",{"A":"ALU","B":"Monitor","C":"Router","D":"Keyboard"},"A","The arithmetic logic unit, or ALU, performs arithmetic and logical operations."),
        ("Which security practice uses a second verification step after a password?",{"A":"Defragmentation","B":"Two-factor authentication","C":"Caching","D":"Virtualization"},"B","Two-factor authentication requires another verification factor in addition to a password."),
      ],
      "Technical Aptitude":[templates[5],("Which structure uses Last In, First Out order?",{"A":"Queue","B":"Stack","C":"Array","D":"Graph"},"B","A stack removes the most recently added item first, which is LIFO."),("What does a compiler do?",{"A":"Translates source code","B":"Stores web pages","C":"Routes packets","D":"Draws charts"},"A","A compiler translates source code into another executable or lower-level form."),("Which loop is best when the number of repetitions is known?",{"A":"for loop","B":"recursive call","C":"switch statement","D":"exception block"},"A","A for loop is commonly used when the iteration count is known."),("What is the purpose of a function parameter?",{"A":"Pass input to a function","B":"Delete variables","C":"Restart a program","D":"Create a database"},"A","Parameters allow a caller to provide input values to a function.")],
    }
    result=[]
    blocked=list(avoid_questions or [])
    for i,slot in enumerate(slots):
        candidates=variants.get(slot["category"],[template_by_category.get(slot["category"],templates[i%len(templates)])])
        selected=next((candidate for candidate in candidates if not any(questions_are_near_duplicates(candidate[0],seen) for seen in blocked)),None)
        if not selected:
            # Development can run a ten-question category practice without a
            # provider key. Keep overflow fixtures unique and explicit; live
            # environments still use provider-authored aptitude questions.
            selected=(
                f"Practice item {i + 1}: which response correctly identifies the assigned topic {slot['topic']}?",
                {
                    "A": slot["topic"],
                    "B": f"Not {slot['topic']}",
                    "C": "An unrelated topic",
                    "D": "No topic is assigned",
                },
                "A",
                f"The assigned topic for this practice item is {slot['topic']}, so option A is correct.",
            )
        q,opts,answer,explanation=selected
        result.append(validate_generated_item({**slot,"question":q,"options":opts,"correct_answer":answer,"explanation":explanation},slot))
        blocked.append(q)
    return result

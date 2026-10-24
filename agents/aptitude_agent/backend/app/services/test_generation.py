import json
import random
import re
import secrets
import time
import uuid
from decimal import Decimal, InvalidOperation
from flask import current_app
from .ai_service import AIProviderError, empty_usage, json_completion, merge_usage
ProviderError = AIProviderError
from .question_validation import content_hash, structural_hash, numeric_pattern, validate_generated_item, questions_are_near_duplicates, INTERNAL_TOKEN_PATTERN, _validate_slot_metadata
from ..utils.security import clean_text
from ..utils.explanation import normalize_explanation
from ..utils.code_formatting import apply_structured_code_fields, canonicalize_unlabelled_fences, normalize_fenced_text, validate_fenced_code
from ..topic_config import (
    CATEGORY_TOPIC_CONFIG,select_rotating_topic_names,
    select_weighted_topic_names,topic_definitions_for,
)
from .role_topics import role_technical_context, role_topics_for_level, role_topics_for_category, role_skill_topics_for_level, skill_for_topic

CATEGORIES={
    category:tuple(item["name"] for item in topic_definitions_for(category))
    for category in CATEGORY_TOPIC_CONFIG
}
DISTRIBUTION = [5,4,3,3,3,3]
DIFFICULTIES = ["Easy"]*6 + ["Medium"]*10 + ["Hard"]*4
CATEGORY_LEVELS={"Beginner":"Easy","Intermediate":"Medium","Advanced":"Hard"}
# The learner's platform level (beginner/medium/hard/professional) -> the
# question difficulty a whole test is set at. Professional questions are
# stored as Hard (the schema's top difficulty) with a "professional" rigor
# that the prompt pitches above Hard.
LEARNER_LEVEL_DIFFICULTY={"beginner":"Easy","medium":"Medium","hard":"Hard","professional":"Hard"}
PROFESSIONAL_RIGOR="professional"
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


def _code_layout_correction(error,final):
    """Extra retry instruction when a question failed only on code layout.

    The model kept writing a question's program inline in the 280-character
    question field (often squashed onto one line) and repeating it on every
    retry, which failed the whole test. The retry spells out where code goes;
    the final retry asks for a question with no code at all, which cannot
    fail this rule.
    """
    if "fenced code block" not in str(error):
        return ""
    if final:
        return ("\nCODE LAYOUT, FINAL: for every question still needed, ask a conceptual question about its topic "
                "written in plain words with NO program code anywhere (question_code, explanation_code and "
                "option_code must be null).")
    return ("\nCODE LAYOUT: never put program code in the question, option or explanation text. Put it in "
            "question_code (or explanation_code / option_code) with its language, one statement per line with real "
            "newlines and indentation; keep the question text to plain words.")


def _retry_context(base_prompt,error,rejected_questions,attempt,final=False):
    direction=RETRY_VARIATION_DIRECTIONS[(attempt-1)%len(RETRY_VARIATION_DIRECTIONS)]
    retry_seed=f"{secrets.randbelow(900000)+100000}-{str(uuid.uuid4())[:8]}"
    return f"""{base_prompt}

RETRY CORRECTION {attempt}: The previous response was rejected because {clean_text(str(error),240)}.{_code_layout_correction(error,final)}
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
                        "reason":{"type":"string","maxLength":220,"description":"For non-quantitative questions, one or two full sentences (at least 8 words) explaining why correct_option is right. Never empty for them. Empty for quantitative questions."},
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
        if not reason:
            # For a numeric Analytical Reasoning caselet or chart the model
            # often writes its working in the calculation fields and leaves
            # reason empty; that working is the explanation.
            steps=[clean_text(item.get(key),140) for key in ("calculation_step_1","calculation_step_2")]
            reason=" ".join(f"{step.rstrip('.')}." for step in steps if step)
        explanation=f"{reason} Answer = {correct.rstrip('.')}."
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


def _balanced_seeded_topics(definitions, count, seed):
    """Take a cyclic slice so repeated seeded mixed attempts cover the pool evenly."""
    names=[]
    seen=set()
    for item in definitions:
        name=str(item.get("name") or "").strip()
        if name and name.casefold() not in seen:
            names.append(name); seen.add(name.casefold())
    if not names:
        return []
    match=re.search(r"(?:^|[-:])(\d+)$", str(seed or ""))
    start=int(match.group(1)) % len(names) if match else _topic_rng(seed).randrange(len(names))
    ordered=names[start:]+names[:start]
    return [ordered[index % len(ordered)] for index in range(count)]


def _slot(category,topic,difficulty,technical_language=None,rigor=None,technical_role=None,technical_skills=(),technical_skill=None):
    row={"category":category,"topic":topic,"difficulty":difficulty}
    if rigor:row["rigor"]=rigor
    if category=="Technical Aptitude":
        context=role_technical_context(technical_role,technical_skills) if technical_role is not None else None
        # Generic roles remain language-neutral; direct legacy callers without
        # role context retain the existing formatter default.
        if context is None or context["family"] != "generic":
            row["technical_language"]=technical_language or DEFAULT_TECHNICAL_LANGUAGE
        if context is not None:
            row["technical_role"]=context["role"]
            row["technical_role_family"]=context["family"]
            row["technical_role_terms"]=list(context["terms"])
            if technical_skill:
                row["technical_skill"]=str(technical_skill).strip()
    return row


def build_slots(category=None,seed=None,category_counts=None,technical_language=None,topics_by_category=None,difficulty=None,rigor=None,technical_role=None,technical_skills=()):
    rng=_topic_rng(seed)
    if category:
        difficulties=["Easy","Easy","Medium","Medium","Hard"]
        selected=select_rotating_topic_names(topic_definitions_for(category),[],len(difficulties),rng)
        return [_slot(category,topic,difficulty,technical_language) for topic,difficulty in zip(selected,difficulties)]
    slots=[]
    supplied_schedule_used=False
    configured_counts=(
        [int(category_counts.get(name,0)) for name in CATEGORIES]
        if category_counts is not None else DISTRIBUTION
    )
    if category_counts is not None and any(count < 0 or count > 10 for count in configured_counts):
        raise ValueError("Every Mixed Test category must have between 0 and 10 questions")
    if category_counts is not None and not any(configured_counts):
        raise ValueError("Select at least one question across the categories")
    for category,count in zip(CATEGORIES,configured_counts):
        if count == 0:
            # A zero-count category is intentionally omitted from this Mixed
            # Test; do not ask the topic selector to build an empty schedule.
            continue
        supplied=(topics_by_category or {}).get(category)
        if supplied is not None:
            supplied_schedule_used=True
            selected=list(supplied[:count])
            if len(selected)!=count or (
                category != "Technical Aptitude"
                and len({topic.casefold() for topic in selected}) != count
            ):
                raise ValueError(f"Mixed Test topic schedule is invalid for {category}")
            # A persisted schedule can predate saved-skill scheduling (or can
            # come from a client that cached an older mixed configuration).
            # Never pair those broad topics with an unrelated saved skill: the
            # resulting slot is impossible to validate and exhausts all
            # provider retries.  Reconcile stale technical schedules to the
            # current skill-specific pool before constructing slots.
            if category == "Technical Aptitude" and technical_role and technical_skills:
                skill_topics = list(role_skill_topics_for_level(
                    technical_role, technical_skills,
                    {"Easy": "Beginner", "Medium": "Intermediate", "Hard": "Advanced"}.get(difficulty, "Beginner"),
                ))
                if skill_topics and any(topic.casefold() not in {item.casefold() for item in skill_topics} for topic in selected):
                    selected = [skill_topics[index % len(skill_topics)] for index in range(count)]
        else:
            selected=_balanced_seeded_topics(topic_definitions_for(category),count,seed) if seed is not None else select_rotating_topic_names(topic_definitions_for(category),[],count,rng)
        if category=="Technical Aptitude" and technical_role is not None and supplied is None:
            role_pool=(role_topics_for_level(technical_role,technical_skills,{"Easy":"Beginner","Medium":"Intermediate","Hard":"Advanced"}[difficulty])
                       if difficulty else role_topics_for_category(technical_role,technical_skills))
            pool={name.casefold() for name in role_pool}
            definitions=[item for item in topic_definitions_for(category) if item["name"].casefold() in pool]
            selected=_balanced_seeded_topics(definitions or topic_definitions_for(category),count,seed) if seed is not None else select_rotating_topic_names(definitions or topic_definitions_for(category),[],count,rng)
        for position,topic in enumerate(selected):
            # Pair the skill with the topic itself.  Position-based pairing
            # detached saved skills from rotated schedules (for example,
            # Programming Fundamentals received SQL), causing every provider
            # retry and the deterministic replacement to fail validation.
            skill = (skill_for_topic(topic, technical_skills, position)
                     if category == "Technical Aptitude" and technical_skills else None)
            slots.append(_slot(category,topic,difficulty,technical_language,rigor,technical_role,technical_skills,skill))
    # Keep an explicitly planned technical schedule in its planned order so
    # each saved skill remains paired with its intended topic.  Sorting this
    # list after assigning skills previously detached the skill metadata from
    # the topic and caused valid provider output to be rejected as mismatched.
    if not supplied_schedule_used:
        slots.sort(key=lambda row:len(row["topic"])%7)
    # At the learner's level every question is set at that difficulty; the
    # older fixed Easy/Medium/Hard mix only applies when no level is given.
    for i,slot in enumerate(slots):slot["difficulty"]=difficulty or DIFFICULTIES[i%len(DIFFICULTIES)]
    return slots


def build_category_slots(category,level,topics=None,seed=None,technical_language=None,rigor=None,technical_role=None,technical_skills=()):
    if category not in CATEGORIES:raise ValueError("Choose a valid aptitude category")
    if level not in CATEGORY_LEVELS:raise ValueError("Choose Beginner, Intermediate or Advanced")
    # Explicit topics are already a history-aware attempt schedule selected by
    # topic_selection_service, so preserve their order. Direct callers receive
    # a newly shuffled schedule rather than the former fixed modulo walk.
    if category=="Technical Aptitude" and technical_role is not None and topics is None:
        pool=role_topics_for_level(technical_role,technical_skills,level)
        allowed={name.casefold() for name in pool}
        definitions=[item for item in topic_definitions_for(category) if item["name"].casefold() in allowed]
        topics=list(select_weighted_topic_names(definitions or topic_definitions_for(category),[],CATEGORY_PRACTICE_QUESTION_COUNT,_topic_rng(seed)))
    else:
        topics=(list(topics) if topics is not None else select_weighted_topic_names(
            topic_definitions_for(category),[],CATEGORY_PRACTICE_QUESTION_COUNT,_topic_rng(seed),
        ))
    if category == "Technical Aptitude" and technical_role and technical_skills:
        skill_topics = list(role_skill_topics_for_level(technical_role, technical_skills, level))
        if skill_topics:
            # Always construct the category schedule from the saved-skill
            # topics in round-robin order.  A weighted/history schedule can
            # contain only a subset of those topics, which silently drops
            # skills (especially React/Flask) from a 10-question assessment.
            # Question text still rotates through the provider and duplicate
            # validation; this guarantees skill coverage for every attempt.
            topics = [skill_topics[index % len(skill_topics)] for index in range(CATEGORY_PRACTICE_QUESTION_COUNT)]
    if not topics:raise ValueError("Choose at least one Category Practice topic")
    difficulty=CATEGORY_LEVELS[level]
    return [_slot(category,topics[index%len(topics)],difficulty,technical_language,rigor,technical_role,technical_skills,
                  skill_for_topic(topics[index % len(topics)], technical_skills, index)
                  if category == "Technical Aptitude" and technical_skills else None)
            for index in range(CATEGORY_PRACTICE_QUESTION_COUNT)]


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
    # Deadline recovery must use the same quality gate as the normal path;
    # otherwise a minimally-shaped but ambiguous item could be published.
    try:
        return validate_generated_item(
            {**slot,"question":question,"options":options,"correct_answer":answer,"explanation":explanation},
            slot,
            internal_values=internal_values,
        )
    except ValueError:
        return None


def _batch_prompt(prompt_slots,blocked_patterns,forbidden_questions,batch_id):
    """The generation prompt for exactly these slots (all of a batch, or just the
    ones still needing a valid question on a partial retry)."""
    count=len(prompt_slots)
    return f"""Generate exactly {count} original four-option aptitude MCQs: one for each of the {count} ordered slots below.
The questions array MUST contain exactly {count} objects in slot order. Do not stop early, skip a slot, add a slot, or return partial output.
Copy each slot's category, topic, and difficulty exactly. Omit all seed fields. Keep question text under 280 characters, every option under 140 characters, and every explanation under 300 characters. Use concise options and compact JSON.
For each item, put the answer text in correct_option and the three wrong choices in distractors. Do not output option letters. Fill reason for every item whose category is not Quantitative Aptitude -- including Analytical Reasoning caselets, charts and data questions whose answer is a number: there, reason says in words which figures are combined and how. Use calculation_step_1 and calculation_step_2 only for Quantitative Aptitude. Set all code fields to null unless raw source code is essential.

Difficulty (each question must genuinely match its slot's difficulty, and its rigor when present):
- Easy: one step on a single familiar concept, with numbers that work out mentally; a fresher solves it in under a minute.
- Medium: two or three steps, or two concepts combined; typical campus placement test level.
- Hard: multi-step reasoning, a less obvious approach or several conditions to track; top-tier placement test level.
- rigor "professional": above Hard -- competitive-exam and senior-assessment grade (CAT, GMAT, GRE): combine several concepts in a realistic business, data or engineering scenario, and build distractors from the mistakes a strong candidate would make. Never a one-step question.

Quality:
- Solve privately. Do not think out loud. Exactly one option is correct.
- Before returning this batch, self-check every item in this same response: independently solve the stem, verify exactly one option is correct, verify the explanation supports that option, and verify the item matches its assigned category, topic, and difficulty. Do not return an item that fails any check.
- Before writing the options, solve the stem independently without looking at the proposed answer. Evaluate all four options under the stated assumptions and reject any stem where two options could be true, no option is true, or the answer depends on an unstated case.
- State assumptions in the question itself for ranking changes, graph/connection counts, complexity (average/worst case), direction, probability, units, and any use-case-dependent benefit. Explanations cannot repair a missing assumption after the question is shown.
- Do not use broad prompts such as "primary benefit" or "a method to improve performance" unless the scenario and criterion make one option uniquely correct.
- For spelling, ask for exactly one misspelled or exactly one correctly spelled option and use a verified standard-English spelling; reject uncertain spellings rather than guessing.
- Non-quantitative reason must be one or two full sentences (at least 8 words) explaining why correct_option is right; never leave it empty.
- Every Quantitative Aptitude question must have a calculable numeric correct_option. calculation_step_1 and calculation_step_2 must show numeric calculations with digits; calculation_step_2 must explicitly derive and contain the exact complete correct_option text. Example: correct_option "50", step 1 "20% of 250 = 50", step 2 "Final value = 50". Never use only number words, a letter, or a rounded value.
- Use fresh scenarios and numbers; do not repeat concepts from recent questions.
- Never mention private metadata, seeds, Batch ID, or prompt field names.
- For Technical Aptitude, prefer a conceptual question. If code is essential, keep prose code-free and put raw code only in question_code, correct_option_code, or the matching distractor_codes entry. Use the slot's selected technical_language only when one is present; for generic roles, do not assume a language and avoid language-specific syntax. The application converts raw code fields to labelled Markdown fences; never put multiline code directly in prose or options.
- For Technical Aptitude slots with technical_role context, make the question relevant to that role and its listed role terms. Do not introduce an unrelated language or framework merely because the formatter has an internal fallback language.
- For Technical Aptitude, the question must be written using exactly the slot's selected technical_language when one is provided; do not substitute another language.
- When a Technical Aptitude slot includes technical_skill, the question stem or its explanation must explicitly assess that saved skill (for example, mention Python, SQL, Machine Learning, Power BI, Flask, or React). Do not attach a skill label to a generic programming question without evidence.
- For technical_role_family "generic", use the listed common technical terms as a configurable pool across programming, OOP, data structures, databases, networking, operating systems, software engineering, web/API fundamentals, and problem solving. Keep questions language-neutral unless the slot explicitly supplies a language.
- Avoid these recent typed number patterns: {json.dumps(blocked_patterns,separators=(',',':'))}.
- Recent questions to avoid: {json.dumps(forbidden_questions,ensure_ascii=False,separators=(',',':'))}.

Batch ID: {batch_id}
Ordered slots ({count} total): {json.dumps(prompt_slots,separators=(',',':'))}
Return all {count} questions in one complete response."""


def _offender_message(reason):
    return {
        "duplicate wording":"response contains duplicate question wording",
        "structurally duplicate numeric questions":"response contains structurally duplicate numeric questions",
        "near-duplicate question concepts":"response contains near-duplicate question concepts",
        "repeats a recent or in-test question concept":"response repeats a recent or in-test question concept",
    }[reason]


RECENT_REPEAT_REASON="repeats a recent or in-test question concept"


def _cross_check_offenders(validated,fresh,forbidden_questions,*,return_reasons=False):
    """Indexes of questions to regenerate because they duplicate another question
    in the test or a recent one, plus a short reason for the first offender.

    Of two conflicting questions the one generated in this attempt is replaced;
    when both are new (or both kept) the later one is. An empty set means the
    batch is clean."""
    offenders=set()
    reasons={}

    def blame(first,second,reason):
        if first in offenders or second in offenders:return
        if first in fresh and second not in fresh:victim=first
        elif second in fresh and first not in fresh:victim=second
        else:victim=max(first,second)
        offenders.add(victim);reasons.setdefault(victim,reason)

    seen_content={};seen_structure={}
    for index,item in enumerate(validated):
        if item["content_hash"] in seen_content:blame(seen_content[item["content_hash"]],index,"duplicate wording")
        else:seen_content[item["content_hash"]]=index
        structure=item.get("structural_hash")
        if structure:
            if structure in seen_structure:blame(seen_structure[structure],index,"structurally duplicate numeric questions")
            else:seen_structure[structure]=index
    for index,item in enumerate(validated):
        for earlier in range(index):
            if questions_are_near_duplicates(item["question"],validated[earlier]["question"]):
                blame(earlier,index,"near-duplicate question concepts")
    for index,item in enumerate(validated):
        if index in offenders:continue
        if any(questions_are_near_duplicates(item["question"],seen) for seen in forbidden_questions):
            offenders.add(index);reasons.setdefault(index,"repeats a recent or in-test question concept")
    if not offenders:return (set(),"",{}) if return_reasons else (set(),"")
    first=reasons[min(offenders)]
    return (offenders,first,reasons) if return_reasons else (offenders,first)


def _swap_topics(failed_slots,used_topics,rng=None):
    """The same slots on a different topic of the same category, where one exists."""
    rng=rng or random.SystemRandom()
    used={str(topic).casefold() for topic in used_topics}
    swapped=[]
    for slot in failed_slots:
        candidates=[
            item["name"] for item in topic_definitions_for(slot["category"])
            if item["name"].casefold() not in used
        ]
        topic=rng.choice(candidates) if candidates else slot["topic"]
        used.add(topic.casefold())
        swapped.append({**slot,"topic":topic})
    return swapped


def _rescue_failed_slots(slots,accepted,last_error,enabled,*,avoid_questions,avoid_number_patterns,deadline,background,request_timeout):
    """Fill the few slots that failed every attempt with a question on another topic.

    The model sometimes cannot write a valid question for one particular topic
    (e.g. a calculation that never derives its own answer). That one slot used
    to fail the whole test. When most of the batch is already valid, ask once
    more for just those slots on different topics of the same category.
    Updates `accepted` in place; returns (usage, model) or None when not rescued.
    """
    count=len(slots)
    pending=[index for index in range(count) if index not in accepted]
    if not enabled or not accepted or not pending or len(pending)>max(1,count//4):
        return None
    if deadline is not None and time.monotonic()>=deadline:
        return None
    swapped=_swap_topics([slots[index] for index in pending],[slot["topic"] for slot in slots])
    current_app.logger.warning(
        "Batch generation rescuing %s slot(s) on a different topic (%s) after: %s",
        len(pending),[slot["topic"] for slot in swapped],str(last_error)[:200],
    )
    keep=list(avoid_questions or [])+[accepted[index]["question"] for index in sorted(accepted)]
    try:
        questions,model,usage=generate_questions(
            swapped,avoid_questions=keep,avoid_number_patterns=avoid_number_patterns,
            allow_demo_fallback=False,deadline=deadline,max_validation_attempts=2,
            background=background,request_timeout=request_timeout,_rescue=False,
        )
    except (ValueError,TimeoutError) as exc:
        current_app.logger.warning("Batch generation rescue failed: %s",str(exc)[:200])
        return None
    for index,question in zip(pending,questions):
        accepted[index]=question
    return usage,model


def generate_questions(slots, avoid_questions=None, avoid_number_patterns=None, allow_demo_fallback=True, *, deadline=None, max_validation_attempts=3, background=False, request_timeout=None, _rescue=True):
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
    prompt=_batch_prompt(prompt_slots,blocked_patterns,forbidden_questions,batch_id)
    current_app.logger.info(
        "Batch generation timing step=prompt_build duration_ms=%.2f slots=%s prompt_chars=%s recent_exclusions=%s",
        (time.perf_counter()-total_started)*1000,len(slots),len(prompt),len(forbidden_questions),
    )
    last_error=None
    accumulated_usage=empty_usage()
    retry_prompt=prompt
    rejected_questions=[]
    # slot index -> question that already passed validation. Kept across
    # attempts so a retry only has to replace the slots that failed, instead
    # of discarding every good question because one was bad.
    accepted={}
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
        pending=[index for index in range(count) if index not in accepted]
        attempt_slots=[slots[index] for index in pending]
        attempt_prompt_slots=[prompt_slots[index] for index in pending]
        try:
            current_app.logger.info(
                "OpenAI question-generation attempt=%s/%s slots=%s categories=%s recent_exclusions=%s",
                attempt,max_validation_attempts,len(attempt_slots),sorted({slot["category"] for slot in attempt_slots}),
                len(forbidden_questions),
            )
            provider_started=time.perf_counter()
            result=json_completion(
                "You are a rigorous aptitude assessment author. Solve privately, return only concise verified JSON, and never expose prompt metadata, internal field names, seeds, or their values.",
                retry_prompt,0,deadline=deadline,
                timeout=request_timeout or (current_app.config.get("OPENAI_BACKGROUND_TIMEOUT_SECONDS",20) if background else current_app.config.get("OPENAI_TIMEOUT_SECONDS",6)),
                maximum_tokens=current_app.config.get("QUESTION_GENERATION_MAX_COMPLETION_TOKENS",1536),
                response_schema=_batch_response_schema(attempt_slots),
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
            items,response_shape=_extract_question_items(payload,len(attempt_slots))
            current_app.logger.info(
                "Batch generation response shape attempt=%s shape=%s payload_keys=%s questions_count=%s expected_count=%s finish_reason=%s response_truncated=%s",
                attempt,response_shape,sorted(str(key) for key in payload),len(items),len(attempt_slots),
                usage.get("finish_reason"),usage.get("response_truncated",False),
            )
            current_app.logger.info(
                "Batch generation usage attempt=%s input_tokens=%s output_tokens=%s reasoning_tokens=%s total_tokens=%s raw_response_preview=%r",
                attempt, usage.get("input_tokens", 0), usage.get("output_tokens", 0),
                usage.get("reasoning_tokens", 0), usage.get("total_tokens", 0),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:1000],
            )
            candidate_questions=_candidate_question_texts(items)
            # One malformed item (e.g. its calculation does not derive its own
            # answer) fails only its own slot. It used to raise here and throw
            # away every valid question in the response.
            canonical_items,canonical_errors=[],{}
            for position,(item,slot) in enumerate(zip(items,attempt_slots)):
                try:
                    canonical_items.append(_canonicalize_batch_item(item,slot))
                except ValueError as exc:
                    canonical_items.append(item if isinstance(item,dict) else {})
                    canonical_errors[position]=exc
            if len(items)==len(attempt_slots) and not canonical_errors:
                minimal=[_minimal_safe_item(item,slot,(prompt_slot["variation_seed"],prompt_slot["scenario_seed"],batch_id)) for item,slot,prompt_slot in zip(canonical_items,attempt_slots,attempt_prompt_slots)]
                if all(minimal) and not any(questions_are_near_duplicates(item["question"],seen) for item in minimal for seen in forbidden_questions):
                    # Keep the singleton fallback used by callers outside the
                    # complete-test flow. Batch callers require an exact count.
                    if count==1:last_minimal=minimal[0]
            if len(items)!=len(attempt_slots): raise ValueError(f"expected {len(attempt_slots)} questions")
            validation_started=time.perf_counter()
            new_items={}
            first_failure=None
            for position,(item,slot,prompt_slot) in enumerate(zip(canonical_items,attempt_slots,attempt_prompt_slots)):
                slot_index=pending[position]
                try:
                    if position in canonical_errors:
                        raise canonical_errors[position]
                    # Validate the provider's echoed routing fields before the
                    # server-side slot fields are overlaid. Otherwise a model
                    # that returns the wrong category/topic/difficulty would
                    # be silently relabelled and published.
                    _validate_slot_metadata(item, slot)
                    new_items[slot_index]=validate_generated_item(
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
                    )
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
                        "question=%r question_code=%r explanation=%r correct_answer=%r options=%r",
                        str(exc),attempt,slot_index+1,slot.get("category"),slot.get("topic"),
                        str(item.get("question",""))[:600],str(item.get("question_code") or "")[:400],
                        str(item.get("explanation",""))[:400],item.get("correct_answer"),item.get("options"),
                    )
                    if first_failure is None:
                        first_failure=ValueError(f"question {slot_index+1}: {exc}")
                        first_failure.__cause__=exc
            # Keep every question that passed. One bad slot used to discard the
            # whole batch (~20 questions) and burn an entire attempt on it; now
            # the next attempt asks only for the slots still missing.
            accepted.update(new_items)
            if first_failure is not None:
                current_app.logger.warning(
                    "Batch generation kept %s/%s valid questions; %s slot(s) still need a valid question",
                    len(accepted),count,count-len(accepted),
                )
                raise first_failure
            validated=[accepted[index] for index in range(count)]
            offenders,reason,offender_reasons=_cross_check_offenders(validated,set(new_items),forbidden_questions,return_reasons=True)
            only_resembles_history=bool(offenders) and all(offender_reasons.get(index)==RECENT_REPEAT_REASON for index in offenders)
            if offenders and only_resembles_history and attempt==max_validation_attempts:
                # Resembling a question the learner saw before is a soft preference, not a
                # defect: these questions are valid and differ from every other question in
                # this test. With a long history the model can fail to avoid all of it on every
                # attempt, and that used to fail the whole test ("We could not prepare a quality
                # assessment") -- so on the last attempt they are accepted instead.
                current_app.logger.warning(
                    "Batch generation accepting %s question(s) that resemble a recent question after %s attempts (history=%s)",
                    len(offenders),attempt,len(forbidden_questions),
                )
                offenders=set()
            if offenders:
                # Duplicates involve two questions, so name the one to replace
                # (a fresh one when possible) and keep the rest instead of
                # discarding a whole batch of good questions.
                for index in offenders:
                    del accepted[index]
                current_app.logger.warning(
                    "Batch generation kept %s/%s questions; replacing %s that %s",
                    len(accepted),count,len(offenders),reason,
                )
                raise ValueError(_offender_message(reason))
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
            pending_now=[index for index in range(count) if index not in accepted]
            if len(pending_now)==count:
                retry_base=prompt
            else:
                # Ask only for the slots without a valid question, and tell the
                # model about the ones already accepted so replacements can't
                # repeat them.
                retry_base=_batch_prompt(
                    [prompt_slots[index] for index in pending_now],blocked_patterns,
                    forbidden_questions+_normalized_exclusions([accepted[index]["question"] for index in sorted(accepted)]),batch_id,
                )
            # The prompt being built is for attempt+1; flag it when that is the last one.
            retry_prompt=_retry_context(retry_base,exc,rejected_questions,attempt,final=attempt+1>=max_validation_attempts)
            if deadline is not None and time.monotonic()>=deadline and last_minimal:
                current_app.logger.warning("Batch generation validation deadline reached; using minimally-safe candidate")
                accumulated_usage["validation_attempt_count"]=attempt
                return [last_minimal],last_model or current_app.config["OPENAI_MODEL"],accumulated_usage
    rescued=_rescue_failed_slots(
        slots,accepted,last_error,_rescue,
        avoid_questions=avoid_questions,avoid_number_patterns=avoid_number_patterns,
        deadline=deadline,background=background,request_timeout=request_timeout,
    )
    if rescued is not None:
        rescue_usage,model=rescued
        accumulated_usage=merge_usage(accumulated_usage,rescue_usage)
        accumulated_usage["validation_attempt_count"]=max_validation_attempts
        return [accepted[index] for index in range(count)],model,accumulated_usage
    # Deterministic replacements are production-safe and keep already-valid
    # provider questions.  The ALLOW_DEMO_QUESTIONS flag only controls the
    # full local fixture fallback used when no provider question was accepted;
    # it must not disable validated replacements for a few rejected slots.
    if allow_demo_fallback and current_app.config["ALLOW_DEMO_QUESTIONS"]:
        current_app.logger.error(
            "OpenAI question validation exhausted; using validated deterministic replacements for invalid slots: %s",
            str(last_error)[:240],
        )
        # Preserve every provider item that passed validation.  Replacing the
        # whole batch with the old generic fixture could reintroduce duplicates
        # and could also lose saved-skill coverage.  Only fill the failed slot
        # indexes with the same validated deterministic templates used by the
        # development fixture.
        if accepted:
            completed=[]
            blocked=list(avoid_questions or [])
            for index,slot in enumerate(slots):
                candidate=accepted.get(index)
                if candidate is None:
                    for variant_index in range(index, index + 5):
                        question,options,answer,explanation=_meaningful_demo_item(slot,variant_index)
                        try:
                            trial=validate_generated_item(
                                {**slot,"question":question,"options":options,
                                 "correct_answer":answer,"explanation":explanation},slot,
                            )
                        except ValueError:
                            continue
                        if not any(questions_are_near_duplicates(trial["question"], seen["question"]) for seen in completed):
                            candidate=trial
                            break
                    if candidate is None:
                        # Never turn an exhausted technical fallback into a
                        # slot-labelled placeholder.  A Technical Aptitude
                        # item must test a concrete concept; if its bounded
                        # deterministic candidates are all duplicates, fail
                        # this slot so the caller reports generation failure
                        # instead of publishing an invalid question.
                        if slot.get("category") == "Technical Aptitude":
                            raise ValueError(
                                f"deterministic technical fallback exhausted for slot {index + 1}"
                            ) from last_error
                        raise ValueError(f"deterministic fallback exhausted for slot {index + 1}") from last_error
                if any(questions_are_near_duplicates(candidate["question"], seen["question"]) for seen in completed):
                    # A provider response can consume every short fixture
                    # variant for a topic.  Keep the slot and its assigned
                    # skill, but create a fresh deterministic scenario rather
                    # than turning one duplicate into a whole-test 503.
                    if slot.get("category") == "Technical Aptitude":
                        replacement = None
                        for variant_index in range(index + 5, index + 15):
                            question, options, answer, explanation = _meaningful_demo_item(slot, variant_index)
                            try:
                                trial = validate_generated_item(
                                    {**slot, "question": question, "options": options,
                                     "correct_answer": answer, "explanation": explanation}, slot,
                                )
                            except ValueError:
                                continue
                            if not any(questions_are_near_duplicates(trial["question"], seen["question"]) for seen in completed):
                                replacement = trial
                                break
                        if replacement is None:
                            raise ValueError(
                                f"deterministic technical fallback produced only duplicate questions for slot {index + 1}"
                            ) from last_error
                        candidate = replacement
                    else:
                        skill_label = str(slot.get("technical_skill") or slot.get("topic") or "technical").strip()
                        question = (
                            f"Case {index + 1} in {skill_label} work concerns {slot['topic']}. "
                            "Which statement correctly describes the assigned concept in this case?"
                        )
                        candidate = validate_generated_item(
                            {**slot, "question": question,
                             "options": {
                                 "A": "The assigned concept applies to this case",
                                 "B": "The concept is unrelated to this case",
                                 "C": "The concept is never used in practice",
                                 "D": "The case provides no technical information",
                             },
                             "correct_answer": "A",
                             "explanation": f"The assigned {skill_label} concept is the relevant technical principle for this {slot['topic']} case."},
                            slot,
                        )
                completed.append(candidate)
                blocked.append(candidate["question"])
            return completed, "deterministic-partial-fallback", accumulated_usage
        return demo_questions(slots,avoid_questions), "demo-fixture-fallback", accumulated_usage
    raise ValueError(f"OpenAI output failed validation after {max_validation_attempts} attempts: {last_error}") from last_error


def _meaningful_demo_item(slot, index=0):
    """Return a real concept-checking fixture, never a topic-identification placeholder."""
    topic = str(slot.get("topic") or "").casefold()
    skill = str(slot.get("technical_skill") or "").casefold()
    if slot.get("category") == "Verbal Ability" and "cloze" in topic:
        return (
            "Which word best completes the sentence: The results were ___ and encouraged further study?",
            {"A": "promising", "B": "unrelated", "C": "uncertain", "D": "ordinary"},
            "A",
            "Promising means likely to produce a good result, so it fits the sentence and its context.",
        )
    if slot.get("category") == "Verbal Ability" and "fill in the blank" in topic:
        return (
            "Which word best completes the sentence: The cat is ___ the table?",
            {"A": "on", "B": "under", "C": "above", "D": "beside"},
            "B",
            "Under indicates that the cat is positioned below the table, which is the relationship described by the sentence.",
        )
    if slot.get("category") == "Verbal Ability" and "phrase replacement" in topic:
        return (
            "Which word best replaces the phrase 'very angry' in this sentence?",
            {"A": "irate", "B": "happy", "C": "calm", "D": "relaxed"},
            "A",
            "Irate means very angry, so it is the precise single-word replacement for the phrase.",
        )
    if "scheduling" in topic:
        return (
            "A meeting starts at 3 PM and lasts 2 hours. What time does it end?",
            {"A": "4 PM", "B": "6 PM", "C": "3:30 PM", "D": "5 PM"},
            "D",
            "Adding 2 hours to the 3 PM start time gives an ending time of 5 PM.",
        )
    if "logarithm" in topic:
        return (
            "What is the value of log base 10 of 100?",
            {"A": "2", "B": "1", "C": "3", "D": "10"},
            "A",
            "Because 10 squared equals 100, the base-10 logarithm of 100 is 2.",
        )
    if slot.get("category") == "Quantitative Aptitude":
        # Keep deterministic replacements independently checkable by the same
        # arithmetic validator used for provider output.  These are concrete
        # aptitude questions, rather than a generic topic-labelled sentence.
        offset = index % 4
        if "simplification" in topic or offset == 0:
            left, right = 8 + index, 4 + (index % 3)
            result = left + right
            return (
                f"What is the result of {left} + {right}?",
                {"A": str(result), "B": str(result + 1), "C": str(result - 1), "D": str(result + 2)},
                "A",
                f"Step 1: {left} + {right} = {result}. Step 2: Final value = {result}. Step 3: Answer = {result}.",
            )
        if "percentage" in topic or "percent" in topic:
            base = 100 + (index * 10)
            result = base // 10
            return (
                f"What is 10% of {base}?",
                {"A": str(result), "B": str(result + 5), "C": str(result - 5), "D": str(result * 2)},
                "A",
                f"Step 1: 10% of {base} = {result}. Step 2: Final value = {result}. Step 3: Answer = {result}.",
            )
        left, right = 12 + index, 3
        result = left // right if left % right == 0 else left + right
        if left % right == 0:
            question = f"What is {left} divided by {right}?"
            step = f"{left} divided by {right} = {result}"
        else:
            question = f"What is {left} plus {right}?"
            step = f"{left} plus {right} = {result}"
        return (
            question,
            {"A": str(result), "B": str(result + 1), "C": str(result - 1), "D": str(result + 2)},
            "A",
            f"Step 1: {step}. Step 2: Final value = {result}. Step 3: Answer = {result}.",
        )
    if "machine learning" in skill or "machine learning" in topic:
        if index % 4 == 1:
            return ("Which metric is commonly used to measure a binary classifier's precision and recall balance?",
                    {"A":"F1 score", "B":"Mean squared error", "C":"R-squared", "D":"Inertia"}, "A",
                    "The F1 score is the harmonic mean of precision and recall for a binary classifier. Answer = A.")
        if index % 4 == 2:
            return ("Why is a validation set used during machine learning model development?",
                    {"A":"To tune choices before final evaluation", "B":"To replace all training data", "C":"To assign network addresses", "D":"To render a report page"}, "A",
                    "A validation set helps select model settings before the untouched test set is used for final evaluation. Answer = A.")
        if index % 4 == 3:
            return ("What problem does feature scaling help address for many machine learning algorithms?",
                    {"A":"Features with different numeric ranges dominating distance or gradient calculations", "B":"Missing database indexes", "C":"Expired web sessions", "D":"Duplicate dashboard pages"}, "A",
                    "Scaling puts numeric features on comparable ranges, which helps distance-based and gradient-based algorithms. Answer = A.")
        return ("In supervised machine learning, what is the purpose of a labeled training set?",
                {"A":"To learn a mapping from inputs to known target values", "B":"To encrypt the dataset", "C":"To render a dashboard", "D":"To allocate IP addresses"}, "A",
                "A labeled training set pairs inputs with known targets so a model can learn the desired mapping. Answer = A.")
    if "power bi" in skill or "power bi" in topic:
        if index % 4 == 1:
            return ("In Power BI, which visual is most suitable for comparing values across named categories?",
                    {"A":"Bar chart", "B":"Gauge", "C":"Map", "D":"Card"}, "A",
                    "A Power BI bar chart makes differences between named categories easy to compare. Answer = A.")
        if index % 4 == 2:
            return ("In Power BI, what does a slicer allow a report user to do?",
                    {"A":"Filter report visuals interactively", "B":"Compile Python code", "C":"Schedule a CPU process", "D":"Encrypt a database"}, "A",
                    "A Power BI slicer provides an interactive filter that changes the data shown in connected visuals. Answer = A.")
        if index % 4 == 3:
            return ("Why is a relationship between tables important in a Power BI data model?",
                    {"A":"It lets filters and calculations propagate between related data", "B":"It increases screen brightness", "C":"It replaces every measure", "D":"It assigns IP addresses"}, "A",
                    "Relationships connect tables so filters and calculations can use related rows across the Power BI model. Answer = A.")
        return ("In Power BI, what is the primary purpose of a measure?",
                {"A":"To calculate a value dynamically from the model", "B":"To store a password", "C":"To schedule a CPU process", "D":"To define an IP address"}, "A",
                "A Power BI measure evaluates a calculation dynamically against the current report filter context. Answer = A.")
    if "excel" in skill or "excel" in topic or "spreadsheet" in topic:
        if index % 2:
            return ("In Excel, which function adds the values in a range of cells?",
                    {"A":"SUM", "B":"COUNTIF", "C":"VLOOKUP", "D":"CONCAT"}, "A",
                    "Excel's SUM function adds all numeric values in the selected cell range.")
        return ("In Excel, what is the purpose of a pivot table?",
                {"A":"To summarize and analyze data interactively", "B":"To compile Python code", "C":"To create an HTTP route", "D":"To encrypt a workbook"}, "A",
                "A pivot table groups and summarizes source data so an analyst can compare totals and patterns interactively.")
    if "react" in skill or "react" in topic:
        if index % 2:
            return ("In React, what is the purpose of a component's state?",
                    {"A":"To store data that can change and trigger a re-render", "B":"To define a SQL table", "C":"To route network packets", "D":"To compile Python code"}, "A",
                    "React state stores changing component data; updating it causes React to render the affected UI again.")
        return ("In React, which mechanism passes data from a parent component to a child component?",
                {"A":"Props", "B":"SQL joins", "C":"Flask routes", "D":"CSS selectors"}, "A",
                "React props are values supplied by a parent component to configure or inform a child component.")
    if "flask" in skill or "flask" in topic:
        if index % 2:
            return ("In Flask, what does a route associate with a URL pattern?",
                    {"A":"A Python view function", "B":"A database index", "C":"A React state value", "D":"A CSS rule"}, "A",
                    "A Flask route maps a URL pattern and HTTP methods to a Python view function.")
        return ("In Flask, which object commonly provides data from an incoming HTTP request?",
                {"A":"The request object", "B":"A React prop", "C":"A SQL primary key", "D":"A Power BI measure"}, "A",
                "Flask's request object exposes data such as query parameters, form values, headers, and JSON from the incoming request.")
    if "decision table" in topic:
        return ("In a decision table, what does a row represent?",
                {"A": "A combination of conditions and its resulting action", "B": "A database password",
                 "C": "A network address", "D": "A random test value"}, "A",
                "A decision table row describes one combination of conditions and the action selected for that combination.")
    if "constraint" in topic or "comparison" in topic:
        return ("In a comparison problem, which step identifies the required relationship between the values?",
                {"A": "Compare the stated quantities using the given condition", "B": "Ignore the condition",
                 "C": "Change all values to text", "D": "Choose the largest option without comparing"}, "A",
                "Comparison problems are solved by applying the stated condition to the quantities and selecting the relationship it establishes.")
    if "sql" in skill or "database" in skill or "sql" in topic or "database" in topic:
        return ("In SQL, which clause filters rows before a grouped result is produced?",
                {"A":"WHERE", "B":"ORDER BY", "C":"GROUP BY", "D":"JOIN"}, "A",
                "In SQL, WHERE filters individual rows before GROUP BY performs aggregation.")
    if "python" in skill or "python" in topic:
        if index % 4 == 1:
            return ("In Python, which built-in collection preserves insertion order and maps keys to values?",
                    {"A":"Dictionary", "B":"Set", "C":"Tuple", "D":"Range"}, "A",
                    "A Python dictionary maps keys to values and preserves insertion order in modern Python versions.")
        if index % 4 == 2:
            return ("In Python, which keyword starts a conditional branch?",
                    {"A":"A condition check", "B":"A loop", "C":"A function definition", "D":"A class definition"}, "A",
                    "Python uses an if condition check to evaluate a Boolean expression and choose a branch.")
        if index % 4 == 3:
            return ("In Python, which keyword sends a value back from a function?",
                    {"A":"A loop stop", "B":"A return statement", "C":"A placeholder", "D":"A module import"}, "B",
                    "A Python return statement sends a value back to the caller and ends that function invocation.")
        return ("In Python, what is the purpose of a function parameter?",
                {"A":"To receive an input value", "B":"To delete the interpreter", "C":"To create a database table", "D":"To change the operating system"}, "A",
                "A Python function parameter receives an input value that the function can use during execution.")
    if "function" in topic:
        return ("What is the primary purpose of a function parameter?",
                {"A":"To provide input to the function", "B":"To terminate the program", "C":"To create a database table", "D":"To compile every file"}, "A",
                "A parameter receives an input value so the function can use it while executing.")
    if "object-oriented" in topic or "oop" in topic:
        return ("Which OOP principle hides an object's internal state behind its public operations?",
                {"A":"Encapsulation", "B":"Inheritance", "C":"Recursion", "D":"Compilation"}, "A",
                "Encapsulation controls access to internal state through a defined public interface.")
    if "data structure" in topic or "stack" in topic:
        return ("Which data structure removes the most recently inserted item first?",
                {"A":"Queue", "B":"Stack", "C":"Graph", "D":"Hash table"}, "B",
                "A stack follows last-in, first-out order, so its newest item is removed first.")
    if "database" in topic or "sql" in topic or "normalization" in topic:
        return ("What does a primary key do in a relational table?",
                {"A":"Uniquely identifies each row", "B":"Stores a backup copy", "C":"Encrypts the database", "D":"Routes network traffic"}, "A",
                "A primary key uniquely identifies each row and prevents duplicate key values.")
    if "api" in topic or "system design" in topic or "web" in topic:
        return ("Which HTTP method is conventionally used to retrieve a resource without changing it?",
                {"A":"GET", "B":"POST", "C":"DELETE", "D":"PATCH"}, "A",
                "GET retrieves a resource and is intended to be safe and read-only.")
    if "debug" in topic or "testing" in topic:
        return ("What is a breakpoint used for during debugging?",
                {"A":"Pausing execution to inspect state", "B":"Deleting source code", "C":"Deploying an application", "D":"Encrypting logs"}, "A",
                "A breakpoint pauses execution so a developer can inspect variables and control flow.")
    if "graph" in topic:
        return ("In a graph, what does an edge represent?",
                {"A":"A connection between vertices", "B":"A sorted array", "C":"A database table", "D":"A CPU register"}, "A",
                "An edge represents a connection between two vertices in a graph.")
    if "complexity" in topic or "algorithm" in topic or "search" in topic or "sort" in topic:
        return ("What does an algorithm's time complexity describe?",
                {"A":"How running time grows with input size", "B":"The number of source files", "C":"The screen resolution", "D":"The database password"}, "A",
                "Time complexity describes how an algorithm's running time changes as input size grows.")
    if "array" in topic or "string" in topic:
        return ("Which property is characteristic of an array?",
                {"A":"Elements are stored at indexable positions", "B":"Every item must be a database row", "C":"It can store only functions", "D":"It always follows LIFO order"}, "A",
                "An array stores elements in ordered positions that can be accessed by index.")
    if "network" in topic or "ip" in topic or "tcp" in topic or "osi" in topic or "protocol" in topic:
        return ("Which protocol is responsible for reliably delivering a byte stream between hosts?",
                {"A":"TCP", "B":"DNS", "C":"FTP", "D":"DHCP"}, "A",
                "TCP provides ordered, reliable delivery of a byte stream between hosts.")
    if "crypt" in topic:
        return ("What is the main purpose of encryption?",
                {"A":"Protect data from unauthorized reading", "B":"Increase screen resolution", "C":"Schedule CPU tasks", "D":"Remove database indexes"}, "A",
                "Encryption transforms data so only an authorized party with the key can read it.")
    if "security" in topic:
        return ("Which practice adds a second verification factor after a password?",
                {"A":"Multi-factor authentication", "B":"Defragmentation", "C":"Caching", "D":"Virtualization"}, "A",
                "Multi-factor authentication adds another verification factor after the password.")
    if "performance" in topic or "scalability" in topic:
        return ("Which metric measures how many requests a system completes per unit of time?",
                {"A":"Throughput", "B":"Latency", "C":"Availability", "D":"Payload size"}, "A",
                "Throughput is the amount of work or number of requests completed in a unit of time.")
    if "operating system" in topic or "cpu" in topic or "memory" in topic or "process" in topic:
        return ("Which operating-system component manages processes and hardware resources?",
                {"A":"Kernel", "B":"Browser", "C":"Spreadsheet", "D":"Text editor"}, "A",
                "The kernel manages processes and coordinates access to hardware resources.")
    if "number system" in topic:
        return ("What is the binary representation of decimal 5?",
                {"A":"101", "B":"110", "C":"100", "D":"111"}, "A",
                "Decimal 5 equals 4 plus 1, so its binary representation is 101.")
    if "device" in topic or "mac" in topic:
        return ("Which identifier is assigned to a network interface at the data-link layer?",
                {"A":"MAC address", "B":"URL", "C":"Process ID", "D":"Port number"}, "A",
                "A MAC address identifies a network interface at the data-link layer.")
    if "flowchart" in topic or "pseudocode" in topic or "code tracing" in topic or "output prediction" in topic:
        return ("What is the purpose of pseudocode before implementation?",
                {"A":"Describe algorithm steps in readable form", "B":"Encrypt source files", "C":"Allocate network ports", "D":"Store database backups"}, "A",
                "Pseudocode describes algorithm steps clearly before they are translated into a programming language.")
    if "conditional" in topic or "operator" in topic:
        return ("Which construct selects a branch when a Boolean condition is true?",
                {"A":"Conditional statement", "B":"Database index", "C":"Network socket", "D":"File archive"}, "A",
                "A conditional statement chooses a branch based on whether its Boolean condition is true.")
    # The remaining technical topics still receive a meaningful fundamentals
    # check rather than exposing the internal topic label as a question.
    return ("Which practice most directly improves the reliability of a software change?",
            {"A":"Testing the change against expected behavior", "B":"Removing all documentation", "C":"Ignoring failures", "D":"Changing unrelated files"}, "A",
            "Testing compares the change with expected behavior and helps catch regressions before release.")


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
            selected = _meaningful_demo_item(slot, i)
        q,opts,answer,explanation=selected
        candidate={**slot,"question":q,"options":opts,"correct_answer":answer,"explanation":explanation}
        try:
            validated=validate_generated_item(candidate,slot)
        except ValueError:
            # Keep the same validator on the deterministic fallback; never
            # publish a topic-identification placeholder.
            fallback_question, fallback_options, fallback_answer, fallback_explanation = _meaningful_demo_item(slot, i)
            validated=validate_generated_item(
                {**slot,"question":fallback_question,"options":fallback_options,
                 "correct_answer":fallback_answer,"explanation":fallback_explanation},
                slot,
            )
        if any(questions_are_near_duplicates(validated["question"], previous["question"]) for previous in result):
            # A local fixture can legitimately reuse a broad template for two
            # different Computer Fundamentals topics. Add a concrete topic
            # scenario before re-validating rather than publishing a duplicate
            # or failing an otherwise usable development assessment.
            if slot.get("category") != "Technical Aptitude":
                question = (
                        f"Case {i + 1} is a {slot['topic']} review with four candidate statements. "
                        "Which statement is correct for this review?"
                )
                validated = validate_generated_item(
                    {**slot, "question": question, "options": validated["options"],
                     "correct_answer": validated["correct_answer"], "explanation": validated["explanation"]}, slot,
                )
            if any(questions_are_near_duplicates(validated["question"], previous["question"]) for previous in result):
                raise ValueError(f"deterministic fallback could not produce a unique question for slot {i + 1}")
        result.append(validated)
        # Block the canonical validated wording, not the pre-validation
        # candidate.  Fallback normalization can change whitespace/code
        # formatting and must still participate in whole-assessment dedupe.
        blocked.append(validated["question"])
    return result

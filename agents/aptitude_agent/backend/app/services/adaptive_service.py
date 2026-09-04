"""Computer-adaptive difficulty and question-generation helpers."""

import uuid
import time

from flask import current_app

from ..extensions import db
from ..models import AptitudeTestQuestion, RecentQuestionHash
from .audit_service import record_event
from .prefetch_service import clear_test_cache, consume_question_prefetch, schedule_question_prefetch
from .test_generation import build_category_slots, build_slots, generate_questions
from .topic_selection_service import (
    attempt_topic_schedule,mixed_attempt_topic_schedules,replace_attempt_topic,
)
from .question_validation import questions_are_near_duplicates
from .question_timing import question_time_seconds
from .usage_service import record_usage


DIFFICULTIES=("Easy","Medium","Hard")
DIFFICULTY_LEVEL={"Easy":1,"Medium":2,"Hard":3}


def _timing(test_id,step,started,**details):
    suffix=" ".join(f"{key}={value}" for key,value in details.items())
    duration_ms=(time.perf_counter()-started)*1000
    current_app.logger.info(
        "Live question timing test=%s step=%s duration_ms=%.2f%s",
        test_id,step,duration_ms,f" {suffix}" if suffix else "",
    )


def _step(difficulty,direction):
    index=DIFFICULTIES.index(difficulty)
    return DIFFICULTIES[max(0,min(len(DIFFICULTIES)-1,index+direction))]


def _average_label(value):
    if value<1.5:return "Easy"
    if value<2.5:return "Medium"
    return "Hard"


def determine_next_difficulty(test,category):
    """Derive the next level from persisted answers for deterministic adaptation."""
    answered=sorted(
        (question for question in test.questions if question.category==category and question.answer),
        key=lambda question:question.sequence_no,
    )
    if not answered:
        reason="started category at Medium; no prior answers"
        return "Medium",reason
    last=answered[-1];answer=last.answer;current=last.difficulty
    if answer.timed_out or not answer.is_correct:
        next_level=_step(current,-1)
        reason=f"stepped down after {'timeout' if answer.timed_out else 'wrong answer'}" if next_level!=current else "remained at Easy after wrong answer"
        return next_level,reason
    if getattr(last,"hint_requested",False):
        return current,"held difficulty because the previous correct answer used a hint"
    ratio=answer.time_taken_seconds/max(1,last.allowed_time_seconds)
    if ratio>=.9:
        return current,"held difficulty because the correct answer used at least 90% of allowed time"
    signal=0;streak=0
    for question in reversed(answered):
        item=question.answer
        if question.difficulty!=current or not item.is_correct or item.timed_out or getattr(question,"hint_requested",False):break
        response_ratio=item.time_taken_seconds/max(1,question.allowed_time_seconds)
        if response_ratio>=.9:break
        streak+=1;signal+=2 if response_ratio<.4 else 1
        if signal>=2:break
    if signal>=2:
        next_level=_step(current,1)
        if next_level!=current:
            reason="stepped up after a fast correct answer" if streak==1 else f"stepped up after {streak} correct answers at {current}"
        else:reason="remained at Hard after strong performance"
        return next_level,reason
    return current,f"held at {current}; correct streak has not reached the step-up threshold"


def _excluded_question_texts(test):
    step_started=time.perf_counter()
    current_questions=AptitudeTestQuestion.query.filter_by(test_id=test.id).order_by(AptitudeTestQuestion.sequence_no).all()
    _timing(test.id,"current_test_questions_query",step_started,rows=len(current_questions))
    current_texts=[question.question_text for question in current_questions]
    step_started=time.perf_counter()
    recent_rows=RecentQuestionHash.query.filter_by(student_id=test.student_id).order_by(RecentQuestionHash.created_at.desc()).limit(current_app.config["RECENT_QUESTION_HISTORY_LIMIT"]).all()
    _timing(test.id,"recent_hashes_query",step_started,rows=len(recent_rows))
    history={row.content_hash for row in recent_rows}
    step_started=time.perf_counter()
    recent_questions=AptitudeTestQuestion.query.filter(AptitudeTestQuestion.content_hash.in_(history)).order_by(AptitudeTestQuestion.generated_at.desc()).limit(60).all() if history else []
    _timing(test.id,"recent_questions_query",step_started,rows=len(recent_questions))
    return [*current_texts,*(question.question_text for question in recent_questions)]


def _question_source(test,slot,sequence):
    """Consume one ephemeral prefetch or perform bounded live generation."""
    excluded_texts=_excluded_question_texts(test)
    source_started=time.perf_counter()
    prefetched=consume_question_prefetch(test.id,sequence,slot)
    if prefetched:
        _timing(
            test.id,"question_source",source_started,source="prefetch_hit",sequence=sequence,
            category=slot["category"],topic=slot["topic"],difficulty=slot["difficulty"],
            background_generation_ms=prefetched.get("generation_ms",0),
        )
        return prefetched["item"],prefetched["model"],prefetched["usage"],"prefetch_hit"

    source="expected_first_question" if sequence==1 else "prefetch_miss"
    current_app.logger.info(
        "Question prefetch source test=%s sequence=%s source=%s category=%s topic=%s difficulty=%s",
        test.id,sequence,source,slot["category"],slot["topic"],slot["difficulty"],
    )
    if sequence>1:
        record_event("question_prefetch_miss",test.student_id,test.id,{"sequence":sequence,"category":slot["category"],"difficulty":slot["difficulty"]})

    step_started=time.perf_counter()
    deadline=time.monotonic()+current_app.config["LIVE_QUESTION_DEADLINE_SECONDS"]
    try:
        generated,model,generation_usage=generate_questions(
            [slot],avoid_questions=excluded_texts,
            allow_demo_fallback=current_app.config["ALLOW_DEMO_QUESTIONS"],
            # One rejected JSON response must not end an otherwise healthy
            # Category Practice attempt. Both attempts share the same
            # learner-facing deadline, so this improves reliability without
            # creating an unbounded wait.
            deadline=deadline,max_validation_attempts=2,
        )
    except ValueError:
        # Invalid generated content can be topic-specific. Give Category
        # Practice one different topic inside the existing shared deadline.
        # Provider/rate-limit errors deliberately propagate: changing a topic
        # cannot repair provider availability and must not multiply latency.
        if test.test_mode!="category_practice" or time.monotonic()>=deadline:
            raise
        replacement=replace_attempt_topic(test,sequence,slot["topic"])
        if replacement==slot["topic"]:
            raise
        slot={**slot,"topic":replacement}
        generated,model,generation_usage=generate_questions(
            [slot],avoid_questions=excluded_texts,
            allow_demo_fallback=current_app.config["ALLOW_DEMO_QUESTIONS"],
            deadline=deadline,max_validation_attempts=2,
        )
    _timing(
        test.id,"openai_generation_and_validation",step_started,source=source,model=model,
        exclusions=len(excluded_texts),provider_wait_ms=generation_usage.get("provider_wait_ms",0),
        provider_retries=generation_usage.get("provider_retry_count",0),validation_attempts=generation_usage.get("validation_attempt_count",1),
    )
    return generated[0],model,generation_usage,source


def _persist_question(test,sequence,slot,reason,event_type,prompt_version):
    total_started=time.perf_counter()
    item,model,generation_usage,source=_question_source(test,slot,sequence)
    step_started=time.perf_counter()
    existing=AptitudeTestQuestion.query.filter_by(test_id=test.id).all()
    if any(questions_are_near_duplicates(item["question"],question.question_text) for question in existing):
        raise ValueError("Question selection produced a duplicate or near-duplicate within this test")
    _timing(test.id,"in_test_duplicate_check",step_started,rows=len(existing))
    current_app.logger.debug(
        "Question selected test=%s sequence=%s category=%s topic=%s source=%s existing_in_test=%s",
        test.id, sequence, item["category"], item["topic"],
        source, len(existing),
    )
    question=AptitudeTestQuestion(
        id=str(uuid.uuid4()),test_id=test.id,sequence_no=sequence,
        category=item["category"],topic=item["topic"],difficulty=item["difficulty"],
        difficulty_reason=reason,question_text=item["question"],option_a=item["options"]["A"],
        option_b=item["options"]["B"],option_c=item["options"]["C"],option_d=item["options"]["D"],
        correct_answer=item["correct_answer"],explanation=item["explanation"],
        allowed_time_seconds=question_time_seconds(item["difficulty"]),generation_model=model,hint_text=None,
        prompt_version=prompt_version,content_hash=item["content_hash"],source_bank_item_id=None,
        structural_hash=item["structural_hash"],
    )
    db.session.add(question)
    db.session.add(RecentQuestionHash(student_id=test.student_id,test_id=test.id,category=question.category,topic=question.topic,content_hash=question.content_hash,structural_hash=question.structural_hash,bank_question_id=None))
    step_started=time.perf_counter()
    db.session.flush()
    _timing(test.id,"question_db_flush",step_started)
    step_started=time.perf_counter()
    record_usage(test.student_id,"question_generation",model,generation_usage,test.id,question.id)
    metadata={"sequence":sequence,"category":question.category,"difficulty":question.difficulty,"source":source}
    if reason:metadata["reason"]=reason
    record_event(event_type,test.student_id,test.id,metadata)
    _timing(test.id,"usage_and_audit_staging",step_started)
    _timing(test.id,"question_persist_total",total_started,sequence=sequence)
    return question


def _slot_for_sequence(test,sequence):
    if getattr(test,"test_mode","mixed")=="category_practice":
        topics=attempt_topic_schedule(test,test.total_questions)
        schedule=build_category_slots(test.selected_category,test.selected_level,topics,technical_language=test.technical_language)
        if sequence<1 or sequence>len(schedule):return None
        return dict(schedule[sequence-1])
    schedule=build_slots(
        test.focus_category,seed=test.id,
        category_counts=test.mixed_category_counts if not test.focus_category else None,
        technical_language=test.technical_language,
        topics_by_category=mixed_attempt_topic_schedules(test) if not test.focus_category else None,
    )
    if sequence<1 or sequence>len(schedule):return None
    slot=dict(schedule[sequence-1])
    slot["difficulty"],_=determine_next_difficulty(test,slot["category"])
    return slot


def schedule_test_prefetch(test,sequence):
    """Best-effort prefetch for exactly one future sequence.

    The slot is recomputed after answer submission. If adaptive difficulty
    changed, schedule_question_prefetch atomically replaces the speculative
    entry created while the learner was viewing the previous question.
    """
    if sequence>test.total_questions:
        clear_test_cache(test.id)
        return False
    slot=_slot_for_sequence(test,sequence)
    if not slot:return False
    return schedule_question_prefetch(test.id,sequence,slot,_excluded_question_texts(test))


def schedule_next_question_prefetch(test,served_sequence):
    return schedule_test_prefetch(test,served_sequence+1)


def ensure_adaptive_question(test):
    total_started=time.perf_counter()
    sequence=test.current_sequence
    step_started=time.perf_counter()
    existing=AptitudeTestQuestion.query.filter_by(test_id=test.id,sequence_no=sequence).first()
    _timing(test.id,"existing_question_query",step_started,found=bool(existing))
    if existing:return existing
    schedule=build_slots(
        test.focus_category,seed=test.id,
        category_counts=test.mixed_category_counts if not test.focus_category else None,
        technical_language=test.technical_language,
        topics_by_category=mixed_attempt_topic_schedules(test) if not test.focus_category else None,
    )
    if sequence<1 or sequence>len(schedule):raise ValueError("adaptive question sequence is outside the test schedule")
    slot=dict(schedule[sequence-1])
    step_started=time.perf_counter()
    difficulty,reason=determine_next_difficulty(test,slot["category"])
    _timing(test.id,"adaptive_difficulty",step_started,category=slot["category"],difficulty=difficulty)
    slot["difficulty"]=difficulty
    question=_persist_question(test,sequence,slot,reason,"adaptive_question_generated","adaptive-v1")
    _timing(test.id,"ensure_question_total",total_started,sequence=sequence)
    current_app.logger.info("Adaptive difficulty test=%s sequence=%s category=%s difficulty=%s reason=%s",test.id,sequence,question.category,difficulty,reason)
    return question


def ensure_category_question(test):
    total_started=time.perf_counter()
    sequence=test.current_sequence
    step_started=time.perf_counter()
    existing=AptitudeTestQuestion.query.filter_by(test_id=test.id,sequence_no=sequence).first()
    _timing(test.id,"existing_question_query",step_started,found=bool(existing))
    if existing:return existing
    topics=attempt_topic_schedule(test,test.total_questions)
    schedule=build_category_slots(test.selected_category,test.selected_level,topics,technical_language=test.technical_language)
    if sequence<1 or sequence>len(schedule):raise ValueError("category-practice sequence is outside the test schedule")
    slot=dict(schedule[sequence-1])
    question=_persist_question(test,sequence,slot,None,"category_question_generated","category-fixed-v1")
    _timing(test.id,"ensure_question_total",total_started,sequence=sequence)
    current_app.logger.info("Fixed category practice test=%s sequence=%s category=%s level=%s difficulty=%s",test.id,sequence,question.category,test.selected_level,question.difficulty)
    return question


def ensure_test_question(test):
    if getattr(test,"test_mode","mixed")=="category_practice":return ensure_category_question(test)
    return ensure_adaptive_question(test)


def difficulty_metrics(test):
    by_category={}
    for question in test.questions:
        by_category.setdefault(question.category,[]).append(question)
    categories=[]
    for category,questions in by_category.items():
        levels=[DIFFICULTY_LEVEL[question.difficulty] for question in questions]
        average=sum(levels)/len(levels);average_label=_average_label(average)
        peak=max(questions,key=lambda question:DIFFICULTY_LEVEL[question.difficulty]).difficulty
        answered=[question for question in questions if question.answer]
        correct=sum(int(question.answer.is_correct) for question in answered)
        categories.append({"category":category,"questions":len(questions),"accuracy":round(correct/len(answered)*100,1) if answered else 0,"average_level":round(average,2),"average_difficulty":average_label,"peak_difficulty":peak})
    all_levels=[DIFFICULTY_LEVEL[question.difficulty] for question in test.questions]
    if not all_levels:return {"average_difficulty":None,"average_level":0,"peak_difficulty":None,"peak_categories":[],"difficulty_by_category":[]}
    overall=sum(all_levels)/len(all_levels);peak_level=max(all_levels);peak=DIFFICULTIES[peak_level-1]
    peak_categories=[row["category"] for row in categories if row["peak_difficulty"]==peak]
    return {"average_difficulty":_average_label(overall),"average_level":round(overall,2),"peak_difficulty":peak,"peak_categories":peak_categories,"difficulty_by_category":categories}

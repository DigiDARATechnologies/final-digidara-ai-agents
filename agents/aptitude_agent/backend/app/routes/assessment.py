from datetime import datetime, timezone
import time
import uuid
from io import BytesIO
from flask import Blueprint, current_app, g, request, send_file
from ..extensions import db
from ..models import AIRecommendation, AptitudeAnswer, AptitudeTest, AptitudeTestQuestion, Student
from ..services.adaptive_service import ensure_test_question, schedule_next_question_prefetch, schedule_test_prefetch
from ..services.analytics_service import analytics_payload
from ..services.hint_service import HintUnavailable, generate_hint
from ..services.prefetch_service import cache_hint, clear_hint, clear_test_cache, get_cached_hint
from ..services.ai_service import AIProviderError
ProviderError = AIProviderError
from ..services.audit_service import record_event
from ..services.evaluation_service import evaluate_answer
from ..services.job_service import abandon_stale_tests, enqueue_job
from ..services.mixed_test_config_service import mixed_counts_by_name
from ..services.pdf_service import generate_test_results_pdf
from ..services.recommendation_service import generate_recommendation
from ..services.rate_limit_service import mysql_rate_limit
from ..services.test_generation import CATEGORY_LEVELS, CATEGORY_PRACTICE_QUESTION_COUNT, CATEGORIES, DEFAULT_TECHNICAL_LANGUAGE, TECHNICAL_LANGUAGES, build_category_slots, build_slots
from ..services.topic_selection_service import (
    save_last_topics,save_mixed_topics,select_mixed_topics_for_attempt,
    select_topics_for_attempt,
)
from ..services.usage_service import record_usage
from ..topic_config import topic_is_starred
from ..utils.authentication import require_student
from ..utils.explanation import normalize_explanation
from ..utils.errors import APIError
from .common import elapsed_seconds, owned_test, public_question, test_summary, utcnow

bp=Blueprint("assessment",__name__,url_prefix="/api/aptitude")

RECOMMENDATION_FALLBACK="We couldn't generate a personalized recommendation this time. Review your incorrect answers to see where to focus."
MAX_RECOMMENDATION_ATTEMPTS=3


def log_timing(endpoint,test_id,step,started):
    duration_ms=(time.perf_counter()-started)*1000
    current_app.logger.info(
        "Assessment timing endpoint=%s test=%s step=%s duration_ms=%.2f",
        endpoint,test_id,step,duration_ms,
    )
    return duration_ms


def synchronous_recommendation(test):
    """Resolve and persist one final recommendation during Results loading."""
    recommendation=AIRecommendation.query.filter_by(test_id=test.id).first()
    if recommendation and recommendation.recommendation_text and recommendation.status=="completed":
        return recommendation
    if (
        recommendation and recommendation.recommendation_text
        and recommendation.status=="failed"
        and recommendation.attempt_count>=MAX_RECOMMENDATION_ATTEMPTS
    ):
        return recommendation
    if not recommendation:
        recommendation=AIRecommendation(id=str(uuid.uuid4()),test_id=test.id,student_id=test.student_id,status="pending",attempt_count=0)
        db.session.add(recommendation)

    started=time.perf_counter()
    recommendation.status="processing"
    recommendation.attempt_count=(recommendation.attempt_count or 0)+1
    timeout=current_app.config["RECOMMENDATION_TIMEOUT_SECONDS"]
    try:
        text,model,usage=generate_recommendation(
            analytics_payload([test]),
            deadline=time.monotonic()+timeout,
            timeout=timeout,
        )
        recommendation.recommendation_text=text
        recommendation.model_version=model
        recommendation.status="completed"
        recommendation.last_error=None
        if any(int(usage.get(key,0) or 0)>0 for key in ("input_tokens","output_tokens","total_tokens")):
            record_usage(test.student_id,"recommendation",model,usage,test.id)
        current_app.logger.info(
            "Recommendation timing test=%s status=completed duration_ms=%.2f model=%s provider_wait_ms=%s retry_count=%s",
            test.id,(time.perf_counter()-started)*1000,model,usage.get("provider_wait_ms",0),usage.get("provider_retry_count",0),
        )
    except Exception as exc:
        recommendation.recommendation_text=RECOMMENDATION_FALLBACK
        recommendation.model_version="deterministic-fallback"
        recommendation.status="failed"
        recommendation.last_error=f"{type(exc).__name__}: {str(exc)}"[:500]
        current_app.logger.warning(
            "Recommendation fallback test=%s learner=%s mode=%s category=%s "
            "attempt=%s/%s duration_ms=%.2f error_type=%s error_kind=%s "
            "status_code=%s retry_after=%s error=%s",
            test.id,test.student_id,test.test_mode,
            test.selected_category or "Mixed Test",recommendation.attempt_count,
            MAX_RECOMMENDATION_ATTEMPTS,(time.perf_counter()-started)*1000,
            type(exc).__name__,getattr(exc,"kind",None),
            getattr(exc,"status_code",None),getattr(exc,"retry_after",None),
            str(exc)[:500],
        )
    db.session.commit()
    return recommendation


def prepare_question(test):
    try:
        return ensure_test_question(test)
    except ProviderError as exc:
        db.session.rollback()
        if exc.kind=="rate_limit":
            raise APIError("AI generation is temporarily rate-limited. Please wait a few minutes and try again.",503,"ai_rate_limited") from exc
        raise APIError("AI generation is temporarily unavailable. Please try again shortly.",503,"ai_unavailable") from exc
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Question preparation failed for test %s: %s",test.id,str(exc)[:200])
        raise APIError("We could not prepare the next question right now. Please try again.",503,"question_generation_failed") from exc


def prepared_question_or_generate(test):
    item=AptitudeTestQuestion.query.filter_by(test_id=test.id,sequence_no=test.current_sequence).first()
    if item:
        return item
    return prepare_question(test)


def abandon_attempt(test,reason):
    """Forfeit an active attempt without deleting its audit/history record."""
    if test.status not in {"generating","ready","in_progress"}:
        return False
    test.status="abandoned"
    clear_test_cache(test.id)
    test.last_activity_at=utcnow()
    record_event("test_abandoned",test.student_id,test.id,{"reason":reason,"answered_count":max(0,test.current_sequence-1)})
    return True

@bp.post("/tests")
@require_student
@mysql_rate_limit(
    "start_test",10,3600,
    limit_config="START_TEST_RATE_LIMIT",
    window_config="START_TEST_RATE_WINDOW_SECONDS",
)
def create_test():
    body=request.get_json(silent=True) or {}
    if not isinstance(body,dict):raise APIError("Request body must be a JSON object",400,"invalid_request")
    mode=str(body.get("mode") or "mixed").strip()
    if mode not in {"mixed","category_practice"}:raise APIError("mode must be mixed or category_practice",400,"invalid_test_mode")
    category=str(body.get("category") or "").strip() or None
    level=str(body.get("level") or "").strip() or None
    requested_language=str(body.get("technical_language") or DEFAULT_TECHNICAL_LANGUAGE).strip()
    language_by_key={language.casefold():language for language in TECHNICAL_LANGUAGES}
    if requested_language.casefold() not in language_by_key:
        raise APIError("Choose C, Java, Python or SQL",400,"invalid_technical_language")
    requested_language=language_by_key[requested_language.casefold()]
    test_id=str(uuid.uuid4())
    selected_topics=None
    mixed_counts=None
    mixed_topics=None
    if mode=="category_practice":
        if category not in CATEGORIES:raise APIError("Choose a valid aptitude category",400,"invalid_category")
        if level not in CATEGORY_LEVELS:raise APIError("Choose Beginner, Intermediate or Advanced",400,"invalid_level")
        selected_topics=select_topics_for_attempt(
            g.student.id,category,level,CATEGORY_PRACTICE_QUESTION_COUNT,
        )
        technical_language=requested_language if category=="Technical Aptitude" else None
        slots=build_category_slots(category,level,selected_topics,technical_language=technical_language)
    else:
        if category and category not in CATEGORIES:raise APIError("Choose a valid aptitude category",400,"invalid_category")
        if category or level:raise APIError("Category and level are only accepted for category practice",400,"invalid_mixed_configuration")
        mixed_counts=mixed_counts_by_name(g.student.id)
        mixed_topics=select_mixed_topics_for_attempt(g.student.id,mixed_counts)
        technical_language=requested_language
        slots=build_slots(
            seed=test_id,category_counts=mixed_counts,
            technical_language=technical_language,topics_by_category=mixed_topics,
        )
        if not slots:raise APIError("Select at least one question",400,"empty_mixed_test")
    abandon_stale_tests(g.student.id)
    db.session.query(Student).filter_by(id=g.student.id).with_for_update().one()
    active_tests=AptitudeTest.query.filter(AptitudeTest.student_id==g.student.id,AptitudeTest.status.in_(["generating","ready","in_progress"])).with_for_update().all()
    for active in active_tests:
        abandon_attempt(active,"superseded_by_new_test")
    hint_budget=2 if mode=="category_practice" else current_app.config["HINTS_PER_TEST"]
    test=AptitudeTest(id=test_id,student_id=g.student.id,status="generating",total_questions=len(slots),test_mode=mode,selected_category=category if mode=="category_practice" else None,selected_level=level if mode=="category_practice" else None,technical_language=technical_language,focus_category=None,mixed_category_counts=mixed_counts,hints_allowed=hint_budget)
    if selected_topics:
        # Question one is generated before the successful topic schedule is
        # persisted, so keep the planned schedule on this ORM instance.
        test._category_topic_schedule=list(selected_topics)
    if mixed_topics:
        # Preserve the selected schedules until successful generation commits
        # them to the shared learner history rows.
        test._mixed_topic_schedules={
            category:list(topics) for category,topics in mixed_topics.items()
        }
    db.session.add(test)
    # AuditEvent references the new test. Flush the parent first so MySQL's
    # foreign-key check never observes the audit row before aptitude_tests.
    db.session.flush()
    record_event("test_created",g.student.id,test.id)
    db.session.commit()
    try:
        question=ensure_test_question(test)
        if mode=="category_practice":
            save_last_topics(
                g.student.id,category,level,
                getattr(test,"_category_topic_schedule",selected_topics),
            )
        else:
            save_mixed_topics(
                g.student.id,getattr(test,"_mixed_topic_schedules",mixed_topics),
            )
        test.status="ready";test.last_activity_at=utcnow();record_event("generation_completed",g.student.id,test.id,{"model":question.generation_model,"mode":mode,"adaptive":mode=="mixed"});db.session.commit()
        return {"test_id":test.id,"status":test.status},201
    except ProviderError as exc:
        clear_test_cache(test.id)
        db.session.rollback();test=db.session.get(AptitudeTest,test.id);test.status="failed";record_event("generation_failed",g.student.id,test.id,{"error_type":exc.kind});db.session.commit()
        if exc.kind=="rate_limit":
            raise APIError("AI generation is temporarily rate-limited. Please wait a few minutes and try again.",503,"ai_rate_limited") from exc
        raise APIError("AI generation is temporarily unavailable. Please try again shortly.",503,"ai_unavailable") from exc
    except Exception as exc:
        clear_test_cache(test.id)
        db.session.rollback();test=db.session.get(AptitudeTest,test.id);test.status="failed";record_event("generation_failed",g.student.id,test.id,{"error_type":type(exc).__name__,"reason":str(exc)[:200]});db.session.commit();current_app.logger.exception("Test generation failed: %s",str(exc)[:200])
        raise APIError("We could not prepare a quality assessment right now. Please try again shortly.",503,"generation_failed") from exc

@bp.get("/tests/<test_id>/status")
@require_student
def status(test_id):
    test=owned_test(test_id);return {"test_id":test.id,"status":test.status}


@bp.get("/tests/<test_id>/question")
@require_student
def question(test_id):
    total_started=time.perf_counter();step_started=time.perf_counter()
    test=owned_test(test_id);log_timing("question",test_id,"owned_test_query",step_started)
    if test.status=="ready":test.status="in_progress"
    if test.status!="in_progress":raise APIError("This assessment is not active",409,"test_not_active")
    step_started=time.perf_counter();item=prepared_question_or_generate(test);log_timing("question",test_id,"prepared_question_query",step_started)
    if item.answer:raise APIError("This question has already been answered",409,"already_answered")
    if item.question_started_at:
        abandon_attempt(test,"question_reentry_attempt")
        db.session.commit()
        raise APIError("This attempt has ended and cannot be resumed. Start a new test.",409,"attempt_not_resumable")
    if not item.question_started_at:item.question_started_at=utcnow()
    test.last_activity_at=utcnow();record_event("question_served",g.student.id,test.id,{"sequence":item.sequence_no});step_started=time.perf_counter();db.session.commit();log_timing("question",test_id,"db_commit",step_started)
    schedule_next_question_prefetch(test,item.sequence_no)
    log_timing("question",test_id,"total",total_started)
    return public_question(item,test)


@bp.post("/tests/<test_id>/abandon")
@require_student
def abandon(test_id):
    owned_test(test_id)
    test=db.session.query(AptitudeTest).filter_by(id=test_id,student_id=g.student.id).with_for_update().one()
    changed=abandon_attempt(test,"student_exit")
    if changed:
        db.session.commit()
    return {"test_id":test.id,"status":test.status,"abandoned":changed}

@bp.post("/tests/<test_id>/hint")
@require_student
@mysql_rate_limit("request_hint",10,60)
def hint(test_id):
    total_started=time.perf_counter();step_started=time.perf_counter()
    test=owned_test(test_id);log_timing("hint",test_id,"initial_test_query",step_started)
    if test.status!="in_progress":raise APIError("This assessment is not active",409,"test_not_active")
    item=db.session.query(AptitudeTestQuestion).filter_by(test_id=test.id,sequence_no=test.current_sequence).first()
    if not item or not item.question_started_at:raise APIError("Fetch the current question before requesting a hint",409,"question_not_started")
    if AptitudeAnswer.query.filter_by(question_id=item.id).first():raise APIError("A hint is not available after answering",409,"already_answered")
    cached_hint=get_cached_hint(test.id,item.id)
    if cached_hint:
        return {"hint":cached_hint,"hints_used":test.hints_used,"hints_remaining":max(0,test.hints_allowed-test.hints_used)}
    if not item.hint_requested and test.hints_used>=test.hints_allowed:raise APIError("No conceptual hints remain for this assessment",409,"no_hints_remaining")
    if elapsed_seconds(item)>item.allowed_time_seconds+current_app.config["TIMEOUT_GRACE_SECONDS"]:raise APIError("The question time has expired",409,"question_timed_out")
    question_id=item.id
    step_started=time.perf_counter()
    try:
        hint_text,usage=generate_hint(item)
    except HintUnavailable as exc:
        raise APIError(str(exc),503,"hint_unavailable") from exc
    log_timing("hint",test_id,"provider_and_safety",step_started)

    # End the read-only transaction before taking write locks. No database row
    # is locked while the external provider is running.
    db.session.rollback();step_started=time.perf_counter()
    test=db.session.query(AptitudeTest).filter_by(id=test_id,student_id=g.student.id).with_for_update().one()
    item=db.session.query(AptitudeTestQuestion).filter_by(id=question_id,test_id=test.id).with_for_update().one()
    if test.status!="in_progress" or test.current_sequence!=item.sequence_no:raise APIError("This assessment is not active",409,"test_not_active")
    if AptitudeAnswer.query.filter_by(question_id=item.id).first():raise APIError("A hint is not available after answering",409,"already_answered")
    cached_hint=get_cached_hint(test.id,item.id)
    if cached_hint:
        db.session.rollback()
        return {"hint":cached_hint,"hints_used":test.hints_used,"hints_remaining":max(0,test.hints_allowed-test.hints_used)}
    if not item.hint_requested and test.hints_used>=test.hints_allowed:raise APIError("No conceptual hints remain for this assessment",409,"no_hints_remaining")
    if elapsed_seconds(item)>item.allowed_time_seconds+current_app.config["TIMEOUT_GRACE_SECONDS"]:raise APIError("The question time has expired",409,"question_timed_out")
    log_timing("hint",test_id,"write_lock_and_revalidate",step_started)
    first_request=not item.hint_requested
    item.hint_requested=True;item.hint_requested_at=item.hint_requested_at or utcnow()
    if first_request:test.hints_used+=1
    test.last_activity_at=utcnow()
    source="deterministic_fallback" if usage.get("fallback") else "live_openai"
    if any(int(usage.get(key,0) or 0)>0 for key in ("input_tokens","output_tokens","total_tokens")):
        record_usage(g.student.id,"hint_generation",usage.get("model") or "deterministic-fallback",usage,test.id,item.id)
    record_event("hint_requested",g.student.id,test.id,{"sequence":item.sequence_no,"hints_used":test.hints_used,"source":source})
    step_started=time.perf_counter();db.session.commit();cache_hint(test.id,item.id,hint_text);log_timing("hint",test_id,"db_commit",step_started)
    log_timing("hint",test_id,"total",total_started)
    return {"hint":hint_text,"hints_used":test.hints_used,"hints_remaining":max(0,test.hints_allowed-test.hints_used)}

@bp.post("/tests/<test_id>/answer")
@require_student
@mysql_rate_limit("submit_answer",30,60)
def answer(test_id):
    total_started=time.perf_counter();step_started=time.perf_counter()
    test=owned_test(test_id);log_timing("answer",test_id,"owned_test_query",step_started)
    if test.status!="in_progress":raise APIError("This assessment is not active",409,"test_not_active")
    step_started=time.perf_counter();item=db.session.query(AptitudeTestQuestion).filter_by(test_id=test.id,sequence_no=test.current_sequence).with_for_update().first();log_timing("answer",test_id,"current_question_query",step_started)
    if not item or not item.question_started_at:raise APIError("Fetch the current question before submitting",409,"question_not_started")
    step_started=time.perf_counter();existing_answer=AptitudeAnswer.query.filter_by(question_id=item.id).first();log_timing("answer",test_id,"existing_answer_query",step_started)
    if existing_answer:raise APIError("Answer already submitted",409,"already_answered")
    body=request.get_json(silent=True) or {}
    if not isinstance(body,dict):raise APIError("Request body must be a JSON object",400,"invalid_request")
    selected=str(body.get("selected_answer") or "").upper()
    if selected not in {"","A","B","C","D"}:raise APIError("selected_answer must be A, B, C or D",400,"invalid_answer")
    elapsed=elapsed_seconds(item);timed_out=elapsed>item.allowed_time_seconds+current_app.config["TIMEOUT_GRACE_SECONDS"] or (bool(body.get("timed_out")) and elapsed>=item.allowed_time_seconds-1)
    if not selected and not timed_out:raise APIError("Select an answer before submitting",400,"answer_required")
    step_started=time.perf_counter();verdict,source=(False,"timeout") if timed_out else evaluate_answer(item,selected);log_timing("answer",test_id,"evaluate_answer",step_started)
    submitted=AptitudeAnswer(id=str(uuid.uuid4()),test_id=test.id,student_id=g.student.id,question_id=item.id,selected_answer=selected or None,correct_answer=item.correct_answer,is_correct=verdict,timed_out=timed_out,time_taken_seconds=min(elapsed,item.allowed_time_seconds),evaluation_source=source)
    step_started=time.perf_counter();db.session.add(submitted);test.correct_count+=int(verdict);test.wrong_count+=int(not verdict and not timed_out);test.timed_out_count+=int(timed_out);test.total_time_seconds+=submitted.time_taken_seconds;test.last_activity_at=utcnow();db.session.flush();log_timing("answer",test_id,"db_flush",step_started)
    complete=test.current_sequence>=test.total_questions
    if complete:
        percentage=round(test.correct_count/test.total_questions*100,2) if test.total_questions else 0
        test.status="completed";test.completed_at=utcnow();test.score=test.correct_count;test.percentage=percentage
        enqueue_job("analytics",g.student.id,test.id);record_event("test_completed",g.student.id,test.id,{"score":test.score})
    else:
        test.current_sequence+=1
        # The next screen generates its question live. A temporary Groq
        # outage therefore never rolls back an answer the learner submitted.
    record_event("answer_submitted",g.student.id,test.id,{"sequence":item.sequence_no,"timed_out":timed_out,"evaluation_source":source});step_started=time.perf_counter();db.session.commit();log_timing("answer",test_id,"db_commit",step_started)
    clear_hint(test.id,item.id)
    if complete:clear_test_cache(test.id)
    else:schedule_test_prefetch(test,test.current_sequence)
    log_timing("answer",test_id,"total",total_started)
    return {"is_correct":verdict,"timed_out":timed_out,"correct_answer":item.correct_answer,"explanation":normalize_explanation(item.explanation),"evaluation_source":source,"hint_requested":bool(item.hint_requested),"complete":complete,"next_sequence":None if complete else test.current_sequence}

@bp.get("/tests/<test_id>")
@require_student
def detail(test_id):
    test=owned_test(test_id)
    if test.status!="completed":raise APIError("Results are available after completion",409,"results_unavailable")
    recommendation=synchronous_recommendation(test)
    return {**test_summary(test),"questions":[{"sequence":q.sequence_no,"category":q.category,"topic":q.topic,"topic_is_starred":topic_is_starred(q.category,q.topic),"difficulty":q.difficulty,"difficulty_reason":q.difficulty_reason,"question":q.question_text,"options":q.options,"selected_answer":q.answer.selected_answer if q.answer else None,"correct_answer":q.correct_answer,"is_correct":q.answer.is_correct if q.answer else False,"timed_out":q.answer.timed_out if q.answer else True,"time_taken_seconds":q.answer.time_taken_seconds if q.answer else 0,"hint_requested":bool(q.hint_requested),"hint_text":None,"explanation":normalize_explanation(q.explanation)} for q in test.questions],"recommendation":recommendation.recommendation_text,"recommendation_status":recommendation.status}


@bp.get("/tests/<test_id>/download")
@require_student
def download_results(test_id):
    test=db.session.get(AptitudeTest,test_id)
    if not test:
        raise APIError("Assessment not found",404,"test_not_found")
    if test.student_id!=g.student.id:
        raise APIError("You do not have permission to download this assessment",403,"test_forbidden")
    if test.status!="completed":
        raise APIError("Results can only be downloaded after completion",409,"results_unavailable")
    try:
        pdf=generate_test_results_pdf(test,g.student)
    except Exception:
        current_app.logger.exception(
            "Assessment PDF generation failed test=%s learner=%s mode=%s",
            test.id,g.student.id,test.test_mode,
        )
        raise
    date=(test.completed_at or utcnow()).strftime("%Y-%m-%d")
    filename=f"test-results-{date}-{test.id}.pdf"
    record_event("test_results_downloaded",g.student.id,test.id,{"filename":filename})
    db.session.commit()
    return send_file(
        BytesIO(pdf),mimetype="application/pdf",as_attachment=True,
        download_name=filename,max_age=0,
    )

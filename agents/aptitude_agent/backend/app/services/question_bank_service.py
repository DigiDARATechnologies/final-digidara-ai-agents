"""Serve learner questions exclusively from the pre-built MySQL bank."""
from sqlalchemy import case, func, or_
from flask import current_app
from ..extensions import db
from ..models import BackgroundJob, QuestionBankItem, RecentQuestionHash
from .hint_service import TOPIC_HINTS
from .question_validation import questions_are_near_duplicates
from .test_generation import CATEGORIES, generate_questions


class QuestionBankUnavailable(RuntimeError):
    pass


def select_approved_item(student_id, category, topic, difficulty, strict_topic=False, excluded_question_texts=()):
    history_limit=__import__("flask").current_app.config["BANK_RECENT_HISTORY_LIMIT"]
    recent=RecentQuestionHash.query.filter_by(student_id=student_id).order_by(RecentQuestionHash.created_at.desc()).limit(history_limit).all()
    seen_hashes=[row.content_hash for row in recent]
    seen_structures=[row.structural_hash for row in recent if row.structural_hash]
    topic_rank=case((QuestionBankItem.topic==topic,0),else_=1)
    query=(
        db.session.query(QuestionBankItem)
        .filter(
            QuestionBankItem.status=="approved",
            QuestionBankItem.category==category,
            QuestionBankItem.difficulty==difficulty,
            *( [~QuestionBankItem.content_hash.in_(seen_hashes)] if seen_hashes else [] ),
            *( [or_(QuestionBankItem.structural_hash.is_(None),~QuestionBankItem.structural_hash.in_(seen_structures))] if seen_structures else [] ),
        )
    )
    if strict_topic:query=query.filter(QuestionBankItem.topic==topic)
    candidates=(query
        .order_by(topic_rank,QuestionBankItem.times_used.asc(),func.rand())
        .with_for_update(skip_locked=True)
        .limit(30).all()
    )
    item=next((candidate for candidate in candidates if not any(
        questions_are_near_duplicates(candidate.question_text,seen_text)
        for seen_text in excluded_question_texts
    )),None)
    if not item:
        from flask import current_app
        bank_total=QuestionBankItem.query.filter_by(status="approved").count()
        if bank_total==0:
            current_app.logger.error(
                "Question bank is empty: learner test cannot start until pool_replenish jobs complete. "
                "Start worker.py and run flask seed-question-bank --local for a fresh local environment."
            )
        else:
            current_app.logger.warning(
                "Question bank shortage category=%s difficulty=%s approved_total=%s",
                category,difficulty,bank_total,
            )
        raise QuestionBankUnavailable(
            f"More approved questions are needed for {category} at {difficulty} level right now. "
            "Try a different category or difficulty, or check back shortly."
        )
    return item


def assert_bank_capacity(category,difficulty,required_count):
    """Fail test creation early instead of creating an unusable partial attempt."""
    available=QuestionBankItem.query.filter_by(category=category,difficulty=difficulty,status="approved").count()
    if available<required_count:
        from flask import current_app
        if QuestionBankItem.query.filter_by(status="approved").count()==0:
            current_app.logger.error("Question bank is empty during test-start capacity check")
        raise QuestionBankUnavailable(
            f"More approved questions are needed for {category} at {difficulty} level right now. "
            "Try a different category or difficulty, or check back shortly."
        )


def _hint_for(topic):
    return TOPIC_HINTS.get(topic,"Identify the core concept being tested and eliminate options that do not follow its rule.")


def generate_bank_batch(category,difficulty,count):
    """Worker-only OpenAI factory. Never call this from learner-facing routes."""
    from flask import current_app
    if not current_app.config.get("OPENAI_API_KEY"):
        raise QuestionBankUnavailable("OpenAI is unavailable; the bank factory will retry when it returns")
    current_app.logger.info(
        "Question bank factory started category=%s difficulty=%s requested=%s",
        category,difficulty,count,
    )
    topics=CATEGORIES[category]
    existing=QuestionBankItem.query.filter_by(category=category,difficulty=difficulty).order_by(QuestionBankItem.created_at.desc()).limit(500).all()
    existing_texts=[row.question_text for row in existing]
    slots=[{"category":category,"topic":topics[index%len(topics)],"difficulty":difficulty} for index in range(count)]
    items=[];model=None;usage={"input_tokens":0,"output_tokens":0,"total_tokens":0}
    batch_size=current_app.config["BANK_GENERATION_BATCH_SIZE"]
    failures=[]
    for start in range(0,len(slots),batch_size):
        if start:
            import time
            delay=current_app.config["BANK_OPENAI_CALL_INTERVAL_SECONDS"]
            current_app.logger.info("Question bank factory throttling next OpenAI call delay_seconds=%s",delay)
            time.sleep(delay)
        chunk=slots[start:start+batch_size]
        current_app.logger.info(
            "Question bank factory OpenAI chunk category=%s difficulty=%s chunk=%s-%s of %s",
            category,difficulty,start+1,start+len(chunk),len(slots),
        )
        try:
            generated,chunk_model,chunk_usage=generate_questions(
                chunk,[*existing_texts,*(item["question"] for item in items)],allow_demo_fallback=False,background=True,
            )
        except Exception as exc:
            failures.append(str(exc)[:180])
            current_app.logger.warning(
                "Question bank factory skipped failed chunk category=%s difficulty=%s chunk=%s-%s error=%s",
                category,difficulty,start+1,start+len(chunk),str(exc)[:220],
            )
            continue
        items.extend(generated);model=chunk_model or model
        for key in ("input_tokens","output_tokens","total_tokens"):
            usage[key]+=int(chunk_usage.get(key,0) or 0)
        usage["model"]=chunk_usage.get("model") or model
    inserted=[]
    for item in items:
        if any(questions_are_near_duplicates(item["question"],text) for text in [*existing_texts,*(row.question_text for row in inserted)]):
            current_app.logger.warning(
                "Question bank factory rejected duplicate category=%s difficulty=%s",
                category,difficulty,
            )
            continue
        row=QuestionBankItem(
            id=str(__import__("uuid").uuid4()),category=item["category"],topic=item["topic"],difficulty=item["difficulty"],
            question_text=item["question"],option_a=item["options"]["A"],option_b=item["options"]["B"],option_c=item["options"]["C"],option_d=item["options"]["D"],
            correct_answer=item["correct_answer"],explanation=item["explanation"],hint_text=_hint_for(item["topic"]),
            content_hash=item["content_hash"],structural_hash=item["structural_hash"],status="approved",source_model=model,prompt_version="bank-factory-v1",
        )
        db.session.add(row);inserted.append(row)
    if not inserted:
        raise QuestionBankUnavailable(
            f"Bank factory generated no usable unique questions for {category} / {difficulty}: "
            f"{failures[-1] if failures else 'all candidates were duplicates'}"
        )
    current_app.logger.info(
        "Question bank factory validated category=%s difficulty=%s generated=%s inserted=%s model=%s",
        category,difficulty,len(items),len(inserted),model,
    )
    return inserted,model,usage


def enqueue_bank_replenishment():
    """Schedule missing pools without permanently deduping failed attempts.

    The hourly bucket prevents scheduler spam while ensuring a combo whose
    approved count is unchanged after a failed job gets a fresh retry later.
    """
    from datetime import datetime, timezone
    from .job_service import enqueue_job
    from flask import current_app
    target=current_app.config["BANK_TARGET_SIZE"];threshold=current_app.config["BANK_REFILL_THRESHOLD"]
    hour_key=datetime.now(timezone.utc).strftime("%Y%m%d%H")
    queued=0
    for category in CATEGORIES:
        for difficulty in ("Easy","Medium","Hard"):
            count=QuestionBankItem.query.filter_by(category=category,difficulty=difficulty,status="approved").count()
            if count<threshold:
                active=BackgroundJob.query.filter(
                    BackgroundJob.job_type=="pool_replenish",
                    BackgroundJob.status.in_(("pending","processing")),
                ).all()
                if any((job.payload_json or {}).get("category")==category and (job.payload_json or {}).get("difficulty")==difficulty for job in active):
                    continue
                requested=min(current_app.config["BANK_REPLENISH_BATCH_SIZE"],target-count)
                if requested>0:
                    enqueue_job("pool_replenish",None,None,{"category":category,"difficulty":difficulty,"count":requested},f"pool-replenish:{category}:{difficulty}:{count}:{hour_key}")
                    queued+=1
    return queued


def bank_pool_status():
    """Small operational snapshot; never exposes question content."""
    rows=QuestionBankItem.query.with_entities(
        QuestionBankItem.category,QuestionBankItem.difficulty,QuestionBankItem.status,db.func.count(QuestionBankItem.id)
    ).filter(QuestionBankItem.status.in_(("approved","archived"))).group_by(
        QuestionBankItem.category,QuestionBankItem.difficulty,QuestionBankItem.status
    ).all()
    counts={}
    archived_counts={}
    for category,difficulty,status,count in rows:
        (counts if status=="approved" else archived_counts)[(category,difficulty)]=count
    combinations=[(category,difficulty) for category in CATEGORIES for difficulty in ("Easy","Medium","Hard")]
    usable_min=5
    target=current_app.config["BANK_TARGET_SIZE"]
    combination_rows=[{
        "category":category,
        "difficulty":difficulty,
        "approved_count":counts.get((category,difficulty),0),
        "archived_count":archived_counts.get((category,difficulty),0),
        "usable":counts.get((category,difficulty),0)>=usable_min,
        "target_gap":max(0,target-counts.get((category,difficulty),0)),
    } for category,difficulty in combinations]
    combination_rows.sort(key=lambda row:(row["approved_count"],row["category"],row["difficulty"]))
    return {
        "approved_total":sum(counts.values()),
        "combinations_total":len(combinations),
        "combinations_with_questions":sum(counts.get(combo,0)>0 for combo in combinations),
        "combinations_usable":sum(counts.get(combo,0)>=usable_min for combo in combinations),
        "minimum_per_combination":usable_min,
        "combinations":combination_rows,
    }


def bootstrap_question_bank(local=False):
    """Queue every empty/critical pool immediately for a fresh installation."""
    from datetime import datetime, timezone
    from .job_service import enqueue_job
    from flask import current_app
    batch=(current_app.config["BANK_BOOTSTRAP_LOCAL_BATCH_SIZE"] if local else current_app.config["BANK_BOOTSTRAP_PRODUCTION_BATCH_SIZE"])
    run_key=datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    queued=0
    for category in CATEGORIES:
        for difficulty in ("Easy","Medium","Hard"):
            count=QuestionBankItem.query.filter_by(category=category,difficulty=difficulty,status="approved").count()
            if count>=batch:
                continue
            active=BackgroundJob.query.filter(
                BackgroundJob.job_type=="pool_replenish",
                BackgroundJob.status.in_(("pending","processing")),
            ).all()
            if any((job.payload_json or {}).get("category")==category and (job.payload_json or {}).get("difficulty")==difficulty for job in active):
                continue
            requested=batch-count
            enqueue_job("pool_replenish",None,None,{"category":category,"difficulty":difficulty,"count":requested,"bootstrap":True},f"bank-bootstrap:{run_key}:{category}:{difficulty}")
            queued+=1
    status=bank_pool_status()
    current_app.logger.info(
        "Question bank bootstrap queued=%s approved=%s usable_combinations=%s/%s",
        queued,status["approved_total"],status["combinations_usable"],status["combinations_total"],
    )
    return queued,status


def archive_low_quality_questions():
    from flask import current_app
    minimum=current_app.config["BANK_QUALITY_MIN_ATTEMPTS"]
    lower=current_app.config["BANK_QUALITY_MIN_ACCURACY"]
    upper=current_app.config["BANK_QUALITY_MAX_ACCURACY"]
    rows=QuestionBankItem.query.filter(QuestionBankItem.status=="approved",QuestionBankItem.attempt_count>=minimum).all()
    archived=0
    for item in rows:
        accuracy=item.correct_count/max(1,item.attempt_count)
        if accuracy<lower or accuracy>upper:
            item.status="archived";archived+=1
    return archived


def bank_inventory():
    rows=(db.session.query(QuestionBankItem.category,QuestionBankItem.difficulty,QuestionBankItem.status,db.func.count(QuestionBankItem.id)).group_by(QuestionBankItem.category,QuestionBankItem.difficulty,QuestionBankItem.status).all())
    return [{"category":category,"difficulty":difficulty,"status":status,"count":count} for category,difficulty,status,count in rows]
"""Legacy question-bank maintenance implementation.

The live learner application intentionally does not import this module. It is
kept temporarily so the existing schema/data can be inspected or migrated
without a destructive database change. No CLI command, route, worker loop, or
readiness check calls these functions.
"""

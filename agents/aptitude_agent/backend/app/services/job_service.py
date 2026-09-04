from datetime import timedelta
import uuid
from flask import current_app
from ..extensions import db
from ..models import AptitudeTest, BackgroundJob, WorkerHeartbeat
from ..models.base import utcnow
from .analytics_service import recalculate_topic_performance
from .prefetch_service import clear_test_cache


RETIRED_JOB_TYPES=("pool_replenish","bank_quality_curation","adaptive_question","category_question","hint_generation","answer_diagnostics","recommendation")


def enqueue_job(job_type, student_id, test_id=None, payload=None, dedupe_key=None):
    if dedupe_key:
        existing=BackgroundJob.query.filter_by(dedupe_key=dedupe_key).first()
        if existing:return existing
    job=BackgroundJob(id=str(uuid.uuid4()),job_type=job_type,student_id=student_id,test_id=test_id,payload_json=payload or {},dedupe_key=dedupe_key,max_attempts=current_app.config["MAX_JOB_ATTEMPTS"])
    db.session.add(job);return job


def process_next_job(worker_id):
    # A failed job or a diagnostics query can leave an implicit SQLAlchemy
    # transaction open on the scoped worker session. Reset it before claiming
    # the next job so one failure never stops the whole worker loop.
    db.session.rollback()
    now=utcnow()
    with db.session.begin():
        query=db.session.query(BackgroundJob).filter(
            BackgroundJob.status=="pending",BackgroundJob.available_at<=now,
            ~BackgroundJob.job_type.in_(RETIRED_JOB_TYPES),
        )
        job=query.order_by(BackgroundJob.created_at).with_for_update(skip_locked=True).first()
        if not job:return False
        job.status="processing";job.locked_at=now;job.locked_by=worker_id;job.attempt_count+=1
        heartbeat=db.session.get(WorkerHeartbeat,worker_id)
        if heartbeat:heartbeat.status="working";heartbeat.current_job_id=job.id;heartbeat.heartbeat_at=now
    try:
        if job.job_type=="analytics": recalculate_topic_performance(job.student_id)
        elif job.job_type=="abandon_cleanup": _abandon_stale()
        else: raise ValueError(f"Unknown job type: {job.job_type}")
        job.status="completed";job.completed_at=utcnow()
        heartbeat=db.session.get(WorkerHeartbeat,worker_id)
        if heartbeat:heartbeat.status="idle";heartbeat.current_job_id=None;heartbeat.heartbeat_at=utcnow()
        db.session.commit()
    except Exception as exc:
        db.session.rollback();job=db.session.get(BackgroundJob,job.id);job.last_error=str(exc)[:500]
        if job.attempt_count>=job.max_attempts:
            job.status="failed"
        else:
            job.status="pending"
            retry_delay=2**job.attempt_count*10
            job.available_at=utcnow()+timedelta(seconds=retry_delay)
        heartbeat=db.session.get(WorkerHeartbeat,worker_id)
        if heartbeat:heartbeat.status="idle";heartbeat.current_job_id=None;heartbeat.heartbeat_at=utcnow()
        db.session.commit()
        current_app.logger.exception(
            "Background job failed id=%s type=%s attempt=%s/%s payload=%s error=%s",
            job.id,job.job_type,job.attempt_count,job.max_attempts,job.payload_json,str(exc)[:500],
        )
    return True


def update_worker_heartbeat(worker_id,hostname,process_id,status="idle",current_job_id=None):
    heartbeat=db.session.get(WorkerHeartbeat,worker_id)
    if not heartbeat:
        heartbeat=WorkerHeartbeat(worker_id=worker_id,hostname=hostname,process_id=process_id)
        db.session.add(heartbeat)
    heartbeat.status=status;heartbeat.current_job_id=current_job_id;heartbeat.heartbeat_at=utcnow()
    db.session.commit()


def retry_failed_job(job_id,student_id=None):
    query=BackgroundJob.query.filter_by(id=job_id,status="failed").filter(~BackgroundJob.job_type.in_(RETIRED_JOB_TYPES))
    if student_id:query=query.filter_by(student_id=student_id)
    job=query.first()
    if not job:return None
    job.status="pending";job.attempt_count=0;job.available_at=utcnow();job.locked_at=None;job.locked_by=None;job.last_error=None;job.completed_at=None
    db.session.commit();return job


def _abandon_stale():
    cutoff=utcnow()-timedelta(seconds=current_app.config["ABANDON_AFTER_SECONDS"])
    query=AptitudeTest.query.filter(AptitudeTest.status.in_(["generating","ready","in_progress"]),AptitudeTest.last_activity_at<cutoff)
    test_ids=[row[0] for row in query.with_entities(AptitudeTest.id).all()]
    query.update({"status":"abandoned"},synchronize_session=False)
    for test_id in test_ids:clear_test_cache(test_id)


def abandon_stale_tests(student_id=None):
    cutoff=utcnow()-timedelta(seconds=current_app.config["ABANDON_AFTER_SECONDS"])
    query=AptitudeTest.query.filter(AptitudeTest.status.in_(["generating","ready","in_progress"]),AptitudeTest.last_activity_at<cutoff)
    if student_id:query=query.filter(AptitudeTest.student_id==student_id)
    test_ids=[row[0] for row in query.with_entities(AptitudeTest.id).all()]
    changed=query.update({"status":"abandoned"},synchronize_session=False)
    for test_id in test_ids:clear_test_cache(test_id)
    if changed:db.session.commit()
    return changed


def cleanup_operational_data():
    from ..models import RateLimitEvent, RecentQuestionHash
    abandon_stale_tests()
    stale_lock=utcnow()-timedelta(minutes=5)
    BackgroundJob.query.filter(BackgroundJob.status=="processing",BackgroundJob.locked_at<stale_lock).update({"status":"pending","locked_at":None,"locked_by":None,"available_at":utcnow()},synchronize_session=False)
    stale_worker=utcnow()-timedelta(seconds=current_app.config["WORKER_STALE_SECONDS"])
    WorkerHeartbeat.query.filter(
        WorkerHeartbeat.heartbeat_at<stale_worker,
        WorkerHeartbeat.status.notin_(("stopped","dead")),
    ).update({"status":"dead","current_job_id":None},synchronize_session=False)
    cutoff=utcnow()-timedelta(days=2)
    RateLimitEvent.query.filter(RateLimitEvent.created_at<cutoff).delete(synchronize_session=False)
    hash_cutoff=utcnow()-timedelta(days=90)
    RecentQuestionHash.query.filter(RecentQuestionHash.created_at<hash_cutoff).delete(synchronize_session=False)
    # Retire jobs left by the former bank/persistent-prefetch architecture.
    # They remain auditable but can never be claimed or write bank rows.
    BackgroundJob.query.filter(
        BackgroundJob.job_type.in_(RETIRED_JOB_TYPES),
        BackgroundJob.status.in_(("pending","processing")),
    ).update({"status":"completed","completed_at":utcnow(),"locked_at":None,"locked_by":None},synchronize_session=False)
    db.session.commit()

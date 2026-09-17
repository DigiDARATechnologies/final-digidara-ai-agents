from datetime import datetime, timedelta, timezone
from ..extensions import db
from ..models import BackgroundJob, WorkerHeartbeat


RETIRED_JOB_TYPES=("pool_replenish","bank_quality_curation","adaptive_question","category_question","hint_generation","answer_diagnostics","recommendation")


def operations_snapshot(student_id=None, stale_seconds=45):
    now=datetime.now(timezone.utc);cutoff=now-timedelta(seconds=stale_seconds)
    all_workers=WorkerHeartbeat.query.order_by(WorkerHeartbeat.heartbeat_at.desc()).all()
    job_query=BackgroundJob.query.filter(~BackgroundJob.job_type.in_(RETIRED_JOB_TYPES))
    if student_id:job_query=job_query.filter_by(student_id=student_id)
    counts={status:job_query.filter_by(status=status).count() for status in ("pending","processing","completed","failed")}
    oldest=job_query.filter_by(status="pending").order_by(BackgroundJob.created_at.asc()).first()
    failed=job_query.filter_by(status="failed").order_by(BackgroundJob.created_at.desc()).limit(20).all()
    def aware(value):return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
    workers=[worker for worker in all_workers if aware(worker.heartbeat_at)>=cutoff and worker.status not in {"stopped","dead"}]
    return {
        "workers":[{"worker_id":worker.worker_id,"status":worker.status,"online":True,"heartbeat_at":aware(worker.heartbeat_at).isoformat(),"current_job_id":worker.current_job_id} for worker in workers],
        "stale_workers_hidden":len(all_workers)-len(workers),
        "jobs":{**counts,"oldest_pending_seconds":max(0,int((now-aware(oldest.created_at)).total_seconds())) if oldest else 0},
        "failed_jobs":[{"id":job.id,"job_type":job.job_type,"test_id":job.test_id,"attempts":job.attempt_count,"last_error":job.last_error,"created_at":aware(job.created_at).isoformat()} for job in failed],
        "question_bank":{"enabled":False,"mode":"openai_complete_batch"},
    }

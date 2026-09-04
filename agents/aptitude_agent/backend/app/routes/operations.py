from flask import Blueprint, current_app, g
from ..services.job_service import retry_failed_job
from ..services.operations_service import operations_snapshot
from ..utils.authentication import require_student
from ..utils.errors import APIError

bp=Blueprint("operations",__name__,url_prefix="/api/aptitude")

@bp.get("/operations")
@require_student
def operations():
    snapshot=operations_snapshot(g.student.id,current_app.config["WORKER_STALE_SECONDS"])
    return {"worker":{"online":any(worker["online"] for worker in snapshot["workers"]),"active_count":sum(worker["online"] for worker in snapshot["workers"])},"jobs":snapshot["jobs"],"failed_jobs":snapshot["failed_jobs"],"question_bank":snapshot["question_bank"]}

@bp.post("/operations/jobs/<job_id>/retry")
@require_student
def retry_job(job_id):
    job=retry_failed_job(job_id,g.student.id)
    if not job:raise APIError("Failed job not found",404,"job_not_found")
    return {"id":job.id,"status":job.status},202

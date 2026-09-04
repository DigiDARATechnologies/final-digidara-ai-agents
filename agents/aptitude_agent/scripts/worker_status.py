import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.app import create_app
from backend.app.services.job_service import retry_failed_job
from backend.app.services.operations_service import operations_snapshot


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--retry",metavar="JOB_ID");args=parser.parse_args();app=create_app()
    with app.app_context():
        if args.retry:
            job=retry_failed_job(args.retry)
            if not job:raise SystemExit("Failed job not found")
            print(f"Queued {job.id}");return
        snapshot=operations_snapshot(stale_seconds=app.config["WORKER_STALE_SECONDS"])
        print("Workers:")
        for worker in snapshot["workers"]:print(f"  {worker['worker_id']} status={worker['status']} online={worker['online']} heartbeat={worker['heartbeat_at']}")
        print("Jobs:",snapshot["jobs"]);print("Question bank:",snapshot["question_bank"])
        for job in snapshot["failed_jobs"]:print(f"FAILED {job['id']} {job['job_type']} attempts={job['attempts']} error={job['last_error']}")


if __name__=="__main__":main()

"""Reset failed pool-replenish jobs so the worker can retry them once."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app import create_app
from backend.app.models import BackgroundJob
from backend.app.services.job_service import retry_failed_job


def main():
    app = create_app()
    with app.app_context():
        jobs = BackgroundJob.query.filter_by(
            job_type="pool_replenish", status="failed"
        ).all()
        print(f"Found {len(jobs)} failed pool_replenish jobs.")
        for job in jobs:
            category = (job.payload_json or {}).get("category", "?")
            difficulty = (job.payload_json or {}).get("difficulty", "?")
            retry_failed_job(job.id)
            print(f"Requeued {job.id} ({category} / {difficulty})")
        print("Done.")


if __name__ == "__main__":
    main()

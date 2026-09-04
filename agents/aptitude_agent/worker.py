"""Analytics and maintenance worker. Recommendations are generated live."""
import os
import socket
import time
import atexit
import signal
from backend.app import create_app
from backend.app.services.job_service import process_next_job, update_worker_heartbeat

app = create_app()
worker_id = f"{socket.gethostname()}:{os.getpid()}"
hostname=socket.gethostname()
process_id=os.getpid()


def mark_stopped():
    """Best-effort lifecycle update for Ctrl+C, SIGTERM, and normal exit."""
    try:
        with app.app_context():
            update_worker_heartbeat(worker_id,hostname,process_id,"stopped")
    except Exception:
        # Never turn shutdown into a traceback just because MySQL is down.
        pass


def stop_signal(_signum,_frame):
    mark_stopped()
    raise KeyboardInterrupt


atexit.register(mark_stopped)
signal.signal(signal.SIGTERM,stop_signal)
if hasattr(signal,"SIGINT"):
    signal.signal(signal.SIGINT,stop_signal)

if __name__ == "__main__":
    print(f"Aptitude worker started as {worker_id}")
    with app.app_context():
        last_cleanup = 0
        last_heartbeat=0
        update_worker_heartbeat(worker_id,hostname,process_id,"starting")
        try:
            while True:
                now=time.monotonic()
                if now-last_cleanup>=60:
                    from backend.app.services.job_service import cleanup_operational_data
                    cleanup_operational_data();last_cleanup=now
                if now-last_heartbeat>=app.config["WORKER_HEARTBEAT_SECONDS"]:
                    update_worker_heartbeat(worker_id,hostname,process_id,"idle");last_heartbeat=now
                worked=process_next_job(worker_id)
                if not worked:time.sleep(app.config["WORKER_POLL_SECONDS"])
        except KeyboardInterrupt:
            update_worker_heartbeat(worker_id,hostname,process_id,"stopped")
            print("Aptitude worker stopped")

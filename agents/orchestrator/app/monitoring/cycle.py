"""The server's regular check, run by scripts/server/monitor-cycle.sh every ten
minutes. Agents run in their own containers, so their logs and health come in on
stdin from the host; this reads them, then sends any email that is due.

    python -m app.monitoring.cycle --label production < logs
"""
import argparse
import re
import sys

from app.monitoring import service

# Application services only: the databases and Judge0 log their own routine "errors".
SERVICES = {"capstone-agent", "codeforge-agent", "communication-agent", "aptitude-agent", "mock-interview-agent",
            "resume-builder-agent", "certificate-agent", "job-agent", "job-worker", "orchestrator"}
_LINE = re.compile(r"^(?P<service>[\w-]+?)(?:-\d+)?\s+\|\s?(?P<text>.*)$")
_ERROR = re.compile(r'\b(?:ERROR|CRITICAL|FATAL)\b|"(?:level|severity)"\s*:\s*"(?:error|critical)"', re.IGNORECASE)
_EXCEPTION = re.compile(r"^(?:[\w.]+\.)?\w*(?:Error|Exception|Timeout|Refused)\b.*")
# Logged as errors, handled by retrying, and not a failure the learner sees.
_EXPECTED = re.compile(r"Question validation failed|sqlalche\.me/")
# A heartbeat that fails during a deploy's restart, and is simply sent again next
# time: its message and whole traceback are not a failure.
_RETRIED = re.compile(r"heartbeat failed")
_TRACEBACK_LINE = re.compile(r"^(?:Traceback \(|During handling|The above exception|$)")


def read_logs(lines) -> list[tuple[str, str, str]]:
    """(severity, service, message) for each failure in `docker compose logs`
    output and each unwell container in the `@ps` lines before it."""
    found: list[tuple[str, str, str]] = []
    in_traceback: set[str] = set()
    retried: set[str] = set()
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith("@ps "):
            parts = line.split()
            service_name, state = parts[1], parts[2]
            health = parts[3] if len(parts) > 3 else ""
            if service_name in SERVICES and (state != "running" or health == "unhealthy"):
                found.append((service.ERROR, service_name, f"Container is {health if state == 'running' else state}"))
            continue
        match = _LINE.match(line)
        if not match or match["service"] not in SERVICES:
            continue
        name, text = match["service"], match["text"].strip()
        if _RETRIED.search(text):
            retried.add(name)
            continue
        if name in retried:
            if match["text"].startswith((" ", "	")) or _TRACEBACK_LINE.match(text) or _EXCEPTION.match(text):
                continue
            retried.discard(name)
        if "Traceback (most recent call last)" in text:
            in_traceback.add(name)
        elif name in in_traceback and _EXCEPTION.match(text):
            # The last line of a traceback says what actually went wrong.
            in_traceback.discard(name)
            found.append((service.ERROR, name, text))
        elif name not in in_traceback and _ERROR.search(text) and not _EXPECTED.search(text):
            found.append((service.WARNING, name, text))
    return found


def run(lines, label: str) -> None:
    for severity, name, message in read_logs(lines):
        # The orchestrator's own errors are already recorded as they happen.
        if name != "orchestrator" or severity == service.ERROR and message.startswith("Container"):
            service.save("logs", severity, message, agent=name)
    service.send_alerts(label)
    if label == "production":
        service.send_daily_report(label)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="server")
    run(sys.stdin, parser.parse_args().label)

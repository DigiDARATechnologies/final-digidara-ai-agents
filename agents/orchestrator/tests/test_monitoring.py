"""Monitoring: failures are recorded safely and reach the monitoring accounts."""
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.security import get_current_user_id
from app.auth.service import create_user
from app.models import SystemIssue, User
from app.monitoring import cycle, service
from app.monitoring.middleware import IssueMiddleware
from app.monitoring.routes import router

MONITOR = "premkumar18082002@gmail.com"


@pytest.fixture
def people(database, monkeypatch):
    monkeypatch.setattr(service, "get_session", database)
    monitor = create_user("Prem", MONITOR, None, "hash", "2026-01")
    learner = create_user("Learner", "learner@example.com", None, "hash", "2026-01")
    admin = create_user("Admin", "boss-admin@example.com", None, "hash", "2026-01")
    session = database()
    session.get(User, admin.id).is_admin = True
    session.commit()
    session.close()
    return monitor.id, learner.id, admin.id


@pytest.fixture
def emails(monkeypatch):
    sent = []
    monkeypatch.setattr(service, "_send_email", lambda to, subject, body: sent.append((to, subject, body)) or True)
    return sent


def issues():
    session = service.get_session()
    try:
        return session.query(SystemIssue).all()
    finally:
        session.close()


def test_scrubbing_removes_addresses_and_secrets():
    text = service.scrub("failed for a.b@gmail.com Bearer abc.def password=hunter2 sk-secret123 token: xyz")
    for private in ("a.b@gmail.com", "abc.def", "hunter2", "secret123", "xyz"):
        assert private not in text


def test_one_kind_of_failure_is_one_row_with_a_count(people):
    service.save("agent", service.ERROR, "Interview 41 failed", agent="mock_interview_agent", action="end", status=500)
    service.save("agent", service.ERROR, "Interview 977 failed", agent="mock_interview_agent", action="end", status=500)
    service.save("agent", service.ERROR, "Something else", agent="mock_interview_agent", action="end", status=500)
    assert sorted(issue.count for issue in issues()) == [1, 2]


def test_only_the_two_kinds_of_account_get_a_briefing(people):
    monitor, learner, admin = people
    service.save("agent", service.ERROR, "Broke", agent="aptitude_agent", status=500)
    assert service.briefing(monitor)["issues"] and service.briefing(admin)["issues"]
    assert service.briefing(learner) == {"allowed": False, "issues": [], "text": ""}


def test_boss_says_a_problem_once_then_again_only_when_it_returns(people):
    monitor = people[0]
    service.save("agent", service.ERROR, "Broke", agent="aptitude_agent", status=500)
    first = service.briefing(monitor)
    assert "Aptitude" in first["text"] and "Broke" in first["text"]
    service.mark_seen(monitor, first["as_of"])
    assert service.briefing(monitor)["text"] == ""
    assert service.briefing(monitor, recent=True)["issues"]
    service.save("agent", service.ERROR, "Broke", agent="aptitude_agent", status=500)
    session = service.get_session()
    session.query(SystemIssue).one().last_seen += timedelta(seconds=2)  # Times are in whole seconds.
    session.commit()
    session.close()
    assert service.briefing(monitor)["issues"][0]["count"] == 2


def test_even_an_everyday_refusal_is_reported(people):
    monitor = people[0]
    service.save("agent", service.WARNING, "Test not active", agent="aptitude_agent", status=409)
    assert len(service.briefing(monitor)["issues"]) == 1


def test_alerts_email_both_accounts_once_and_not_too_often(people, emails):
    service.save("agent", service.ERROR, "Broke", agent="aptitude_agent", status=500)
    now = datetime.utcnow() + timedelta(seconds=1)
    assert service.send_alerts("production", now) == 1
    assert emails[0][0] == sorted([MONITOR, "boss-admin@example.com", "support@digidaratechnologies.com"])
    assert "[SkillDARA production]" in emails[0][1] and "Broke" in emails[0][2]
    assert service.send_alerts("production", now + timedelta(hours=1)) == 0
    service.save("agent", service.ERROR, "New one", agent="job_agent", status=500)
    assert service.send_alerts("production", now + timedelta(minutes=5)) == 0  # Inside the gap.
    assert service.send_alerts("production", datetime.utcnow() + timedelta(minutes=31)) == 1
    assert "New one" in emails[1][2] and "Broke" not in emails[1][2]


def test_a_failed_email_is_tried_again(people, monkeypatch):
    monkeypatch.setattr(service, "_send_email", lambda *_: False)
    service.save("agent", service.ERROR, "Broke", agent="aptitude_agent", status=500)
    assert service.send_alerts("production") == 0
    assert issues()[0].alerted_at is None


def test_the_daily_report_goes_once_a_morning_even_when_all_is_well(people, emails):
    morning = datetime(2026, 11, 4, 3, 40)
    assert service.send_daily_report("production", morning.replace(hour=2)) is False
    assert service.send_daily_report("production", morning) is True
    assert "all clear" in emails[0][1]
    assert service.send_daily_report("production", morning + timedelta(hours=1)) is False


def test_logs_become_issues_without_the_noise():
    logs = [
        "@ps aptitude-agent running healthy\n",
        "@ps job-agent running unhealthy\n",
        "@ps resume-builder-agent exited \n",
        "@ps mysql exited \n",
        "aptitude-agent-1  | 10:00 ERROR Question validation failed reason=x\n",
        "aptitude-agent-1  | 10:00 INFO all good\n",
        "mock-interview-agent-1  | Traceback (most recent call last):\n",
        'mock-interview-agent-1  |   File "x.py", line 1, in y\n',
        "mock-interview-agent-1  | ValueError: bad row\n",
        'certificate-agent-1  | {"level": "error", "event": "pdf_failed"}\n',
        "mysql-1  | ERROR the database's own routine line\n",
    ]
    found = cycle.read_logs(logs)
    assert (service.ERROR, "job-agent", "Container is unhealthy") in found
    assert (service.ERROR, "resume-builder-agent", "Container is exited") in found
    assert (service.ERROR, "mock-interview-agent", "ValueError: bad row") in found
    assert any(name == "certificate-agent" and severity == service.WARNING for severity, name, _ in found)
    assert len(found) == 4


def test_a_retried_heartbeat_is_not_a_failure():
    logs = [
        "job-agent-1  | job_agent heartbeat failed",
        "job-agent-1  | Traceback (most recent call last):",
        'job-agent-1  |   File "x.py", line 1, in y',
        "job-agent-1  | TimeoutError: timed out",
        "job-agent-1  | ",
        "job-agent-1  | The above exception was the direct cause of the following exception:",
        "job-agent-1  | requests.exceptions.ReadTimeout: read timed out",
        "job-agent-1  | 10:01 INFO back to normal",
        "job-agent-1  | Traceback (most recent call last):",
        "job-agent-1  | ValueError: a real one",
    ]
    assert cycle.read_logs(logs) == [(service.ERROR, "job-agent", "ValueError: a real one")]


def test_the_cycle_records_and_emails(people, emails):
    cycle.run(["@ps job-agent running unhealthy\n"], "production")
    assert issues()[0].agent == "job-agent"
    assert "unhealthy" in emails[0][2]


def test_a_refused_save_is_recorded_without_the_learners_text(people, monkeypatch):
    saved = []
    monkeypatch.setattr(service, "record", lambda *args, **kwargs: saved.append((args, kwargs)))
    from pydantic import BaseModel

    class Body(BaseModel):
        number: int

    app = FastAPI()
    app.add_middleware(IssueMiddleware)

    @app.put("/chats/sync")
    def sync(body: Body) -> dict:
        return {}

    response = TestClient(app).put("/chats/sync", json={"number": "my private chat text"})
    assert response.status_code == 422
    assert saved[0][1]["status"] == 422 and saved[0][1]["action"] == "/chats/sync"
    assert "private" not in saved[0][0][2]


def test_the_routes_answer_each_account_for_itself(people):
    monitor, learner, _ = people
    service.save("agent", service.ERROR, "Broke", agent="aptitude_agent", status=500)
    current = {"id": learner}
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: current["id"]
    client = TestClient(app)
    assert client.get("/platform-admin/monitoring/briefing").json()["allowed"] is False
    current["id"] = monitor
    briefing = client.get("/platform-admin/monitoring/briefing").json()
    assert briefing["allowed"] is True and briefing["issues"][0]["agent"] == "Aptitude"
    assert client.post("/platform-admin/monitoring/seen", json={"as_of": briefing["as_of"]}).status_code == 200
    assert client.get("/platform-admin/monitoring/briefing").json()["issues"] == []
    assert client.post("/platform-admin/monitoring/seen", json={"as_of": "not a time"}).status_code == 400


def test_boss_says_todays_jobs_once_a_day_and_whenever_asked(people):
    monitor, learner, _ = people
    today = service.today_in_india()
    service.save_job_day(today, [12, 1, 1240, 86, 1100, 54])
    first = service.briefing(monitor)
    assert "1,240 jobs" in first["text"] and "86 new" in first["text"] and "1 run failed" in first["text"]
    service.mark_seen(monitor, first["as_of"])
    assert service.briefing(monitor)["text"] == ""
    assert "1,240 jobs" in service.briefing(monitor, recent=True)["jobs_text"]
    assert "jobs_text" not in service.briefing(learner)


def test_a_day_without_a_fetch_says_so(people):
    monitor = people[0]
    assert "no job fetch recorded" in service.briefing(monitor)["text"]
    service.save_job_day(service.today_in_india(), [0, 0, 0, 0, 0, 0])
    assert "no job fetch ran" in service.briefing(monitor)["text"]


def test_the_cycle_keeps_the_job_counts_and_ignores_bad_lines():
    days = cycle.job_days(["@jobs 2026-11-03 2 0 50 10 40 0\n", "@jobs broken\n", "@jobs 2026-11-03 a b c d e f\n", "job-agent-1  | hello\n"])
    assert days == [("2026-11-03", [2, 0, 50, 10, 40, 0])]


def test_the_jobs_email_goes_once_each_night_to_both_accounts(people, emails):
    night = datetime(2026, 11, 3, 18, 10)
    service.save_job_day("2026-11-03", [2, 0, 50, 10, 40, 0])
    assert service.send_jobs_report("production", night.replace(hour=12)) is False
    assert service.send_jobs_report("production", night) is True
    assert MONITOR in emails[0][0] and "boss-admin@example.com" in emails[0][0]
    assert "50 jobs" in emails[0][2] and "**" not in emails[0][2]
    assert service.send_jobs_report("production", night.replace(minute=20)) is False
    assert service.send_jobs_report("production", night.replace(minute=40)) is False  # Tomorrow, in India.
    assert len(emails) == 1


def test_the_morning_report_gives_yesterdays_jobs(people, emails):
    service.save_job_day("2026-11-03", [2, 0, 50, 10, 40, 0])
    assert service.send_daily_report("production", datetime(2026, 11, 4, 3, 40)) is True
    assert "50 jobs yesterday" in emails[0][2]


def test_a_learners_report_reaches_the_team_with_the_agents_errors(people, emails, monkeypatch):
    monitor = people[0]

    class Now:
        def __init__(self, target, **_):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(service.threading, "Thread", Now)
    service.save("logs", service.ERROR, "ValueError: could not prepare", agent="aptitude_agent")
    service.report_to_team("Rubi", "rubi@example.com", "other", "aptitude_agent", "My test will not start")
    to, subject, body = emails[0]
    assert "support@digidaratechnologies.com" in to and MONITOR in to
    assert "aptitude_agent" in subject and "rubi@example.com" in body
    assert "My test will not start" in body and "could not prepare" in body
    assert any("My test will not start" in issue["message"] for issue in service.briefing(monitor)["issues"])

"""What went wrong on the platform, for the people who look after it.

Failures are recorded here from every side (see routes.py, middleware.py and
cycle.py) and reach the monitoring accounts two ways: Boss tells them when they
sign in or while they are working, and they get email. One kind of failure is
one row with a count, so a problem hitting a thousand learners is one line, and
rows are never deleted.

Stored text is scrubbed first. It is read by people and sent by email, and
errors can carry learners' addresses and tokens.
"""
import logging
import os
import queue
import re
import smtplib
import ssl
import threading
import hashlib
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy.exc import IntegrityError

from app.auth.email_verification import _smtp_settings
from app.db import get_session
from app.models import MonitorState, SystemIssue, User

# This module's own failures must not be recorded by the handler they would pass through.
logger = logging.getLogger("app.monitoring")

ERROR = "error"
WARNING = "warning"
# Everyday refusals (a test that already ended) are only a problem when they keep happening.
# The owner asked to hear about everything, small or big, so one is enough.
WARNING_REPORT_COUNT = 1
MAX_MESSAGE = 500
ALERT_GAP = timedelta(minutes=30)
REMIND_AFTER = timedelta(hours=6)
FIRST_BRIEFING_WINDOW = timedelta(hours=24)
BRIEFING_LINES = 5
DAILY_REPORT_HOUR_UTC = 3  # 03:30 UTC is 9 in the morning in India.
DAILY_REPORT_MINUTE_UTC = 30
JOBS_REPORT_HOUR_UTC = 18  # 11:30 at night in India: the day's totals are nearly final.
IST = timedelta(hours=5, minutes=30)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_SECRET = re.compile(r"(?i)\b(bearer\s+|sk-|token[\"'=:\s]+|password[\"'=:\s]+|api[_-]?key[\"'=:\s]+|authorization[\"'=:\s]+)[^\s\"',;]+")
_LONG_ID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27}\b|\b[0-9a-fA-F]{16,}\b")
_NUMBER = re.compile(r"\d+")
_FINGERPRINT_CHARS = 120


def monitor_emails() -> set[str]:
    return {email.strip().lower() for email in os.environ.get("MONITOR_EMAILS", "premkumar18082002@gmail.com").split(",") if email.strip()}


def is_monitor(user: User | None) -> bool:
    return bool(user) and (bool(user.is_admin) or (user.email or "").lower() in monitor_emails())


def recipients(session) -> list[str]:
    admins = session.query(User.email).filter(User.is_admin.is_(True)).all()
    support = os.environ.get("ISSUE_EMAIL", "support@digidaratechnologies.com").strip().lower()
    return sorted(monitor_emails() | {support} | {email.lower() for (email,) in admins if email})


def scrub(text: str) -> str:
    cleaned = _SECRET.sub(lambda match: f"{match.group(1)}[hidden]", _EMAIL.sub("[email]", text or ""))
    return " ".join(cleaned.split())[:MAX_MESSAGE]


def _fingerprint(source: str, agent: str, action: str, status: int | None, message: str) -> str:
    # What the failure is, without the numbers and ids that differ every time.
    general = _NUMBER.sub("#", _LONG_ID.sub("#", message))[:_FINGERPRINT_CHARS].lower()
    return hashlib.sha256("|".join((source, agent, action, str(status or ""), general)).encode()).hexdigest()


def save(source: str, severity: str, message: str, *, agent: str = "", action: str = "", status: int | None = None) -> None:
    """Records one failure now. Requests use record(), which does not wait for the database."""
    message = scrub(message) or (f"HTTP {status}" if status else "Unknown failure")
    fingerprint = _fingerprint(source, agent, action, status, message)
    for attempt in (1, 2):
        session = get_session()
        try:
            # MySQL keeps whole seconds: with fractions it rounds up, and an issue
            # already told about would look newer than the telling.
            now = datetime.utcnow().replace(microsecond=0)
            issue = session.query(SystemIssue).filter_by(fingerprint=fingerprint).first()
            if issue is None:
                session.add(SystemIssue(fingerprint=fingerprint, source=source, severity=severity, agent=agent[:64],
                                        action=action[:64], status=status, message=message, count=1,
                                        first_seen=now, last_seen=now))
            else:
                issue.count += 1
                issue.last_seen = now
                issue.message = message
            session.commit()
            return
        except IntegrityError:
            # Another worker recorded its first one at the same moment: count this on top.
            session.rollback()
            if attempt == 2:
                raise
        finally:
            session.close()


_pending: queue.Queue = queue.Queue(maxsize=2000)
_writer_lock = threading.Lock()
_writer: threading.Thread | None = None


def _write_forever() -> None:
    while True:
        args, kwargs = _pending.get()
        try:
            save(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - monitoring must never disturb anything else
            logger.warning("could not record an issue: %s", type(exc).__name__)


def record(source: str, severity: str, message: str, **fields) -> None:
    """Never blocks and never raises: it runs inside learners' requests."""
    global _writer
    try:
        if _writer is None or not _writer.is_alive():
            with _writer_lock:
                if _writer is None or not _writer.is_alive():
                    _writer = threading.Thread(target=_write_forever, name="issue-writer", daemon=True)
                    _writer.start()
        _pending.put_nowait(((source, severity, message), fields))
    except Exception:  # noqa: BLE001 - a full queue only means this one goes uncounted
        pass


class IssueLogHandler(logging.Handler):
    """Errors this server writes to its own log. A failed agent call is already
    recorded with its agent and action, so the gateway's copy of it is not."""

    SKIPPED = ("app.monitoring", "orchestrator.gateway")

    def emit(self, log: logging.LogRecord) -> None:
        if log.name.startswith(self.SKIPPED):
            return
        try:
            kind = log.exc_info[0].__name__ if log.exc_info and log.exc_info[0] else ""
            record("server", ERROR, f"{log.getMessage()}{f' ({kind})' if kind else ''}", agent="orchestrator", action=log.name[:64])
        except Exception:  # noqa: BLE001
            pass


def install_log_handler() -> None:
    root = logging.getLogger()
    if not any(isinstance(handler, IssueLogHandler) for handler in root.handlers):
        handler = IssueLogHandler(level=logging.ERROR)
        root.addHandler(handler)


def today_in_india(now: datetime | None = None) -> str:
    return ((now or datetime.utcnow()) + IST).date().isoformat()


def save_job_day(day: str, counts: list[int]) -> None:
    """counts: runs, failed runs, fetched, new, updated, rejected."""
    session = get_session()
    try:
        _write_state(session, f"jobs:{day}", ",".join(str(count) for count in counts))
        session.commit()
    finally:
        session.close()


def jobs_text(session, day: str, when: str = "today") -> str:
    saved = _read_state(session, f"jobs:{day}")
    if not saved:
        return f"Job Agent: no job fetch recorded {when} yet."
    runs, failed, fetched, new, updated, rejected = (int(part) for part in saved.split(","))
    if not runs:
        return f"Job Agent: no job fetch ran {when}."
    text = f"Job Agent fetched **{fetched:,} jobs** {when}: {new:,} new, {updated:,} updated, {rejected:,} rejected, in {runs:,} run{'' if runs == 1 else 's'}."
    return text + (f" {failed:,} run{' failed' if failed == 1 else 's failed'}." if failed else "")


def _reportable(issue: SystemIssue) -> bool:
    return issue.severity == ERROR or issue.count >= WARNING_REPORT_COUNT


def _read_state(session, key: str) -> str | None:
    row = session.get(MonitorState, key)
    return row.value if row else None


def _write_state(session, key: str, value: str) -> None:
    row = session.get(MonitorState, key)
    if row:
        row.value = value
    else:
        session.add(MonitorState(key=key, value=value))


def _agent_label(issue: SystemIssue) -> str:
    return (issue.agent or issue.source).replace("_agent", "").replace("-agent", "").replace("_", " ").replace("-", " ").title()


def describe(issue: SystemIssue) -> dict:
    return {
        "severity": issue.severity, "source": issue.source, "agent": _agent_label(issue), "action": issue.action,
        "status": issue.status, "message": issue.message, "count": issue.count,
        "first_seen": issue.first_seen.isoformat() + "Z", "last_seen": issue.last_seen.isoformat() + "Z",
    }


def _newest(session, since: datetime) -> list[SystemIssue]:
    rows = session.query(SystemIssue).filter(SystemIssue.last_seen > since).order_by(SystemIssue.last_seen.desc()).all()
    # Worst first: errors, then the failures that happened most.
    return sorted((issue for issue in rows if _reportable(issue)), key=lambda issue: (issue.severity != ERROR, -issue.count))


def spoken_summary(issues: list[dict], *, recent: bool = False) -> str:
    if not issues:
        return "No problems in the last 24 hours. All agents are working." if recent else ""
    errors = sum(issue["severity"] == ERROR for issue in issues)
    opening = f"{len(issues)} problem{'' if len(issues) == 1 else 's'} {'in the last 24 hours' if recent else 'need your attention'}"
    if errors:
        opening += f", {errors} serious"

    def line(issue: dict) -> str:
        where = f"{issue['agent']} ({issue['action']})" if issue["action"] else issue["agent"]
        times = "1 time" if issue["count"] == 1 else f"{issue['count']} times"
        return f"**{where}**: {issue['message'][:160]} - {times}."

    lines = [line(issue) for issue in issues[:BRIEFING_LINES]]
    more = len(issues) - BRIEFING_LINES
    ending = f"\n\nAnd {more} more in the email report." if more > 0 else ""
    return f"{opening}.\n\n" + "\n\n".join(lines) + ending


def briefing(user_id: str, *, recent: bool = False) -> dict:
    """What this account has not been told yet; `recent` is everything from the last 24 hours."""
    session = get_session()
    try:
        user = session.get(User, user_id)
        if not is_monitor(user):
            return {"allowed": False, "issues": [], "text": ""}
        now = datetime.utcnow()
        seen = _read_state(session, f"seen:{user_id}")
        since = now - FIRST_BRIEFING_WINDOW if recent or not seen else datetime.fromisoformat(seen)
        newest = _newest(session, since)
        issues = [describe(issue) for issue in newest]
        today = today_in_india(now)
        jobs = jobs_text(session, today)
        # Up to the newest one told, so anything after it is still news.
        as_of = max((issue.last_seen for issue in newest), default=now)
        text = spoken_summary(issues, recent=recent)
        # Once a day, Boss opens with the day's job fetching.
        if not recent and _read_state(session, f"jobs_told:{user_id}") != today:
            text = f"{jobs}\n\n{text}" if text else jobs
        return {"allowed": True, "issues": issues, "text": text, "jobs_text": jobs, "as_of": as_of.isoformat()}
    finally:
        session.close()


def mark_seen(user_id: str, as_of: str) -> None:
    session = get_session()
    try:
        if is_monitor(session.get(User, user_id)):
            _write_state(session, f"seen:{user_id}", datetime.fromisoformat(as_of).isoformat())
            _write_state(session, f"jobs_told:{user_id}", today_in_india())
            session.commit()
    finally:
        session.close()


def _send_email(to: list[str], subject: str, body: str) -> bool:
    settings = _smtp_settings()
    if settings is None or not to:
        logger.warning("monitoring email not sent: %s", "SMTP is not configured" if settings is None else "no recipients")
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"SkillDARA Boss <{settings['sender']}>"
    message["To"] = ", ".join(to)
    message.set_content(body)
    try:
        if settings["port"] == 465:
            with smtplib.SMTP_SSL(settings["host"], settings["port"], timeout=15, context=ssl.create_default_context()) as smtp:
                smtp.login(settings["user"], settings["password"])
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings["host"], settings["port"], timeout=15) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(settings["user"], settings["password"])
                smtp.send_message(message)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("monitoring email could not be sent: %s", type(exc).__name__)
        return False


def _email_lines(issues: list[SystemIssue]) -> str:
    def line(issue: SystemIssue) -> str:
        where = f"{_agent_label(issue)}{f' / {issue.action}' if issue.action else ''}{f' / HTTP {issue.status}' if issue.status else ''}"
        return (f"[{issue.severity.upper()}] {where}\n  {issue.message}\n"
                f"  {issue.count} time(s), first {issue.first_seen:%d %b %H:%M} UTC, last {issue.last_seen:%d %b %H:%M} UTC")
    return "\n\n".join(line(issue) for issue in issues)


def report_to_team(name: str, email: str, category: str, agent: str, words: str) -> None:
    """A learner asked Boss to tell the team: it goes on the record the admins see,
    and by email straight away with the same agent's recent errors. Never blocks."""
    save("report", ERROR, words, agent=agent or "boss", action=category)

    def send() -> None:
        session = get_session()
        try:
            recent = [issue for issue in _newest(session, datetime.utcnow() - FIRST_BRIEFING_WINDOW)
                      if issue.agent == agent and issue.source != "report"]
            logs = f"\n\nRecent errors on this agent:\n\n{_email_lines(recent)}" if recent else "\n\nNo errors recorded on this agent in the last 24 hours."
            _send_email(recipients(session), f"[SkillDARA] A learner reported a problem: {agent or category}",
                        f"From: {name} <{email}>\nAgent: {agent or '-'}\nType: {category}\n\nThey said:\n{words}{logs}\n")
        except Exception as exc:  # noqa: BLE001 - the report itself is already saved
            logger.warning("the report email could not be sent: %s", type(exc).__name__)
        finally:
            session.close()

    threading.Thread(target=send, name="report-email", daemon=True).start()


def send_alerts(label: str, now: datetime | None = None) -> int:
    """Emails failures nobody has been emailed about; a failure still happening
    is repeated every few hours, and one email goes at most every half hour."""
    now = now or datetime.utcnow()
    session = get_session()
    try:
        last = _read_state(session, "last_alert_at")
        if last and now - datetime.fromisoformat(last) < ALERT_GAP:
            return 0
        rows = session.query(SystemIssue).filter(SystemIssue.last_seen > now - REMIND_AFTER).all()
        due = [issue for issue in rows if _reportable(issue)
               and (issue.alerted_at is None or (issue.last_seen > issue.alerted_at and now - issue.alerted_at >= REMIND_AFTER))]
        if not due:
            return 0
        due.sort(key=lambda issue: (issue.severity != ERROR, -issue.count))
        subject = f"[SkillDARA {label}] {len(due)} problem{'' if len(due) == 1 else 's'} found"
        if not _send_email(recipients(session), subject, f"Boss found these on {label}:\n\n{_email_lines(due)}\n"):
            return 0
        for issue in due:
            issue.alerted_at = now
        _write_state(session, "last_alert_at", now.isoformat())
        session.commit()
        return len(due)
    finally:
        session.close()


def send_daily_report(label: str, now: datetime | None = None) -> bool:
    """Once a morning, also when all is well: silence must not be the only sign that it is."""
    now = now or datetime.utcnow()
    if (now.hour, now.minute) < (DAILY_REPORT_HOUR_UTC, DAILY_REPORT_MINUTE_UTC):
        return False
    today = now.date().isoformat()
    session = get_session()
    try:
        if _read_state(session, "daily_report_on") == today:
            return False
        issues = _newest(session, now - timedelta(hours=24))
        yesterday = (now + IST - timedelta(days=1)).date().isoformat()
        jobs = jobs_text(session, yesterday, "yesterday").replace("**", "")
        body = (f"Boss's report for {label}, last 24 hours:\n\n{jobs}\n\n{_email_lines(issues)}\n" if issues
                else f"Boss's report for {label}: no problems in the last 24 hours.\n\n{jobs}\n")
        subject = f"[SkillDARA {label}] Daily report: {f'{len(issues)} problem(s)' if issues else 'all clear'}"
        if not _send_email(recipients(session), subject, body):
            return False
        _write_state(session, "daily_report_on", today)
        session.commit()
        return True
    finally:
        session.close()


def send_jobs_report(label: str, now: datetime | None = None) -> bool:
    """Every night, the day's job fetching, to the same people as the other reports."""
    now = now or datetime.utcnow()
    # Only before midnight in India (18:30 UTC): later, "today" is already tomorrow.
    if now.hour != JOBS_REPORT_HOUR_UTC or now.minute >= 30:
        return False
    today = today_in_india(now)
    session = get_session()
    try:
        if _read_state(session, "jobs_report_on") == today:
            return False
        text = jobs_text(session, today).replace("**", "")
        if not _send_email(recipients(session), f"[SkillDARA {label}] Jobs fetched today ({today})", f"{text}\n"):
            return False
        _write_state(session, "jobs_report_on", today)
        session.commit()
        return True
    finally:
        session.close()

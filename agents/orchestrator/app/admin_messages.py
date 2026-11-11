"""Messages from the SkillDARA team to a learner: the reply when a Boss report
is marked solved, or any message the team writes. The learner sees unread ones
in a popup the next time they open the app. Nothing here is ever deleted
(except with the learner's own account)."""
from __future__ import annotations

from datetime import datetime

from app import db
from app.models import AdminMessage, BossIssueReport, User

MAX_BODY = 2000
SOLVED_TEXT = "Good news: the problem you reported to Boss has been solved. Thank you for telling us!"


class MessageError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _as_dict(message: AdminMessage) -> dict:
    return {"id": message.id, "report_id": message.report_id, "body": message.body,
            "created_at": _iso(message.created_at), "read_at": _iso(message.read_at)}


def _clean(body: str | None) -> str:
    text = (body or "").strip()[:MAX_BODY]
    if not text:
        raise MessageError(400, "Write a message first.")
    return text


def send(sender_id: str, user_id: str, body: str, report_id: str | None = None) -> dict:
    text = _clean(body)
    session = db.get_session()
    try:
        if session.get(User, user_id) is None:
            raise MessageError(404, "That learner no longer exists.")
        message = AdminMessage(user_id=user_id, sender_id=sender_id, body=text, report_id=report_id)
        session.add(message)
        session.commit()
        return _as_dict(message)
    finally:
        session.close()


def _report(session, report_id: str) -> BossIssueReport:
    report = session.get(BossIssueReport, report_id, with_for_update=True)
    if report is None:
        raise MessageError(404, "No such report.")
    return report


def reply_to_report(sender_id: str, report_id: str, body: str) -> dict:
    session = db.get_session()
    try:
        user_id = _report(session, report_id).user_id
    finally:
        session.close()
    return send(sender_id, user_id, body, report_id)


def set_report_status(sender_id: str, report_id: str, solved: bool, body: str | None = None) -> dict:
    """Mark a report solved -- and tell the learner (the default text unless
    the team wrote their own) -- or open it again."""
    session = db.get_session()
    try:
        report = _report(session, report_id)
        report.status = "solved" if solved else "open"
        report.solved_at = datetime.utcnow() if solved else None
        user_id = report.user_id
        session.commit()
    finally:
        session.close()
    message = send(sender_id, user_id, (body or "").strip() or SOLVED_TEXT, report_id) if solved else None
    return {"id": report_id, "status": "solved" if solved else "open", "message": message}


def by_report(report_ids: list[str]) -> dict[str, list[dict]]:
    """Every message sent about these reports, oldest first."""
    if not report_ids:
        return {}
    session = db.get_session()
    try:
        rows = (session.query(AdminMessage).filter(AdminMessage.report_id.in_(report_ids))
                .order_by(AdminMessage.created_at).all())
        result: dict[str, list[dict]] = {}
        for row in rows:
            result.setdefault(row.report_id, []).append(_as_dict(row))
        return result
    finally:
        session.close()


def for_learner(user_id: str) -> list[dict]:
    """All of a learner's messages, newest first (none hidden)."""
    session = db.get_session()
    try:
        rows = (session.query(AdminMessage, BossIssueReport.message)
                .outerjoin(BossIssueReport, BossIssueReport.id == AdminMessage.report_id)
                .filter(AdminMessage.user_id == user_id).order_by(AdminMessage.created_at.desc()).all())
        # The learner's own words, so they know which report a reply is about.
        return [{**_as_dict(row), "report_message": report_message} for row, report_message in rows]
    finally:
        session.close()


def mark_read(user_id: str) -> int:
    session = db.get_session()
    try:
        count = (session.query(AdminMessage).filter(AdminMessage.user_id == user_id, AdminMessage.read_at.is_(None))
                 .update({"read_at": datetime.utcnow()}, synchronize_session=False))
        session.commit()
        return count
    finally:
        session.close()


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(AdminMessage).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()

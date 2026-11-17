"""The emails a learner can turn on in Settings > Notifications, sent by the
server's ten-minute cycle (app/monitoring/cycle.py):

* weekly progress -- Monday morning (India), last week's activity per agent;
* low coins -- once a month, when the balance drops under LOW_COIN_POINTS
  and the learner used the agents in the last week;
* plan renewal -- RENEWAL_DAYS before a paid plan runs out;
* assessment reminders -- an organization's assessment link closing within
  ASSESSMENT_HOURS that the member has not started.

Each goes out once (UserPreference.sent remembers), only when both the
email switch and its own switch are on, and at most MAX_EMAILS_PER_CYCLE
per run so a big backlog can't stall the cycle.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from email.message import EmailMessage

from sqlalchemy import func

from app import db
from app.account import preferences
from app.auth import email_verification
from app.billing.plans import PLANS, active_plan, plan_name, points_for_tokens
from app.models import (Assessment, OrganizationMember, Payment, ProctorSession, TokenUsageEvent, User,
                        UserPreference)

logger = logging.getLogger("orchestrator.reminders")

LOW_COIN_POINTS = 10
RENEWAL_DAYS = 3
ASSESSMENT_HOURS = 24
MAX_EMAILS_PER_CYCLE = 100
IST = timedelta(hours=5, minutes=30)


def _site_url() -> str:
    """SITE_URL, else the server's own https origin (staging links to staging)."""
    explicit = os.environ.get("SITE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",")]
    return next((o.rstrip("/") for o in origins if o.startswith("https://")), "https://www.skilldara.com")


SITE_URL = _site_url()


def _send(user: User, subject: str, lines: list[str], to: str | None = None) -> bool:
    first = (user.name or "there").split()[0]
    message = EmailMessage()
    message["Subject"] = subject
    message.set_content(
        f"Hi {first},\n\n" + "\n".join(lines) + f"\n\nOpen SkillDARA: {SITE_URL}\n\n"
        "You can change which emails you get in Settings > Notifications.\n\n- SkillDARA"
    )
    try:
        email_verification._deliver(to or user.email, message)
        return True
    except email_verification.VerificationError:
        return False


class _Run:
    """Shared state of one cycle: the email budget and the saved 'sent' marks."""

    def __init__(self, session, now: datetime):
        self.session = session
        self.now = now
        self.left = MAX_EMAILS_PER_CYCLE
        self.rows: dict[str, UserPreference] = {}

    def row(self, user_id: str) -> UserPreference:
        if user_id not in self.rows:
            row = self.session.get(UserPreference, user_id)
            if row is None:
                row = UserPreference(user_id=user_id, prefs={}, sent={})
                self.session.add(row)
            self.rows[user_id] = row
        return self.rows[user_id]

    def prefs(self, user_id: str) -> dict:
        return preferences._clean(self.row(user_id).prefs)

    def sent(self, user_id: str, key: str):
        return (self.row(user_id).sent or {}).get(key)

    def mark(self, user_id: str, key: str, value) -> None:
        row = self.row(user_id)
        row.sent = {**(row.sent or {}), key: value}
        self.session.commit()

    def wants(self, user_id: str, switch: str) -> bool:
        notifications = self.prefs(user_id)["notifications"]
        return notifications["email"] and notifications[switch]


def _agent_label(name: str) -> str:
    return (name or "Other").replace("_", " ").replace("-", " ").title()


def weekly_progress(run: _Run) -> None:
    local = run.now + IST
    # Monday from 9:00 India time.
    if local.weekday() != 0 or local.hour < 9:
        return
    year, week, _ = local.isocalendar()
    stamp = f"{year}-W{week:02d}"
    since = run.now - timedelta(days=7)
    for row in run.session.query(UserPreference).all():
        if run.left <= 0:
            return
        if not run.wants(row.user_id, "weekly_progress") or run.sent(row.user_id, "weekly") == stamp:
            continue
        user = run.session.get(User, row.user_id)
        if user is None:
            continue
        usage = (run.session.query(TokenUsageEvent.agent_name, func.count(TokenUsageEvent.id),
                                   func.coalesce(func.sum(TokenUsageEvent.tokens), 0))
                 .filter(TokenUsageEvent.user_id == user.id, TokenUsageEvent.created_at >= since)
                 .group_by(TokenUsageEvent.agent_name).all())
        if usage:
            lines = ["Here is what you did on SkillDARA last week:", ""]
            lines += [f"- {_agent_label(name)}: {count} request{'s' if count != 1 else ''}, "
                      f"{points_for_tokens(int(tokens), user.tokens_per_point):g} coins" for name, count, tokens in usage]
            lines += ["", "Keep the streak going this week."]
        else:
            lines = ["You didn't use SkillDARA last week. A short practice session today keeps your skills fresh."]
        run.left -= 1
        if _send(user, "Your SkillDARA week", lines):
            run.mark(user.id, "weekly", stamp)


def low_coins(run: _Run) -> None:
    month = (run.now + IST).strftime("%Y-%m")
    recent = run.now - timedelta(days=7)
    active_users = {user_id for (user_id,) in run.session.query(TokenUsageEvent.user_id)
                    .filter(TokenUsageEvent.created_at >= recent).distinct()}
    if not active_users:
        return
    users = (run.session.query(User)
             .filter(User.id.in_(active_users), User.token_balance < User.tokens_per_point * LOW_COIN_POINTS).all())
    for user in users:
        if run.left <= 0:
            return
        if not run.wants(user.id, "low_coin_warning") or run.sent(user.id, "low_coins") == month:
            continue
        points = points_for_tokens(max(0, user.token_balance), user.tokens_per_point)
        run.left -= 1
        if _send(user, "You're running low on SkillDARA coins",
                 [f"You have {points:g} coins left. Top up in Settings > Billing so your practice isn't interrupted."]):
            run.mark(user.id, "low_coins", month)


def renewal(run: _Run) -> None:
    since = run.now - timedelta(days=400)
    payments = (run.session.query(Payment).filter(Payment.status == "paid", Payment.paid_at >= since)
                .order_by(Payment.paid_at.desc()).all())
    by_user: dict[str, list[Payment]] = {}
    for payment in payments:
        by_user.setdefault(payment.user_id, []).append(payment)
    for user_id, paid in by_user.items():
        if run.left <= 0:
            return
        plan_id, expires = active_plan(paid, run.now)
        if not expires or expires - run.now > timedelta(days=RENEWAL_DAYS):
            continue
        if PLANS.get(plan_id, {}).get("subscription"):
            continue
        prefs = run.prefs(user_id)
        if not (prefs["notifications"]["email"] and prefs["billing"]["renewal_reminder"]):
            continue
        if run.sent(user_id, "renewal") == expires.isoformat():
            continue
        user = run.session.get(User, user_id)
        if user is None:
            continue
        when = (expires + IST).strftime("%d %b %Y")
        run.left -= 1
        if _send(user, f"Your {plan_name(plan_id)} plan ends on {when}",
                 [f"Your {plan_name(plan_id)} plan ends on {when}. Renew it in Settings > Billing to keep your benefits."],
                 to=prefs["billing"]["billing_email"] or None):
            run.mark(user_id, "renewal", expires.isoformat())


def assessments(run: _Run) -> None:
    soon = run.now + timedelta(hours=ASSESSMENT_HOURS)
    closing = (run.session.query(Assessment)
               .filter(Assessment.active.is_(True), Assessment.closes_at.isnot(None),
                       Assessment.closes_at > run.now, Assessment.closes_at <= soon).all())
    for assessment in closing:
        if assessment.opens_at and assessment.opens_at > run.now:
            continue
        members = run.session.query(OrganizationMember).filter_by(organization_id=assessment.organization_id).all()
        for member in members:
            if run.left <= 0:
                return
            if member.role != "member" or not run.wants(member.user_id, "assessment_reminders"):
                continue
            done = list(run.sent(member.user_id, "assessments") or [])
            if assessment.id in done:
                continue
            started = (run.session.query(ProctorSession.id)
                       .filter_by(user_id=member.user_id, assessment_id=assessment.id).first())
            if started:
                continue
            user = run.session.get(User, member.user_id)
            if user is None:
                continue
            when = (assessment.closes_at + IST).strftime("%d %b, %I:%M %p")
            run.left -= 1
            if _send(user, f"Reminder: {assessment.title} closes soon",
                     [f'Your assessment "{assessment.title}" closes on {when} (India time).',
                      f"Start it here: {SITE_URL}/assessment/{assessment.token}"]):
                run.mark(member.user_id, "assessments", (done + [assessment.id])[-200:])


def send_due(now: datetime | None = None) -> None:
    """Send every reminder that is due. Never raises: one failing job must not
    stop the monitoring cycle that calls it."""
    if email_verification._smtp_settings() is None:
        return
    session = db.get_session()
    try:
        run = _Run(session, now or datetime.utcnow())
        for job in (assessments, renewal, low_coins, weekly_progress):
            try:
                job(run)
            except Exception:
                session.rollback()
                run.rows.clear()
                logger.exception("reminder job %s failed", job.__name__)
    finally:
        session.close()

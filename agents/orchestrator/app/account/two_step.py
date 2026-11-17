"""Two-step verification by email: when it is on, a password sign-in only
gives a session after the 6-digit code emailed to the account is entered.

Google sign-in skips it (Google already checks the person). The code is
stored only as an HMAC keyed with JWT_SECRET, lasts CODE_TTL, allows
MAX_ATTEMPTS wrong guesses and can be re-sent once per RESEND_COOLDOWN. The
sign-in in between is carried by a short-lived signed "challenge" token that
cannot be used as a session.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from email.message import EmailMessage

import jwt

from app import db
from app.auth import email_verification
from app.auth.security import JWT_ALGORITHM, JWT_SECRET
from app.models import TwoStepSetting, User

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5
_PURPOSE = "two_step_login"


class TwoStepError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _hash(user_id: str, code: str) -> str:
    return hmac.new(JWT_SECRET.encode(), f"two-step:{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def available() -> bool:
    """Codes go by email, so this needs SMTP."""
    return email_verification._smtp_settings() is not None


def is_enabled(user_id: str) -> bool:
    session = db.get_session()
    try:
        row = session.get(TwoStepSetting, user_id)
        return bool(row and row.enabled)
    finally:
        session.close()


def mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:2]}{'*' * max(1, len(name) - 2)}@{domain}"


def _email(user: User, code: str, reason: str) -> None:
    first = (user.name or "there").split()[0]
    minutes = int(CODE_TTL.total_seconds() // 60)
    message = EmailMessage()
    message["Subject"] = f"{code} is your SkillDARA sign-in code"
    message.set_content(
        f"Hi {first},\n\nYour SkillDARA {reason} code is: {code}\n\nIt expires in {minutes} minutes.\n\n"
        "If this wasn't you, change your password in Settings > Security.\n\n- SkillDARA"
    )
    message.add_alternative(
        f"""<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#1c2434">
<h2 style="color:#2851d8">Your {reason} code</h2>
<p>Hi {first},</p>
<p style="font-size:30px;font-weight:bold;letter-spacing:6px;background:#f4f5f8;padding:14px;text-align:center;border-radius:8px">{code}</p>
<p>It expires in {minutes} minutes.</p>
<p style="color:#667085;font-size:13px">If this wasn't you, change your password in Settings &gt; Security.</p>
</div>""",
        subtype="html",
    )
    try:
        email_verification._deliver(user.email, message)
    except email_verification.VerificationError as exc:
        raise TwoStepError(exc.status_code, exc.message) from exc


def send_code(user_id: str, reason: str = "sign-in", now: datetime | None = None, force: bool = False) -> None:
    """Make a new code and email it. `force` skips the resend cooldown (the
    first code of a sign-in)."""
    now = now or datetime.utcnow()
    session = db.get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            raise TwoStepError(401, "This account no longer exists.")
        row = session.get(TwoStepSetting, user_id, with_for_update=True)
        if row is None:
            row = TwoStepSetting(user_id=user_id, enabled=False, attempts=0)
            session.add(row)
        if not force and row.code_sent_at and now - row.code_sent_at < RESEND_COOLDOWN:
            raise TwoStepError(429, "Please wait a minute before asking for another code.")
        code = f"{secrets.randbelow(1_000_000):06d}"
        row.code_hash = _hash(user_id, code)
        row.code_expires_at = now + CODE_TTL
        row.code_sent_at = now
        row.attempts = 0
        session.commit()
        _email(user, code, reason)
    finally:
        session.close()


def check_code(user_id: str, code: str, now: datetime | None = None) -> None:
    """Raise unless `code` is the current one. A right code is used up."""
    now = now or datetime.utcnow()
    code = (code or "").strip()
    session = db.get_session()
    try:
        row = session.get(TwoStepSetting, user_id, with_for_update=True)
        if row is None or not row.code_hash or not row.code_expires_at:
            raise TwoStepError(400, "Please ask for a new code.")
        if row.code_expires_at < now:
            raise TwoStepError(400, "This code has expired. Please ask for a new one.")
        if row.attempts >= MAX_ATTEMPTS:
            raise TwoStepError(429, "Too many wrong codes. Please ask for a new one.")
        if not hmac.compare_digest(row.code_hash, _hash(user_id, code)):
            row.attempts += 1
            session.commit()
            raise TwoStepError(400, "That code is not right. Please check your email and try again.")
        row.code_hash = None
        row.code_expires_at = None
        row.attempts = 0
        session.commit()
    finally:
        session.close()


def set_enabled(user_id: str, enabled: bool) -> None:
    session = db.get_session()
    try:
        row = session.get(TwoStepSetting, user_id, with_for_update=True)
        if row is None:
            session.add(TwoStepSetting(user_id=user_id, enabled=enabled, attempts=0))
        else:
            row.enabled = enabled
        session.commit()
    finally:
        session.close()


def challenge_for(user_id: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "purpose": _PURPOSE, "iat": now, "exp": now + int(CODE_TTL.total_seconds())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def user_for_challenge(challenge: str) -> str:
    try:
        payload = jwt.decode(challenge, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TwoStepError(401, "This sign-in has expired. Please log in again.") from exc
    if payload.get("purpose") != _PURPOSE:
        raise TwoStepError(401, "This sign-in has expired. Please log in again.")
    return payload["sub"]


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(TwoStepSetting).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()

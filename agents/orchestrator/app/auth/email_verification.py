"""Email verification by a 6-digit code sent over SMTP.

Password signup can't prove the person owns the address, and the platform
relies on it (Razorpay page payments are credited to the account with the
email entered there). So a password account must confirm its email before
using the agents; Google accounts are verified by Google.

The code itself is never stored: only an HMAC of it, keyed with JWT_SECRET
and bound to the user id, so a leaked database row can't be replayed. A code
lasts CODE_TTL, allows MAX_ATTEMPTS wrong guesses, and can be re-sent once
per RESEND_COOLDOWN (plus a per-hour rate limit on the route).

SMTP comes from the environment (SMTP_HOST, SMTP_PORT, SMTP_USER,
SMTP_PASSWORD, SMTP_FROM) -- never from code. Verification is only enforced
when SMTP is configured, so a missing setting can't lock everyone out; set
EMAIL_VERIFICATION_REQUIRED=true/false to force it either way.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage

from app.auth.security import JWT_SECRET
from app import db
from app.models import User

logger = logging.getLogger("orchestrator.email_verification")

CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
MAX_ATTEMPTS = 5
SMTP_TIMEOUT_SECONDS = 15


class VerificationError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _smtp_settings() -> dict | None:
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    if not (host and user and password):
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": user,
        "password": password,
        "sender": os.environ.get("SMTP_FROM", "").strip() or user,
    }


def verification_required() -> bool:
    setting = os.environ.get("EMAIL_VERIFICATION_REQUIRED", "auto").strip().lower()
    if setting in {"true", "1", "yes"}:
        return True
    if setting in {"false", "0", "no"}:
        return False
    return _smtp_settings() is not None


def is_verified(user: User) -> bool:
    """Whether this account may use the agents."""
    return bool(user.email_verified) or not verification_required()


def _code_hash(user_id: str, code: str) -> str:
    return hmac.new(JWT_SECRET.encode(), f"email-code:{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def _send(to_address: str, name: str, code: str) -> None:
    settings = _smtp_settings()
    if settings is None:
        raise VerificationError(503, "Email verification is not available right now. Please try again later.")
    message = EmailMessage()
    message["Subject"] = f"{code} is your DigiDARA verification code"
    message["From"] = f"DigiDARA AI Agents <{settings['sender']}>"
    message["To"] = to_address
    first_name = (name or "there").split()[0]
    message.set_content(
        f"Hi {first_name},\n\n"
        f"Your DigiDARA verification code is: {code}\n\n"
        f"It expires in {int(CODE_TTL.total_seconds() // 60)} minutes. Enter it in the app to verify your email.\n\n"
        "If you didn't create a DigiDARA account, you can ignore this email.\n\n"
        "- DigiDARA AI Agents"
    )
    message.add_alternative(
        f"""<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;color:#1c2434">
<h2 style="color:#2851d8">Verify your email</h2>
<p>Hi {first_name},</p>
<p>Your DigiDARA verification code is:</p>
<p style="font-size:30px;font-weight:bold;letter-spacing:6px;background:#f4f5f8;padding:14px;text-align:center;border-radius:8px">{code}</p>
<p>It expires in {int(CODE_TTL.total_seconds() // 60)} minutes.</p>
<p style="color:#667085;font-size:13px">If you didn't create a DigiDARA account, you can ignore this email.</p>
</div>""",
        subtype="html",
    )
    context = ssl.create_default_context()
    try:
        if settings["port"] == 465:
            with smtplib.SMTP_SSL(settings["host"], settings["port"], timeout=SMTP_TIMEOUT_SECONDS, context=context) as smtp:
                smtp.login(settings["user"], settings["password"])
                smtp.send_message(message)
        else:
            with smtplib.SMTP(settings["host"], settings["port"], timeout=SMTP_TIMEOUT_SECONDS) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings["user"], settings["password"])
                smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        # Never the exception text: it can carry server replies and addresses.
        logger.warning("verification email could not be sent: %s", type(exc).__name__)
        raise VerificationError(502, "We couldn't send the email just now. Please try again in a minute.") from exc


def send_code(user_id: str, now: datetime | None = None) -> None:
    """Create a new code, store its hash and email it. A new code replaces
    the old one and resets the attempt count."""
    now = now or datetime.utcnow()
    session = db.get_session()
    try:
        user = session.get(User, user_id, with_for_update=True)
        if user is None:
            raise VerificationError(401, "This account no longer exists.")
        if user.email_verified:
            raise VerificationError(409, "Your email is already verified.")
        if user.email_code_sent_at and now - user.email_code_sent_at < RESEND_COOLDOWN:
            wait = int((RESEND_COOLDOWN - (now - user.email_code_sent_at)).total_seconds()) + 1
            raise VerificationError(429, f"Please wait {wait} seconds before asking for a new code.")
        code = f"{secrets.randbelow(1_000_000):06d}"
        user.email_code_hash = _code_hash(user.id, code)
        user.email_code_expires_at = now + CODE_TTL
        user.email_code_sent_at = now
        user.email_code_attempts = 0
        email, name = user.email, user.name
        session.commit()
    finally:
        session.close()
    _send(email, name, code)


def verify_code(user_id: str, code: str, now: datetime | None = None) -> None:
    """Mark the email verified if `code` matches; otherwise count the attempt."""
    now = now or datetime.utcnow()
    code = (code or "").strip()
    session = db.get_session()
    try:
        user = session.get(User, user_id, with_for_update=True)
        if user is None:
            raise VerificationError(401, "This account no longer exists.")
        if user.email_verified:
            return
        if not user.email_code_hash or not user.email_code_expires_at or now > user.email_code_expires_at:
            raise VerificationError(400, "This code has expired. Please ask for a new one.")
        if user.email_code_attempts >= MAX_ATTEMPTS:
            raise VerificationError(429, "Too many wrong codes. Please ask for a new one.")
        if not (code.isdigit() and len(code) == 6 and hmac.compare_digest(user.email_code_hash, _code_hash(user.id, code))):
            user.email_code_attempts += 1
            session.commit()
            left = MAX_ATTEMPTS - user.email_code_attempts
            raise VerificationError(400, f"That code is not right. {left} {'try' if left == 1 else 'tries'} left." if left else "Too many wrong codes. Please ask for a new one.")
        user.email_verified = True
        user.email_code_hash = None
        user.email_code_expires_at = None
        user.email_code_attempts = 0
        session.commit()
    finally:
        session.close()

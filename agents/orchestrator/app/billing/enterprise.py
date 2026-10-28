"""Enterprise enquiries from the billing page.

An organization (college, institute, company) fills in its details; the
enquiry is saved and emailed to SkillDARA support (ENTERPRISE_ENQUIRY_EMAIL,
default support@digidaratechnologies.com) with Reply-To set to the contact,
so support can answer straight from their inbox.
"""
from __future__ import annotations

import html
import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from app import db
from app.auth.email_verification import SMTP_TIMEOUT_SECONDS, _smtp_settings
from app.models import EnterpriseEnquiry

logger = logging.getLogger("orchestrator.billing.enterprise")

SUPPORT_EMAIL = os.environ.get("ENTERPRISE_ENQUIRY_EMAIL", "").strip() or "support@digidaratechnologies.com"
ORGANIZATION_TYPES = {"college": "College / university", "training_institute": "Training institute",
                      "company": "Company", "other": "Other"}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EnquiryError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _clean(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def submit(user_id: str | None, account_email: str, data: dict) -> dict:
    enquiry = EnterpriseEnquiry(
        user_id=user_id,
        organization=_clean(data.get("organization"), 255),
        organization_type=data.get("organization_type") if data.get("organization_type") in ORGANIZATION_TYPES else "other",
        contact_name=_clean(data.get("contact_name"), 255),
        email=_clean(data.get("email"), 255).lower(),
        phone=re.sub(r"[^\d+ -]", "", str(data.get("phone") or ""))[:32].strip(),
        learners=data.get("learners") if isinstance(data.get("learners"), int) and 0 < data["learners"] <= 1_000_000 else None,
        city=_clean(data.get("city"), 120),
        message=str(data.get("message") or "").strip()[:2000],
    )
    if len(enquiry.organization) < 2:
        raise EnquiryError(400, "Enter your organization's name.")
    if len(enquiry.contact_name) < 2:
        raise EnquiryError(400, "Enter the contact person's name.")
    if not _EMAIL.match(enquiry.email):
        raise EnquiryError(400, "Enter a valid email address.")
    if len(re.sub(r"\D", "", enquiry.phone)) < 8:
        raise EnquiryError(400, "Enter a valid phone number.")

    session = db.get_session()
    try:
        session.add(enquiry)
        session.commit()
        enquiry_id = enquiry.id
        sent = _email(enquiry, account_email)
        if sent:
            enquiry.emailed = True
            session.commit()
    finally:
        session.close()
    if not sent:
        # Saved, but support has not been told: say so, with the address to write to.
        raise EnquiryError(502, f"We saved your details but could not email our team just now. "
                                f"Please also write to {SUPPORT_EMAIL}.")
    return {"id": enquiry_id, "sent_to": SUPPORT_EMAIL}


def _email(enquiry: EnterpriseEnquiry, account_email: str) -> bool:
    settings = _smtp_settings()
    if settings is None:
        logger.warning("enterprise enquiry %s not emailed: SMTP is not configured", enquiry.id)
        return False
    rows = [
        ("Organization", enquiry.organization),
        ("Type", ORGANIZATION_TYPES.get(enquiry.organization_type, enquiry.organization_type)),
        ("Contact person", enquiry.contact_name),
        ("Email", enquiry.email),
        ("Phone", enquiry.phone),
        ("Number of learners", str(enquiry.learners) if enquiry.learners else "Not given"),
        ("City", enquiry.city or "Not given"),
        ("SkillDARA account", account_email or "Not signed in"),
    ]
    message = EmailMessage()
    message["Subject"] = f"Enterprise enquiry: {enquiry.organization}"
    message["From"] = f"SkillDARA <{settings['sender']}>"
    message["To"] = SUPPORT_EMAIL
    message["Reply-To"] = enquiry.email
    message.set_content(
        "A new Enterprise enquiry from the SkillDARA billing page.\n\n"
        + "\n".join(f"{label}: {value}" for label, value in rows)
        + f"\n\nMessage:\n{enquiry.message or '(none)'}\n\nReply to this email to answer {enquiry.contact_name}.\n"
    )
    table = "".join(
        f'<tr><td style="padding:6px 12px;color:#667085">{html.escape(label)}</td>'
        f'<td style="padding:6px 12px"><b>{html.escape(value)}</b></td></tr>' for label, value in rows
    )
    message.add_alternative(
        f"""<div style="font-family:Arial,sans-serif;max-width:560px;color:#1c2434">
<h2 style="color:#2851d8">New Enterprise enquiry</h2>
<table style="border-collapse:collapse">{table}</table>
<h3>Message</h3><p style="white-space:pre-wrap">{html.escape(enquiry.message or "(none)")}</p>
<p style="color:#667085;font-size:13px">Reply to this email to answer {html.escape(enquiry.contact_name)} directly.</p>
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
        return True
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("enterprise enquiry %s not emailed: %s", enquiry.id, type(exc).__name__)
        return False

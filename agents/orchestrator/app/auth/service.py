from datetime import datetime
import os

from app.auth.security import hash_password
from app.db import get_session
from app.models import Payment, User


def get_by_email(email: str) -> User | None:
    session = get_session()
    try:
        return session.query(User).filter_by(email=email).first()
    finally:
        session.close()


def get_by_id(user_id: str) -> User | None:
    session = get_session()
    try:
        return session.get(User, user_id)
    finally:
        session.close()


def get_by_google_id(google_id: str) -> User | None:
    session = get_session()
    try:
        return session.query(User).filter_by(google_id=google_id).first()
    finally:
        session.close()


def create_user(
    name: str,
    email: str,
    mobile: str | None,
    password_hash: str,
    consent_policy_version: str,
) -> User:
    session = get_session()
    try:
        user = User(
            name=name,
            email=email,
            mobile=mobile,
            password_hash=password_hash,
            consent_accepted_at=datetime.utcnow(),
            consent_policy_version=consent_policy_version,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def create_google_user(name: str, email: str, google_id: str, consent_policy_version: str) -> User:
    """No password_hash — this account can only ever sign in via Google."""
    session = get_session()
    try:
        user = User(
            name=name,
            email=email,
            google_id=google_id,
            consent_accepted_at=datetime.utcnow(),
            consent_policy_version=consent_policy_version,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def delete_user(user_id: str) -> None:
    """DPDP Act 2023 right to erasure. Payment rows are intentionally kept
    (financial records DigiDARA must retain under tax/accounting law and
    which hold no name/email/mobile of their own -- see app/models.py) but
    are no longer reachable through any authenticated account afterwards."""
    session = get_session()
    try:
        user = session.get(User, user_id)
        if user:
            session.delete(user)
            session.commit()
    finally:
        session.close()


def export_user_data(user_id: str) -> dict | None:
    """DPDP Act 2023 right to access -- a machine-readable dump of every
    piece of personal data this service holds about the requesting user."""
    session = get_session()
    try:
        user = session.get(User, user_id)
        if not user:
            return None
        payments = session.query(Payment).filter_by(user_id=user_id).all()
        return {
            "account": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "mobile": user.mobile,
                "google_linked": user.google_id is not None,
                "created_at": user.created_at.isoformat(),
                "token_balance": user.token_balance,
                "consent_accepted_at": user.consent_accepted_at.isoformat() if user.consent_accepted_at else None,
                "consent_policy_version": user.consent_policy_version,
            },
            "payments": [
                {
                    "plan_id": payment.plan_id,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": payment.status,
                    "created_at": payment.created_at.isoformat(),
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                }
                for payment in payments
            ],
        }
    finally:
        session.close()


def deduct_tokens(user_id: str, amount: int) -> bool:
    """
    Atomically deduct `amount` tokens, in a single UPDATE guarded by a
    balance check, so two concurrent requests can never both succeed past
    a balance that only covers one of them. Returns True if the deduction
    happened, False if the balance was insufficient.
    """
    from sqlalchemy import text
    from app.db import get_session

    session = get_session()
    try:
        result = session.execute(
            text(
                "UPDATE users SET token_balance = token_balance - :amount "
                "WHERE id = :user_id AND token_balance >= :amount"
            ),
            {"amount": amount, "user_id": user_id},
        )
        session.commit()
        return result.rowcount > 0
    finally:
        session.close()


def settle_tokens(user_id: str, amount: int) -> None:
    """
    Post-hoc charge for real, already-incurred usage (the actual LLM cost
    an agent reports back after the call already happened). Unlike
    deduct_tokens, this is unconditional -- the call already happened, so
    there is nothing left to gate. A balance can go slightly negative here
    at most once, right at the moment it crosses zero; the caller is
    already blocked from starting further requests at that point.
    """
    from sqlalchemy import text
    from app.db import get_session

    session = get_session()
    try:
        session.execute(
            text("UPDATE users SET token_balance = token_balance - :amount WHERE id = :user_id"),
            {"amount": amount, "user_id": user_id},
        )
        session.commit()
    finally:
        session.close()


def credit_tokens(user_id: str, amount: int) -> None:
    """Add tokens to a balance -- used after a verified top-up payment."""
    from sqlalchemy import text
    from app.db import get_session

    session = get_session()
    try:
        session.execute(
            text("UPDATE users SET token_balance = token_balance + :amount WHERE id = :user_id"),
            {"amount": amount, "user_id": user_id},
        )
        session.commit()
    finally:
        session.close()


def link_google_id(user_id: str, google_id: str) -> User:
    """A password account signing in with Google for the first time under
    the same email — attach the Google identity rather than creating a
    second account."""
    session = get_session()
    try:
        user = session.get(User, user_id)
        user.google_id = google_id
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def set_password(user_id: str, password_hash: str) -> None:
    session = get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            return
        user.password_hash = password_hash
        session.commit()
    finally:
        session.close()


def seed_admin_from_env() -> None:
    """Create or promote the configured platform administrator once.

    Existing passwords are deliberately never reset during startup.
    """
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    session = get_session()
    try:
        user = session.query(User).filter_by(email=email).first()
        if user is None:
            session.add(User(name="Admin", email=email, password_hash=hash_password(password), is_admin=True))
            session.commit()
        elif not user.is_admin:
            user.is_admin = True
            session.commit()
    finally:
        session.close()

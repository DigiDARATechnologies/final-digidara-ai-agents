from datetime import datetime
import os

from app.auth.security import hash_password
from app.billing.plans import points_for_tokens
from app.agent_state import service as agent_state_service
from app.chat_history import service as chat_history_service
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
            email_verified=True,
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
    chat_history_service.purge_history(user_id)
    agent_state_service.purge_state(user_id)
    _purge_phase2(user_id)
    session = get_session()
    try:
        user = session.get(User, user_id)
        if user:
            session.delete(user)
            session.commit()
    finally:
        session.close()


def _purge_phase2(user_id: str) -> None:
    """Learner profile, levels, readiness history, organization membership and
    A2A tasks. Local imports: those modules import this one."""
    from app.learner import service as learner_service
    from app.models import A2ATask
    from app.organizations import service as org_service
    from app.readiness import service as readiness_service

    from app.coach import service as coach_service
    from app.memory import service as memory_service

    learner_service.purge(user_id)
    readiness_service.purge(user_id)
    org_service.purge(user_id)
    memory_service.clear(user_id)
    coach_service.purge(user_id)
    session = get_session()
    try:
        session.query(A2ATask).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()


def _export_phase2(user_id: str) -> dict:
    from app.coach import service as coach_service
    from app.learner import service as learner_service
    from app.memory import service as memory_service
    from app.organizations import service as org_service
    from app.readiness import service as readiness_service

    return {
        **learner_service.export_data(user_id),
        "readiness_history": readiness_service.history(user_id),
        "organization": org_service.export_data(user_id),
        "memory": memory_service.list_for(user_id),
        "career_plan": coach_service.get(user_id),
    }


def export_user_data(user_id: str) -> dict | None:
    """DPDP Act 2023 right to access -- a machine-readable dump of every
    piece of personal data this service holds about the requesting user."""
    chats, _ = chat_history_service.get_history(user_id)
    saved_states = agent_state_service.get_all(user_id)
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
                "points_balance": points_for_tokens(max(0, user.token_balance), user.tokens_per_point),
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
            "chat_history": chats,
            "agent_state": saved_states,
            **_export_phase2(user_id),
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


def settle_tokens(user_id: str, amount: int, agent_name: str = "", action: str = "") -> None:
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
    from app.models import TokenUsageEvent

    session = get_session()
    try:
        session.execute(
            text("UPDATE users SET token_balance = token_balance - :amount WHERE id = :user_id"),
            {"amount": amount, "user_id": user_id},
        )
        # Recorded in the same transaction as the charge, so the monthly
        # usage in Settings always matches what was taken from the balance.
        session.add(TokenUsageEvent(user_id=user_id, agent_name=(agent_name or "")[:255], action=(action or "")[:100], tokens=amount))
        session.commit()
    finally:
        session.close()


def credit_tokens(user_id: str, amount: int, points: float | None = None) -> None:
    """Add tokens to a balance -- used after a verified top-up payment.

    `points` is what the purchase was sold as. The account's tokens-per-point
    rate is re-blended so the shown balance becomes exactly the points it
    showed before plus the points just bought (100 + 250 = 350), even though
    each plan has its own rate. Without `points` the tokens are added at the
    account's existing rate. The row is locked so a concurrent charge
    (settle_tokens) can't land between reading and writing the balance.
    """
    from app.billing.plans import FREE_TOKENS_PER_POINT

    session = get_session()
    try:
        user = session.get(User, user_id, with_for_update=True)
        if user is None:
            return
        rate = user.tokens_per_point or FREE_TOKENS_PER_POINT
        balance = user.token_balance or 0
        new_balance = balance + amount
        if points and new_balance > 0:
            # A negative balance (the last call overshot) is a debt in tokens;
            # it shows as 0 points, and is paid off out of the new tokens.
            new_points = max(0, balance) / rate + points
            user.tokens_per_point = new_balance / new_points
        user.token_balance = new_balance
        session.commit()
    finally:
        session.close()


def link_google_id(user_id: str, google_id: str) -> User:
    """A password account signing in with Google for the first time under
    the same email — attach the Google identity rather than creating a
    second account.

    Google has just proven this person owns the address. If the account was
    never verified, whoever chose its password never proved that, and may be
    someone who registered the victim's email in advance to keep a way in
    after the real owner arrives. So their password is dropped and every
    existing session is revoked. The owner keeps signing in with Google, and
    PUT /auth/password accepts a new password with no current one once it's
    gone.
    """
    session = get_session()
    try:
        user = session.get(User, user_id)
        user.google_id = google_id
        if not user.email_verified:
            user.password_hash = None
            user.session_version = (user.session_version or 0) + 1
        user.email_verified = True
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def set_password(user_id: str, password_hash: str) -> int | None:
    """Set a new password and sign every existing session out (a stolen
    session must not outlive a password change). Returns the new session
    version, so the caller can hand the current device a fresh token."""
    session = get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            return None
        user.password_hash = password_hash
        user.session_version = (user.session_version or 0) + 1
        session.commit()
        return user.session_version
    finally:
        session.close()


def seed_admin_from_env() -> None:
    """Create or promote the configured platform administrator once.

    An existing admin's password is deliberately never reset during startup.
    Promoting an existing account is different: signup doesn't verify email,
    so an unverified account under ADMIN_EMAIL may have been registered by
    someone else to be handed admin here. Such an account takes the operator's
    ADMIN_PASSWORD and loses every earlier session before it is promoted.
    """
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        return
    session = get_session()
    try:
        user = session.query(User).filter_by(email=email).first()
        if user is None:
            session.add(User(name="Admin", email=email, password_hash=hash_password(password), is_admin=True, email_verified=True))
            session.commit()
        elif not user.is_admin:
            if not user.email_verified:
                user.password_hash = hash_password(password)
                user.session_version = (user.session_version or 0) + 1
                user.email_verified = True
            user.is_admin = True
            session.commit()
    finally:
        session.close()

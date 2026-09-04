from app.db import get_session
from app.models import User


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


def create_user(name: str, email: str, mobile: str | None, password_hash: str) -> User:
    session = get_session()
    try:
        user = User(name=name, email=email, mobile=mobile, password_hash=password_hash)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def create_google_user(name: str, email: str, google_id: str) -> User:
    """No password_hash — this account can only ever sign in via Google."""
    session = get_session()
    try:
        user = User(name=name, email=email, google_id=google_id)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
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

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now() -> datetime:
    """Naive UTC — MySQL's DATETIME column has no timezone concept, so every
    value written here (and every comparison against it) is UTC by
    convention, not by column type."""
    return datetime.utcnow()


def _uuid() -> str:
    return uuid.uuid4().hex


class AgentRegistry(Base):
    """Matches the registry contract from the architecture brief: agent
    identity is (agent_name, version) so v1 and v2 of the same agent can
    coexist during a migration."""

    __tablename__ = "agent_registry"

    agent_name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(50))
    endpoint: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    input_schema: Mapped[dict] = mapped_column(JSON)
    output_schema: Mapped[dict] = mapped_column(JSON)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan_tier: Mapped[str] = mapped_column(String(20), default="free")
    status: Mapped[str] = mapped_column(String(20), default="healthy")
    last_heartbeat: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    __table_args__ = (PrimaryKeyConstraint("agent_name", "version"),)


class User(Base):
    """The platform's one real, password-verified account. Every agent's own
    identity bridge (ensure_profile / ensure_session) keeps working exactly
    as before — they just now receive a name/email that's actually been
    authenticated here instead of self-reported by the browser."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Nullable: a Google-only account (no password ever set) has no hash to
    # check — /auth/login must reject those rather than crash on None.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mobile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    # Starting free balance for every new account; consumed by gateway
    # calls and topped up via Razorpay. See app/billing/routes.py.
    token_balance: Mapped[int] = mapped_column(Integer, default=50000, server_default="50000")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    plan_id: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    razorpay_order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

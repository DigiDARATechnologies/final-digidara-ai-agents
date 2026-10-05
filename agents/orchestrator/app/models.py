import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.billing.plans import FREE_TOKENS_PER_POINT, free_signup_tokens
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
    # MySQL's plain DATETIME has no fractional-seconds precision (fsp=0) --
    # it silently truncates every value written here to the whole second,
    # unlike SQLite (used by the default unit-test suite), which keeps full
    # microsecond precision natively. resolve_healthy() picks the "freshest"
    # of possibly several healthy versions of the same agent by ordering on
    # this column during a version rollout; two versions that register or
    # heartbeat within the same second could tie -- or even invert -- once
    # truncated, so the gateway could nondeterministically route to the
    # stale version instead of the new one. fsp=6 keeps microsecond
    # precision on MySQL too; SQLite is unaffected either way.
    last_heartbeat: Mapped[datetime] = mapped_column(
        DateTime().with_variant(MySQLDateTime(fsp=6), "mysql"), default=_utc_now
    )

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
    # Platform operator status. The gateway derives the Job Agent admin
    # header from this server-side value, never from browser input.
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # True once someone has proven they control `email`: Google sign-in, or
    # the operator's own ADMIN_EMAIL / ADMIN_PASSWORD. Password signup does
    # not verify the address, so anyone can register an account under an
    # email they don't own; see auth/service.py:link_google_id for why that
    # matters when the real owner later signs in with Google.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Embedded in every session token as "sv"; bumping it revokes every token
    # issued before (see auth/security.py:decode_access_token).
    session_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    # Starting free balance for every new account; consumed by gateway
    # calls and topped up via Razorpay. See app/billing/routes.py.
    token_balance: Mapped[int] = mapped_column(Integer, default=free_signup_tokens, server_default="50000")
    # How many of this account's tokens make one displayed point. Accounts
    # from before points, and free accounts, use FREE_TOKENS_PER_POINT; each
    # purchase blends in its plan's rate (auth/service.py:credit_tokens).
    tokens_per_point: Mapped[float] = mapped_column(Float, default=FREE_TOKENS_PER_POINT, server_default="3000")
    # DPDP Act 2023 consent record: the timestamp/policy-version pair the
    # user affirmatively agreed to at signup (see app/auth/consent.py). Not
    # nullable in practice for new rows -- signup rejects a missing
    # consent flag before create_user is ever called -- but nullable here
    # so the column can be added to a table with pre-existing accounts.
    consent_accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ChatHistoryState(Base):
    """Marks an account as migrated even when its history is intentionally empty."""

    __tablename__ = "chat_history_state"

    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(500))
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at_ms: Mapped[int] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (PrimaryKeyConstraint("id", "user_id"),)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(128))
    user_id: Mapped[str] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT, "mysql"))
    display_time: Mapped[str] = mapped_column(String(32))
    message_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "user_id"],
            ["conversations.id", "conversations.user_id"],
            ondelete="CASCADE",
        ),
    )


class AgentChatState(Base):
    """A learner's progress in one chat with one agent, kept server-side so it
    follows them across devices instead of living in browser storage."""

    __tablename__ = "agent_chat_state"

    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    agent_id: Mapped[str] = mapped_column(String(64))
    chat_id: Mapped[str] = mapped_column(String(128))
    state: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    __table_args__ = (PrimaryKeyConstraint("user_id", "agent_id", "chat_id"),)


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
    # Exactly what this payment credited, written in the same UPDATE that
    # marks it paid (billing/routes.py:_mark_paid). History and the admin
    # screens read these, so a later price or plan change can never rewrite
    # what a past payment gave. NULL on payments from before they existed.
    credited_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credited_points: Mapped[float | None] = mapped_column(Float, nullable=True)


class TokenUsageEvent(Base):
    """One charge the gateway made against a user's token balance -- what
    lets Settings > Usage show this month's usage instead of all-time totals."""

    __tablename__ = "token_usage_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    agent_name: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(100), default="")
    tokens: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)

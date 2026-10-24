import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, LargeBinary, PrimaryKeyConstraint, String, Text, UniqueConstraint
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
    # The pending email verification code (auth/email_verification.py): only
    # its keyed hash is stored, with when it expires, when it was last sent
    # (resend cooldown) and how many wrong guesses it has had.
    email_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_code_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_code_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
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
    # The buyer's GSTIN, when they gave one for a business tax invoice.
    customer_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)


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


# ---------------------------------------------------------------------------
# Phase 2: learner profile, per-agent levels, organizations, readiness, A2A.
# All new tables -- create_all adds them on startup without touching any
# existing table, so a database restored from production keeps every row.
# ---------------------------------------------------------------------------


class LearnerProfile(Base):
    """What the learner is preparing for. Collected right after sign-up and
    sent (as the gateway's `learner` envelope field) to every agent, so each
    agent tailors its questions to the same target role, skills and degree."""

    __tablename__ = "learner_profiles"

    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    target_role: Mapped[str] = mapped_column(String(200), default="")
    degree: Mapped[str] = mapped_column(String(200), default="")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    # "fresher" or "experienced" -- framing for interviews and job search.
    experience: Mapped[str] = mapped_column(String(32), default="fresher")
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class AgentLevel(Base):
    """One learner's level with one agent: beginner, medium, hard or
    professional. Every learner starts at beginner with every agent; the
    learner, or an admin of their organization, moves it up."""

    __tablename__ = "agent_levels"

    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    agent_name: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(16), default="beginner")
    # Who set it last: "default", "self", "organization" or "readiness".
    source: Mapped[str] = mapped_column(String(16), default="default")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (PrimaryKeyConstraint("user_id", "agent_name"),)


class RoleTrack(Base):
    """One target role a learner has worked towards. Changing the target role
    starts the new role from zero: the levels in use are saved here for the
    old role, and readiness only counts activity inside the new role's
    periods. Switching back restores that role's levels and periods."""

    __tablename__ = "role_tracks"

    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"))
    # The target role, lowercased with single spaces.
    role_key: Mapped[str] = mapped_column(String(200))
    # agent_name -> {"level", "source"}, saved when the learner left this role.
    levels: Mapped[dict] = mapped_column(JSON, default=dict)
    # The skills the learner had for this role, offered again on switching back.
    skills: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # [[start ISO or null, end ISO or null], ...]: when this role was the target.
    # A null start is "since the account began" (the role held before tracks existed).
    periods: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)

    __table_args__ = (PrimaryKeyConstraint("user_id", "role_key"),)


class Organization(Base):
    """A college, training institute or company that registers its learners
    and monitors their readiness. `join_code` lets learners attach their own
    account; admins can also create member accounts in bulk."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32), default="college")
    join_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    created_by: Mapped[str | None] = mapped_column(String(32), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    member_limit: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    # "active" or "suspended" (a suspended organization's admins and codes stop working).
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class OrgJoinCode(Base):
    """A join code an organization hands out. A code can carry a class --
    department, year and section, each optional -- so everyone who joins
    with it is placed there; a code without them lets the learner choose."""

    __tablename__ = "org_join_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    year: Mapped[str | None] = mapped_column(String(40), nullable=True)
    section: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class OrgOption(Base):
    """A department, year or section an organization uses, offered in the
    join and filter dropdowns. Admins and joining learners can add new ones."""

    __tablename__ = "org_options"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    # "department", "year" or "section".
    kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    __table_args__ = (UniqueConstraint("organization_id", "kind", "value", name="uq_org_option"),)


class OrgAccessLog(Base):
    """Every time an organization admin opens a learner's personal details or
    a chat: who, whose, what and when (DPDP accountability)."""

    __tablename__ = "org_access_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    viewer_id: Mapped[str] = mapped_column(String(32))
    subject_user_id: Mapped[str] = mapped_column(String(32), index=True)
    # "profile", "conversation" or "assistant".
    action: Mapped[str] = mapped_column(String(32))
    target: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)


class OrgAssistantMessage(Base):
    """One turn of an organization admin's chat with the organization
    assistant, kept so the conversation continues across sessions."""

    __tablename__ = "org_assistant_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    # "user" or "assistant".
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    # Actions the assistant took for this reply, shown under it.
    actions: Mapped[list] = mapped_column(JSON, default=list)
    # Microseconds on MySQL, so a question and its reply never share a timestamp.
    created_at: Mapped[datetime] = mapped_column(DateTime().with_variant(MySQLDateTime(fsp=6), "mysql"), default=_utc_now, index=True)


class OrganizationMember(Base):
    """A learner belongs to at most one organization (the unique user_id).

    `progress_shared_at` is the member's own consent (DPDP) to let the
    organization's admins see their readiness and levels; until it is set the
    organization sees only that the member exists."""

    __tablename__ = "organization_members"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    # "owner", "admin" or "member".
    role: Mapped[str] = mapped_column(String(16), default="member")
    # The organization's own id for this person: roll number, employee id.
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress_shared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The learner's class, from their join code or chosen when joining.
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    year: Mapped[str | None] = mapped_column(String(40), nullable=True)
    section: Mapped[str | None] = mapped_column(String(40), nullable=True)
    join_code_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class ReadinessSnapshot(Base):
    """One computed job-readiness result, kept so the profile can show the
    trend over time instead of only today's number."""

    __tablename__ = "readiness_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    band: Mapped[str] = mapped_column(String(32), default="not_started")
    areas: Mapped[dict] = mapped_column(JSON, default=dict)
    # The target role (RoleTrack.role_key) this snapshot was computed for.
    role_key: Mapped[str] = mapped_column(String(200), default="", index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)


class A2ATask(Base):
    """An A2A protocol task (https://a2a-protocol.org) handled by the hub, so
    `tasks/get` can return it after `message/send` has completed."""

    __tablename__ = "a2a_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    context_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    agent_name: Mapped[str] = mapped_column(String(64))
    # The calling agent for agent-to-agent calls, or "user" for a person.
    caller: Mapped[str] = mapped_column(String(64), default="user")
    state: Mapped[str] = mapped_column(String(24), default="submitted")
    task: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class LearnerMemory(Base):
    """Something worth remembering about a learner, shared by every agent:
    their goal and preferences, what they are good at, where they struggle,
    milestones. Agents receive the most relevant few with every call (the
    gateway's `learner.memory`) and add their own over A2A; the learner sees
    and can delete every one (DPDP)."""

    __tablename__ = "learner_memories"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # goal, preference, strength, gap, milestone or note.
    kind: Mapped[str] = mapped_column(String(16), default="note")
    text: Mapped[str] = mapped_column(String(500))
    # Who wrote it: "user", "readiness", or the agent's registry name.
    source: Mapped[str] = mapped_column(String(64), default="user")
    # Only this agent receives it; NULL means every agent does.
    agent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    importance: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now, index=True)


class CareerPlan(Base):
    """The learner's latest AI career plan: weeks of tasks across the agents,
    written from their readiness, profile and memory (app/coach)."""

    __tablename__ = "career_plans"

    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class ChatShareLink(Base):
    """A link to one of a learner's chats that Boss made on request. "private"
    opens only for the account that made it; "public" opens for any signed-in
    account. The token is the link; it is never derived from the chat id."""

    __tablename__ = "chat_share_links"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(String(128))
    mode: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


# ---------------------------------------------------------------------------
# Proctoring and assessment links (app/proctoring).
# ---------------------------------------------------------------------------


class Assessment(Base):
    """A test an organization admin hands out as a link. Opening the link
    (signed in) starts the test on this platform with the admin's settings:
    which interview, how many questions, at what level, and which
    proctoring checks run."""

    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    # Only "mock_interview" for now.
    kind: Mapped[str] = mapped_column(String(32), default="mock_interview")
    # {"round_type", "role_name", "subject", "num_questions", "level"}.
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    # Which checks run: {"tab", "fullscreen", "copy_paste", "webcam", "face", "max_warnings"}.
    proctoring: Mapped[dict] = mapped_column(JSON, default=dict)
    # The link itself (/assessment/<token>); never derived from the id.
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Open between these times (UTC); either may be empty.
    opens_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Members of the organization only, or anyone signed in who has the link.
    members_only: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class ProctorSession(Base):
    """One proctored sitting: a Hard/Professional mock interview or capstone
    viva, or an attempt at an assessment link. The learner agreed to it
    (consent_at) before the camera or any check started."""

    __tablename__ = "proctor_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # "mock_interview_agent" or "capstone_project_agent".
    agent_name: Mapped[str] = mapped_column(String(64))
    # What is proctored: the interview id, or "<submission id>:<attempt>" for a viva.
    ref: Mapped[str] = mapped_column(String(128), default="", index=True)
    assessment_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=True, index=True)
    level: Mapped[str] = mapped_column(String(16), default="")
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    # "active", "completed" or "terminated" (too many warnings).
    status: Mapped[str] = mapped_column(String(16), default="active")
    warnings: Mapped[int] = mapped_column(Integer, default=0)
    integrity: Mapped[int] = mapped_column(Integer, default=100)
    # The agent's result, recorded by the gateway: {"score", "max", "label"}.
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    consent_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ProctorEvent(Base):
    """Something the proctor noticed, e.g. the learner left the tab or a
    second face was in the camera."""

    __tablename__ = "proctor_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("proctor_sessions.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(String(255), default="")
    penalty: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class ProctorSnapshot(Base):
    """A small webcam still taken during a proctored sitting. Kept for
    SNAPSHOT_RETENTION_DAYS (app/proctoring/service.py), then deleted."""

    __tablename__ = "proctor_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("proctor_sessions.id", ondelete="CASCADE"), index=True)
    image: Mapped[bytes] = mapped_column(LargeBinary(length=2**24))
    # What the face check found: number of faces (null until checked).
    faces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, index=True)


# ---------------------------------------------------------------------------
# Knowledge tests (app/knowledge): an organization admin uploads documents,
# the model writes questions from them, and learners take the test through an
# assessment link.
# ---------------------------------------------------------------------------


class KnowledgeTest(Base):
    __tablename__ = "knowledge_tests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    # "mcq", "qa" (written or spoken answers) or "mixed".
    question_type: Mapped[str] = mapped_column(String(8), default="mcq")
    num_questions: Mapped[int] = mapped_column(Integer, default=10)
    seconds_per_question: Mapped[int] = mapped_column(Integer, default=90)
    # What the admin wants the questions to focus on (optional).
    instructions: Mapped[str] = mapped_column(Text, default="")
    # "draft", "generating", "ready" or "failed".
    status: Mapped[str] = mapped_column(String(16), default="draft")
    error: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now, onupdate=_utc_now)


class KnowledgeDocument(Base):
    """One uploaded file and the text read from it (for an image, what the
    vision model read and saw in it). The file itself is not kept."""

    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(String(32), ForeignKey("knowledge_tests.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    # "pdf", "docx", "pptx", "txt" or "image".
    kind: Mapped[str] = mapped_column(String(16))
    chars: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text().with_variant(LONGTEXT, "mysql"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)


class KnowledgeQuestion(Base):
    __tablename__ = "knowledge_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(String(32), ForeignKey("knowledge_tests.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    # "mcq" or "qa".
    qtype: Mapped[str] = mapped_column(String(8))
    question: Mapped[str] = mapped_column(Text)
    # Four choices for a multiple choice question; empty for "qa".
    options: Mapped[list] = mapped_column(JSON, default=list)
    # The right choice's index (mcq).
    correct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The model answer (qa), used to grade; shown in the report.
    answer: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")


class KnowledgeAttempt(Base):
    """One learner's sitting of a knowledge test, through an assessment link
    (its proctored session)."""

    __tablename__ = "knowledge_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    test_id: Mapped[str] = mapped_column(String(32), ForeignKey("knowledge_tests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    proctor_session_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("proctor_sessions.id", ondelete="CASCADE"), nullable=True, unique=True)
    # "active" or "completed".
    status: Mapped[str] = mapped_column(String(16), default="active")
    # question id -> {"answer", "time_taken", "timed_out"}.
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

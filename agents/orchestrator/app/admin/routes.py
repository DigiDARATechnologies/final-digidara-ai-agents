"""Platform admin API: every user, every payment, every agent, and the activity between them.

Read-only, and only for accounts with `users.is_admin` set (that flag is set by
ADMIN_EMAIL / ADMIN_PASSWORD at startup -- see auth/service.py:seed_admin_from_env --
never by anything a browser sends). Opening a user's conversation is written to the
log with the admin's id, because that is personal data.
"""
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_

from app import config
from app.auth.security import get_current_user_id
from app.billing.plans import payment_label, tokens_for_plan_id
from app.db import get_session
from app.models import AgentChatState, AgentRegistry, Conversation, ConversationMessage, Payment, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])

MAX_PAGE_SIZE = 100
_DAY = timedelta(days=1)


def require_admin(user_id: str = Depends(get_current_user_id)) -> str:
    session = get_session()
    try:
        user = session.get(User, user_id)
        if user is None or not user.is_admin:
            raise HTTPException(403, "Administrator access is required.")
        return user_id
    finally:
        session.close()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _rupees(paise) -> float:
    # int(): MySQL's SUM() returns a Decimal, which JSON would send as the string "599.00".
    return round(int(paise or 0) / 100, 2)


def _paid_by_user(session) -> dict[str, int]:
    rows = session.query(Payment.user_id, func.sum(Payment.amount)).filter(Payment.status == "paid").group_by(Payment.user_id).all()
    return {user_id: int(total or 0) for user_id, total in rows}


def _chat_usage(session) -> list[dict]:
    """Chats, distinct users and messages per agent (the chat's agent id, e.g. "capstone-project")."""
    chats = defaultdict(lambda: {"chats": 0, "users": set(), "messages": 0, "last_active": None})
    for agent_id, user_id, updated in session.query(Conversation.agent_id, Conversation.user_id, Conversation.updated_at).filter(Conversation.deleted_at.is_(None)):
        entry = chats[agent_id]
        entry["chats"] += 1
        entry["users"].add(user_id)
        if updated and (entry["last_active"] is None or updated > entry["last_active"]):
            entry["last_active"] = updated
    message_counts = (
        session.query(Conversation.agent_id, func.count(ConversationMessage.id))
        .join(ConversationMessage, (ConversationMessage.conversation_id == Conversation.id) & (ConversationMessage.user_id == Conversation.user_id))
        .filter(Conversation.deleted_at.is_(None))
        .group_by(Conversation.agent_id)
        .all()
    )
    for agent_id, count in message_counts:
        chats[agent_id]["messages"] = int(count)
    return sorted(
        ({"agent_id": agent_id, "chats": e["chats"], "users": len(e["users"]), "messages": e["messages"], "last_active": _iso(e["last_active"])} for agent_id, e in chats.items()),
        key=lambda item: item["chats"], reverse=True,
    )


@router.get("/overview")
def overview(_admin: str = Depends(require_admin)) -> dict:
    now = datetime.utcnow()
    session = get_session()
    try:
        users_total = session.query(func.count(User.id)).scalar() or 0
        users = {
            "total": users_total,
            "new_7d": session.query(func.count(User.id)).filter(User.created_at >= now - 7 * _DAY).scalar() or 0,
            "new_30d": session.query(func.count(User.id)).filter(User.created_at >= now - 30 * _DAY).scalar() or 0,
            "admins": session.query(func.count(User.id)).filter(User.is_admin.is_(True)).scalar() or 0,
        }

        payments = session.query(Payment).all()
        paid = [p for p in payments if p.status == "paid"]
        by_status: dict[str, int] = defaultdict(int)
        for p in payments:
            by_status[p.status] += 1
        by_plan: dict[str, dict] = {}
        for p in paid:
            entry = by_plan.setdefault(p.plan_id, {"plan_id": p.plan_id, "label": payment_label(p.plan_id), "count": 0, "amount": 0})
            entry["count"] += 1
            entry["amount"] += p.amount
        daily: dict[str, dict] = {}
        for offset in range(29, -1, -1):
            day = (now - offset * _DAY).date().isoformat()
            daily[day] = {"date": day, "amount": 0, "count": 0}
        for p in paid:
            when = (p.paid_at or p.created_at)
            key = when.date().isoformat()
            if key in daily:
                daily[key]["amount"] += p.amount
                daily[key]["count"] += 1
        revenue = {
            "currency": "INR",
            "total": _rupees(sum(p.amount for p in paid)),
            "last_30d": _rupees(sum(p.amount for p in paid if (p.paid_at or p.created_at) >= now - 30 * _DAY)),
            "last_7d": _rupees(sum(p.amount for p in paid if (p.paid_at or p.created_at) >= now - 7 * _DAY)),
            "paid_count": len(paid),
            "paying_customers": len({p.user_id for p in paid}),
            "by_status": dict(by_status),
            "by_plan": sorted(({**e, "amount": _rupees(e["amount"])} for e in by_plan.values()), key=lambda e: e["amount"], reverse=True),
            "daily": [{**d, "amount": _rupees(d["amount"])} for d in daily.values()],
        }

        tokens = {
            "outstanding_balance": int(session.query(func.sum(User.token_balance)).scalar() or 0),
            "credited_by_payments": sum(tokens_for_plan_id(p.plan_id) or 0 for p in paid),
            "users_out_of_tokens": session.query(func.count(User.id)).filter(User.token_balance <= 0).scalar() or 0,
        }

        usage = _chat_usage(session)
        week_ago = now - 7 * _DAY
        activity = {
            "conversations": session.query(func.count()).select_from(Conversation).filter(Conversation.deleted_at.is_(None)).scalar() or 0,
            "messages": session.query(func.count(ConversationMessage.id)).scalar() or 0,
            "active_users_7d": session.query(func.count(func.distinct(Conversation.user_id))).filter(Conversation.updated_at >= week_ago, Conversation.deleted_at.is_(None)).scalar() or 0,
            "by_agent": usage,
        }

        cutoff = now - timedelta(seconds=config.HEARTBEAT_TTL_SECONDS)
        registry = session.query(AgentRegistry).all()
        agents = {
            "registered": len({r.agent_name for r in registry}),
            "healthy": len({r.agent_name for r in registry if r.status == "healthy" and r.last_heartbeat >= cutoff}),
        }

        recent_users = session.query(User).order_by(User.created_at.desc()).limit(6).all()
        recent_payments = session.query(Payment).order_by(Payment.created_at.desc()).limit(6).all()
        emails = {u.id: u.email for u in session.query(User.id, User.email).filter(User.id.in_([p.user_id for p in recent_payments] or [""]))}
        return {
            "generated_at": now.isoformat(),
            "users": users, "revenue": revenue, "tokens": tokens, "activity": activity, "agents": agents,
            "recent_signups": [{"id": u.id, "name": u.name, "email": u.email, "created_at": _iso(u.created_at)} for u in recent_users],
            "recent_payments": [
                {"id": p.id, "email": emails.get(p.user_id, ""), "label": payment_label(p.plan_id), "amount": _rupees(p.amount), "status": p.status, "created_at": _iso(p.created_at)}
                for p in recent_payments
            ],
        }
    finally:
        session.close()


@router.get("/users")
def list_users(
    search: str = "", sort: str = Query("newest", pattern="^(newest|oldest|balance|spent|active)$"),
    page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=MAX_PAGE_SIZE), _admin: str = Depends(require_admin),
) -> dict:
    session = get_session()
    try:
        query = session.query(User)
        term = search.strip()
        if term:
            like = f"%{term.lower()}%"
            query = query.filter(or_(func.lower(User.name).like(like), func.lower(User.email).like(like), func.lower(User.mobile).like(like)))
        users = query.all()
        paid = _paid_by_user(session)
        chat_rows = session.query(Conversation.user_id, func.count(), func.max(Conversation.updated_at), func.count(func.distinct(Conversation.agent_id))) \
            .filter(Conversation.deleted_at.is_(None)).group_by(Conversation.user_id).all()
        chats = {user_id: (int(count), last, int(agents)) for user_id, count, last, agents in chat_rows}
        rows = [{
            "id": u.id, "name": u.name, "email": u.email, "mobile": u.mobile or "", "is_admin": bool(u.is_admin), "google": bool(u.google_id),
            "created_at": _iso(u.created_at), "token_balance": u.token_balance, "paid_total": _rupees(paid.get(u.id, 0)),
            "chats": chats.get(u.id, (0, None, 0))[0], "agents_used": chats.get(u.id, (0, None, 0))[2],
            "last_active": _iso(chats.get(u.id, (0, None, 0))[1]),
        } for u in users]
        keys = {
            "newest": (lambda r: r["created_at"] or "", True), "oldest": (lambda r: r["created_at"] or "", False),
            "balance": (lambda r: r["token_balance"], False), "spent": (lambda r: r["paid_total"], True),
            "active": (lambda r: r["last_active"] or "", True),
        }
        key, reverse = keys[sort]
        rows.sort(key=key, reverse=reverse)
        total = len(rows)
        start = (page - 1) * limit
        return {"total": total, "page": page, "limit": limit, "users": rows[start:start + limit]}
    finally:
        session.close()


@router.get("/users/{user_id}")
def user_detail(user_id: str, _admin: str = Depends(require_admin)) -> dict:
    session = get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(404, "User not found.")
        payments = session.query(Payment).filter_by(user_id=user_id).order_by(Payment.created_at.desc()).all()
        conversations = session.query(Conversation).filter_by(user_id=user_id).order_by(Conversation.updated_at.desc()).all()
        counts = dict(
            session.query(ConversationMessage.conversation_id, func.count(ConversationMessage.id)).filter_by(user_id=user_id).group_by(ConversationMessage.conversation_id).all()
        )
        states = session.query(AgentChatState).filter_by(user_id=user_id).order_by(AgentChatState.updated_at.desc()).all()
        paid = [p for p in payments if p.status == "paid"]
        return {
            "user": {
                "id": user.id, "name": user.name, "email": user.email, "mobile": user.mobile or "", "is_admin": bool(user.is_admin),
                "google": bool(user.google_id), "created_at": _iso(user.created_at), "token_balance": user.token_balance,
                "consent_accepted_at": _iso(user.consent_accepted_at), "consent_policy_version": user.consent_policy_version,
            },
            "totals": {
                "paid": _rupees(sum(p.amount for p in paid)), "payments": len(payments), "paid_payments": len(paid),
                "tokens_bought": sum(tokens_for_plan_id(p.plan_id) or 0 for p in paid),
                "conversations": len([c for c in conversations if c.deleted_at is None]),
                "messages": sum(counts.values()),
            },
            "payments": [{
                "id": p.id, "label": payment_label(p.plan_id), "plan_id": p.plan_id, "amount": _rupees(p.amount), "currency": p.currency,
                "status": p.status, "razorpay_order_id": p.razorpay_order_id, "razorpay_payment_id": p.razorpay_payment_id,
                "created_at": _iso(p.created_at), "paid_at": _iso(p.paid_at), "tokens": tokens_for_plan_id(p.plan_id) or 0,
            } for p in payments],
            "conversations": [{
                "id": c.id, "agent_id": c.agent_id, "title": c.title, "messages": counts.get(c.id, 0), "pinned": bool(c.pinned),
                "created_at": _iso(c.created_at), "updated_at": _iso(c.updated_at), "deleted": c.deleted_at is not None,
            } for c in conversations],
            "agent_progress": [{
                "agent_id": s.agent_id, "chat_id": s.chat_id, "step": (s.state or {}).get("step") if isinstance(s.state, dict) else None,
                "updated_at": _iso(s.updated_at),
            } for s in states],
        }
    finally:
        session.close()


@router.get("/users/{user_id}/conversations/{conversation_id}")
def conversation_messages(user_id: str, conversation_id: str, admin_id: str = Depends(require_admin)) -> dict:
    session = get_session()
    try:
        conversation = session.get(Conversation, (conversation_id, user_id))
        if conversation is None:
            raise HTTPException(404, "Conversation not found.")
        messages = session.query(ConversationMessage).filter_by(conversation_id=conversation_id, user_id=user_id).order_by(ConversationMessage.position).all()
        # Personal data: leave a trail of who looked at whose conversation.
        logger.info("admin %s viewed conversation %s of user %s (%d messages)", admin_id, conversation_id, user_id, len(messages))
        return {
            "id": conversation.id, "agent_id": conversation.agent_id, "title": conversation.title,
            "messages": [{"role": m.role, "content": m.content, "time": m.display_time, "created_at": _iso(m.created_at)} for m in messages],
        }
    finally:
        session.close()


@router.get("/payments")
def list_payments(
    status: str = "", search: str = "", page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=MAX_PAGE_SIZE),
    _admin: str = Depends(require_admin),
) -> dict:
    session = get_session()
    try:
        query = session.query(Payment, User.email, User.name).outerjoin(User, User.id == Payment.user_id)
        if status.strip():
            query = query.filter(Payment.status == status.strip())
        term = search.strip().lower()
        if term:
            like = f"%{term}%"
            query = query.filter(or_(func.lower(User.email).like(like), func.lower(User.name).like(like), func.lower(Payment.razorpay_order_id).like(like),
                                     func.lower(func.coalesce(Payment.razorpay_payment_id, "")).like(like)))
        total = query.count()
        rows = query.order_by(Payment.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
        summary_rows = session.query(Payment.status, func.count(), func.sum(Payment.amount)).group_by(Payment.status).all()
        return {
            "total": total, "page": page, "limit": limit,
            "summary": {s: {"count": int(c), "amount": _rupees(a)} for s, c, a in summary_rows},
            "payments": [{
                "id": p.id, "user_id": p.user_id, "email": email or "(deleted account)", "name": name or "", "label": payment_label(p.plan_id),
                "amount": _rupees(p.amount), "currency": p.currency, "status": p.status, "razorpay_order_id": p.razorpay_order_id,
                "razorpay_payment_id": p.razorpay_payment_id, "created_at": _iso(p.created_at), "paid_at": _iso(p.paid_at),
                "tokens": tokens_for_plan_id(p.plan_id) or 0,
            } for p, email, name in rows],
        }
    finally:
        session.close()


@router.get("/agents")
def list_agents(_admin: str = Depends(require_admin)) -> dict:
    now = datetime.utcnow()
    session = get_session()
    try:
        rows = session.query(AgentRegistry).order_by(AgentRegistry.agent_name, AgentRegistry.version.desc()).all()
        cutoff = now - timedelta(seconds=config.HEARTBEAT_TTL_SECONDS)
        agents = []
        for r in rows:
            schema = r.input_schema if isinstance(r.input_schema, dict) else {}
            actions = ((schema.get("properties") or {}).get("action") or {}).get("enum") or []
            age = int((now - r.last_heartbeat).total_seconds()) if r.last_heartbeat else None
            agents.append({
                "agent_name": r.agent_name, "version": r.version, "endpoint": r.endpoint, "description": r.description, "owner": r.owner or "",
                "plan_tier": r.plan_tier, "status": r.status, "last_heartbeat": _iso(r.last_heartbeat), "heartbeat_age_seconds": age,
                "online": r.status == "healthy" and bool(r.last_heartbeat and r.last_heartbeat >= cutoff), "actions": list(actions),
            })
        return {"agents": agents, "chat_usage": _chat_usage(session)}
    finally:
        session.close()

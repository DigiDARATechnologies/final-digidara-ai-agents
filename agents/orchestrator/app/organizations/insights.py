"""The organization admin's dashboard: analytics, filters and drill-down.

Everything here is for one organization's owners/admins (or DigiDARA's
platform admin) and only ever covers members who share their progress --
joining is that consent. Opening a learner's details or one of their chats
is written to the access log, which the organization and the learner can
both read.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.learner import levels as level_rules
from app.learner import service as learner_service
from app.models import (
    Conversation,
    ConversationMessage,
    OrgAccessLog,
    OrganizationMember,
    TokenUsageEvent,
    User,
)
from app.organizations import service as org_service
from app.organizations.service import OrgError, _member_in_org, _require_admin
from app.readiness import service as readiness_service

FILTER_FIELDS = ("department", "year", "section")
INACTIVE_DAYS = 14
ACTIVE_DAYS = 7
TREND_DAYS = 14
LIST_LIMIT = 5
MESSAGE_LIMIT = 500


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None


def filter_members(rows: list[dict], filters: dict) -> list[dict]:
    """Members matching every filter that is set: class fields, join code,
    readiness band, a level with one agent, activity and a text search."""
    now = datetime.utcnow()
    search = str(filters.get("search") or "").strip().lower()
    agent, level = filters.get("agent"), filters.get("level")
    result = []
    for row in rows:
        if row.get("role") != "member":
            continue
        if any(filters.get(field) and (row.get(field) or "") != filters[field] for field in FILTER_FIELDS):
            continue
        if filters.get("code_id") and (row.get("join_code") or {}).get("id") != filters["code_id"]:
            continue
        band = (row.get("readiness") or {}).get("band", "not_started") if row.get("progress_shared") else None
        if filters.get("band") and band != filters["band"]:
            continue
        if agent and level and (row.get("levels") or {}).get(agent) != level:
            continue
        last = _parse_time(row.get("last_active_at"))
        status = filters.get("status")
        if status == "active" and not (last and last >= now - timedelta(days=ACTIVE_DAYS)):
            continue
        if status == "inactive" and last and last >= now - timedelta(days=INACTIVE_DAYS):
            continue
        if status == "not_signed_in" and row.get("has_signed_in"):
            continue
        if search and search not in " ".join(str(row.get(k) or "") for k in ("name", "email", "external_id")).lower():
            continue
        result.append(row)
    return result


def _group(rows: list[dict], field: str) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row.get(field) or "Not set", []).append(row)
    result = []
    for name, members in sorted(groups.items(), key=lambda item: (item[0] == "Not set", item[0].lower())):
        scores = [m["readiness"]["overall"] for m in members if m.get("readiness") and m["readiness"].get("overall") is not None]
        bands = Counter((m.get("readiness") or {}).get("band", "not_started") for m in members if m.get("progress_shared"))
        result.append({
            "name": name, "learners": len(members),
            "average_readiness": round(sum(scores) / len(scores), 1) if scores else None,
            "bands": dict(bands),
        })
    return result


def _brief(row: dict) -> dict:
    return {
        "member_id": row["member_id"], "name": row["name"], "email": row["email"],
        "department": row.get("department"), "year": row.get("year"), "section": row.get("section"),
        "readiness": (row.get("readiness") or {}).get("overall"), "last_active_at": row.get("last_active_at"),
    }


def analytics(admin_id: str, org_id: str, filters: dict) -> dict:
    """The dashboard for every learner matching the filters."""
    rows = filter_members(org_service.members(admin_id, org_id), filters)
    shared = [r for r in rows if r["progress_shared"]]
    now = datetime.utcnow()
    scores = [r["readiness"]["overall"] for r in shared if r.get("readiness") and r["readiness"].get("overall") is not None]
    bands = Counter((r.get("readiness") or {}).get("band", "not_started") for r in shared)
    by_level = {agent: {level: 0 for level in level_rules.LEVELS} for agent in level_rules.LEVELED_AGENTS}
    for row in shared:
        for agent, level in (row.get("levels") or {}).items():
            if agent in by_level and level in by_level[agent]:
                by_level[agent][level] += 1
    active = [r for r in shared if (t := _parse_time(r.get("last_active_at"))) and t >= now - timedelta(days=ACTIVE_DAYS)]
    inactive = [r for r in shared if not (t := _parse_time(r.get("last_active_at"))) or t < now - timedelta(days=INACTIVE_DAYS)]

    user_ids = [r["user_id"] for r in shared]
    usage: dict[str, int] = {}
    daily: dict[str, set[str]] = {}
    if user_ids:
        since = now - timedelta(days=30)
        session = db.get_session()
        try:
            for agent_name, count in (session.query(TokenUsageEvent.agent_name, func.count(TokenUsageEvent.id))
                                      .filter(TokenUsageEvent.user_id.in_(user_ids), TokenUsageEvent.created_at >= since)
                                      .group_by(TokenUsageEvent.agent_name).all()):
                usage[agent_name or "other"] = int(count)
            trend_since = now - timedelta(days=TREND_DAYS)
            for user_id, when in (session.query(TokenUsageEvent.user_id, TokenUsageEvent.created_at)
                                  .filter(TokenUsageEvent.user_id.in_(user_ids), TokenUsageEvent.created_at >= trend_since).all()):
                daily.setdefault(when.date().isoformat(), set()).add(user_id)
        finally:
            session.close()
    trend = []
    for offset in range(TREND_DAYS - 1, -1, -1):
        day = (now - timedelta(days=offset)).date().isoformat()
        trend.append({"date": day, "active_learners": len(daily.get(day, set()))})

    ranked = sorted((r for r in shared if r.get("readiness") and r["readiness"].get("overall") is not None),
                    key=lambda r: r["readiness"]["overall"])
    return {
        "totals": {
            "learners": len(rows), "sharing": len(shared), "signed_in": sum(1 for r in rows if r["has_signed_in"]),
            "active_7d": len(active), "inactive_14d": len(inactive),
            "average_readiness": round(sum(scores) / len(scores), 1) if scores else None,
        },
        "bands": dict(bands),
        "levels": by_level,
        "breakdown": {field: _group(shared, field) for field in FILTER_FIELDS},
        "usage_30d": dict(sorted(usage.items(), key=lambda item: -item[1])),
        "active_trend": trend,
        "top": [_brief(r) for r in reversed(ranked[-LIST_LIMIT:])],
        "needs_attention": [_brief(r) for r in ranked[:LIST_LIMIT]],
        "inactive": [_brief(r) for r in inactive[:LIST_LIMIT]],
        "band_labels": readiness_service.BAND_LABELS,
        "level_labels": level_rules.LEVEL_LABELS,
        "agent_labels": level_rules.LEVELED_AGENTS,
    }


def _log(session, org_id: str, viewer_id: str, subject_user_id: str, action: str, target: str = "") -> None:
    session.add(OrgAccessLog(organization_id=org_id, viewer_id=viewer_id, subject_user_id=subject_user_id,
                             action=action, target=target[:200]))


def _shared_member(session, admin_id: str, org_id: str, member_id: str) -> OrganizationMember:
    _require_admin(session, admin_id, org_id)
    member = _member_in_org(session, org_id, member_id)
    if member.progress_shared_at is None:
        raise OrgError(403, "This member has not agreed to share their progress.")
    return member


def member_detail(admin_id: str, org_id: str, member_id: str) -> dict:
    """Everything about one learner: profile, class, levels, readiness and
    its trend, activity with each agent, their chats and what agents remember."""
    from app.coach import service as coach_service
    from app.memory import service as memory_service

    session = db.get_session()
    try:
        member = _shared_member(session, admin_id, org_id, member_id)
        user = session.get(User, member.user_id)
        activity = [
            {"agent_name": name or "other", "requests": int(count), "last_at": last.isoformat() if last else None}
            for name, count, last in (session.query(TokenUsageEvent.agent_name, func.count(TokenUsageEvent.id),
                                                    func.max(TokenUsageEvent.created_at))
                                      .filter(TokenUsageEvent.user_id == member.user_id)
                                      .group_by(TokenUsageEvent.agent_name).all())
        ]
        counts = dict(session.query(ConversationMessage.conversation_id, func.count(ConversationMessage.id))
                      .filter(ConversationMessage.user_id == member.user_id)
                      .group_by(ConversationMessage.conversation_id).all())
        conversations = [
            {"id": c.id, "agent_id": c.agent_id, "title": c.title, "messages": counts.get(c.id, 0),
             "updated_at": c.updated_at.isoformat() if c.updated_at else None}
            for c in (session.query(Conversation).filter(Conversation.user_id == member.user_id, Conversation.deleted_at.is_(None))
                      .order_by(Conversation.updated_at.desc()).limit(200).all())
        ]
        _log(session, org_id, admin_id, member.user_id, "profile")
        session.commit()
        identity = {
            "member_id": member.id, "user_id": user.id, "name": user.name, "email": user.email,
            "mobile": user.mobile or "", "external_id": member.external_id,
            "department": member.department, "year": member.year, "section": member.section,
            "joined_at": member.created_at.isoformat() if member.created_at else None,
        }
        user_id = member.user_id
    finally:
        session.close()
    snapshot = readiness_service.latest(user_id)
    plan = coach_service.get(user_id)
    return {
        "member": identity,
        "profile": learner_service.get_profile(user_id),
        "levels": list(learner_service.get_levels(user_id).values()),
        "role_history": learner_service.role_history(user_id),
        "readiness": None if snapshot is None else {
            "overall": snapshot.overall, "band": snapshot.band,
            "band_label": readiness_service.BAND_LABELS.get(snapshot.band, snapshot.band),
            "computed_at": snapshot.computed_at.isoformat(),
            "areas": readiness_service.area_scores(snapshot),
            "next_steps": (snapshot.areas or {}).get("next_steps") or [],
        },
        "readiness_history": readiness_service.history(user_id),
        "activity": sorted(activity, key=lambda a: -a["requests"]),
        "conversations": conversations,
        "memories": [{"text": m["text"], "kind": m.get("kind"), "created_at": m.get("created_at")}
                     for m in memory_service.list_for(user_id)][:50],
        "career_plan": {"headline": plan.get("headline"), "summary": plan.get("summary")} if plan else None,
    }


def member_conversation(admin_id: str, org_id: str, member_id: str, conversation_id: str) -> dict:
    session = db.get_session()
    try:
        member = _shared_member(session, admin_id, org_id, member_id)
        conversation = session.get(Conversation, (conversation_id, member.user_id))
        if conversation is None or conversation.deleted_at is not None:
            raise OrgError(404, "No such chat for this learner.")
        messages = (session.query(ConversationMessage)
                    .filter_by(conversation_id=conversation_id, user_id=member.user_id)
                    .order_by(ConversationMessage.position).limit(MESSAGE_LIMIT).all())
        _log(session, org_id, admin_id, member.user_id, "conversation", conversation.title or conversation_id)
        session.commit()
        return {
            "id": conversation.id, "agent_id": conversation.agent_id, "title": conversation.title,
            "messages": [{"role": m.role, "content": m.content, "time": m.display_time,
                          "created_at": m.created_at.isoformat() if m.created_at else None} for m in messages],
        }
    finally:
        session.close()


def _log_rows(session, query) -> list[dict]:
    rows = query.order_by(OrgAccessLog.created_at.desc()).limit(200).all()
    names = dict(session.query(User.id, User.name).filter(
        User.id.in_({r.viewer_id for r in rows} | {r.subject_user_id for r in rows})).all()) if rows else {}
    return [{
        "viewer": names.get(r.viewer_id, "DigiDARA admin"), "subject": names.get(r.subject_user_id, ""),
        "action": r.action, "target": r.target, "at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]


def access_log(admin_id: str, org_id: str) -> list[dict]:
    session = db.get_session()
    try:
        _require_admin(session, admin_id, org_id)
        return _log_rows(session, session.query(OrgAccessLog).filter_by(organization_id=org_id))
    finally:
        session.close()


def my_access_log(user_id: str) -> list[dict]:
    """A learner's own view: who in their organization opened their details or chats."""
    session = db.get_session()
    try:
        return _log_rows(session, session.query(OrgAccessLog).filter_by(subject_user_id=user_id))
    finally:
        session.close()

"""Shared learner memory: what every agent should know about this learner.

Three writers: the learner (Profile > Memory), the readiness service (each
agent's current strengths and gaps, replaced on every check so they stay
true), and agents themselves over A2A (`remember`). One reader per agent call:
`for_agent` picks the few most relevant memories -- the ones for everyone
plus that agent's own -- pinned and important first.
"""
from __future__ import annotations

from datetime import datetime

from app import db
from app.models import LearnerMemory

KINDS = ("goal", "preference", "strength", "gap", "milestone", "note")
MAX_TEXT = 500
MAX_PER_USER = 200
CONTEXT_LIMIT = 8
READINESS_SOURCE = "readiness"


class MemoryInputError(ValueError):
    pass


def _clean(text: str) -> str:
    return " ".join(str(text or "").split())[:MAX_TEXT]


def _dict(row: LearnerMemory) -> dict:
    return {
        "id": row.id, "kind": row.kind, "text": row.text, "source": row.source,
        "agent_name": row.agent_name, "importance": row.importance, "pinned": bool(row.pinned),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _trim(session, user_id: str) -> None:
    """Keep at most MAX_PER_USER: the least important, oldest unpinned go first."""
    count = session.query(LearnerMemory).filter_by(user_id=user_id).count()
    if count <= MAX_PER_USER:
        return
    extra = (
        session.query(LearnerMemory).filter_by(user_id=user_id, pinned=False)
        .order_by(LearnerMemory.importance.asc(), LearnerMemory.updated_at.asc())
        .limit(count - MAX_PER_USER).all()
    )
    for row in extra:
        session.delete(row)


def add(user_id: str, text: str, kind: str = "note", source: str = "user",
        agent_name: str | None = None, importance: int = 3, pinned: bool = False) -> dict:
    text = _clean(text)
    if len(text) < 2:
        raise MemoryInputError("Write something to remember.")
    kind = kind if kind in KINDS else "note"
    importance = min(5, max(1, int(importance)))
    session = db.get_session()
    try:
        existing = (
            session.query(LearnerMemory)
            .filter_by(user_id=user_id, source=source, agent_name=agent_name, text=text).first()
        )
        if existing is not None:
            existing.updated_at = datetime.utcnow()
            existing.importance = max(existing.importance, importance)
            existing.pinned = existing.pinned or pinned
            row = existing
        else:
            row = LearnerMemory(user_id=user_id, kind=kind, text=text, source=source,
                                agent_name=agent_name, importance=importance, pinned=pinned)
            session.add(row)
        session.flush()
        _trim(session, user_id)
        session.commit()
        session.refresh(row)
        return _dict(row)
    finally:
        session.close()


def list_for(user_id: str) -> list[dict]:
    session = db.get_session()
    try:
        rows = (
            session.query(LearnerMemory).filter_by(user_id=user_id)
            .order_by(LearnerMemory.pinned.desc(), LearnerMemory.updated_at.desc()).all()
        )
        return [_dict(row) for row in rows]
    finally:
        session.close()


def for_agent(user_id: str, agent_name: str, limit: int = CONTEXT_LIMIT) -> list[dict]:
    """The memories one agent receives: shared ones plus its own."""
    session = db.get_session()
    try:
        rows = (
            session.query(LearnerMemory)
            .filter(LearnerMemory.user_id == user_id)
            .filter((LearnerMemory.agent_name.is_(None)) | (LearnerMemory.agent_name == agent_name))
            .order_by(LearnerMemory.pinned.desc(), LearnerMemory.importance.desc(), LearnerMemory.updated_at.desc())
            .limit(limit).all()
        )
        return [{"kind": row.kind, "text": row.text, "source": row.source} for row in rows]
    finally:
        session.close()


def set_pinned(user_id: str, memory_id: str, pinned: bool) -> dict:
    session = db.get_session()
    try:
        row = session.get(LearnerMemory, memory_id)
        if row is None or row.user_id != user_id:
            raise MemoryInputError("No such memory.")
        row.pinned = pinned
        session.commit()
        session.refresh(row)
        return _dict(row)
    finally:
        session.close()


def forget(user_id: str, memory_id: str, source: str | None = None) -> bool:
    """Delete one memory. An agent (source given) may only delete its own."""
    session = db.get_session()
    try:
        row = session.get(LearnerMemory, memory_id)
        if row is None or row.user_id != user_id or (source is not None and row.source != source):
            return False
        session.delete(row)
        session.commit()
        return True
    finally:
        session.close()


def sync_readiness(user_id: str, areas: list[dict]) -> None:
    """Replace each assessed agent's readiness strengths and gaps, so the
    memory every agent sees reflects the latest check, not an old one."""
    session = db.get_session()
    try:
        for area in areas:
            if area.get("status") != "assessed":
                continue
            agent = area["agent_name"]
            session.query(LearnerMemory).filter_by(user_id=user_id, source=READINESS_SOURCE, agent_name=agent).delete()
            label = area.get("label") or agent
            for text in area.get("strengths") or []:
                session.add(LearnerMemory(user_id=user_id, kind="strength", text=_clean(f"{label}: {text}"),
                                          source=READINESS_SOURCE, agent_name=agent, importance=3))
            for text in area.get("gaps") or []:
                session.add(LearnerMemory(user_id=user_id, kind="gap", text=_clean(f"{label}: {text}"),
                                          source=READINESS_SOURCE, agent_name=agent, importance=4))
        session.flush()
        _trim(session, user_id)
        session.commit()
    finally:
        session.close()


def clear(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(LearnerMemory).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()


def skill(action: str, payload: dict, user_id: str, caller: str) -> dict:
    """The memory pseudo-agent's A2A skills, for agents to call."""
    if action == "recall":
        agent = str(payload.get("agent_name") or caller)
        return {"memories": for_agent(user_id, agent, min(50, int(payload.get("limit") or CONTEXT_LIMIT)))}
    if action == "remember":
        # An agent's memory is for itself unless it says scope "all".
        scope = None if payload.get("scope") == "all" else (caller if caller != "user" else None)
        source = caller if caller != "user" else "user"
        return {"memory": add(user_id, payload.get("text", ""), payload.get("kind", "note"), source,
                              scope, int(payload.get("importance") or 3))}
    if action == "forget":
        return {"deleted": forget(user_id, str(payload.get("id") or ""), None if caller == "user" else caller)}
    from app.a2a.protocol import INVALID_PARAMS, RpcError

    raise RpcError(INVALID_PARAMS, f"Unknown memory skill {action!r}. Use recall, remember or forget.")

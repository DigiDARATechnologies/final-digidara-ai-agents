"""Per-chat agent flow state, stored server-side instead of browser storage.

One row per (user, agent, chat): a learner's progress in one conversation with
one agent (a Capstone project, an Aptitude test in progress, a resume draft...).
Rows are small and independent, so saving one chat never touches another.
"""
import json
from datetime import datetime


from app.db import get_session
from app.models import AgentChatState

ALLOWED_AGENT_IDS = {
    "capstone", "codeforge", "aptitude", "communication", "resume_builder", "certificate", "job_fetch",
}
MAX_STATE_BYTES = 1_000_000
MAX_CHATS_PER_AGENT = 200


class StateRejected(ValueError):
    """The state cannot be stored; the message is safe to show the client."""


def _to_dict(row: AgentChatState) -> dict:
    return {
        "agentId": row.agent_id,
        "chatId": row.chat_id,
        "state": row.state,
        "updatedAt": row.updated_at.isoformat() + "Z",
    }


def get_all(user_id: str) -> list[dict]:
    session = get_session()
    try:
        rows = session.query(AgentChatState).filter_by(user_id=user_id).order_by(AgentChatState.updated_at.desc()).all()
        return [_to_dict(row) for row in rows]
    finally:
        session.close()


def put_state(user_id: str, agent_id: str, chat_id: str, state: dict) -> dict:
    if agent_id not in ALLOWED_AGENT_IDS:
        raise StateRejected("Unknown agent.")
    if not chat_id or len(chat_id) > 128:
        raise StateRejected("Invalid chat id.")
    if len(json.dumps(state, ensure_ascii=False).encode("utf-8")) > MAX_STATE_BYTES:
        raise StateRejected("This chat's saved state is too large.")
    session = get_session()
    try:
        row = session.get(AgentChatState, (user_id, agent_id, chat_id))
        now = datetime.utcnow()
        if row is None:
            count = session.query(AgentChatState).filter_by(user_id=user_id, agent_id=agent_id).count()
            if count >= MAX_CHATS_PER_AGENT:
                raise StateRejected("Too many saved chats for this agent. Delete some and try again.")
            row = AgentChatState(user_id=user_id, agent_id=agent_id, chat_id=chat_id, state=state, updated_at=now)
            session.add(row)
        else:
            row.state = state
            row.updated_at = now
        try:
            session.commit()
        except Exception:
            # Two saves of the same new chat can race; the loser just updates.
            session.rollback()
            row = session.get(AgentChatState, (user_id, agent_id, chat_id))
            if row is None:
                raise
            row.state = state
            row.updated_at = now
            session.commit()
        return _to_dict(row)
    finally:
        session.close()


def delete_state(user_id: str, agent_id: str, chat_id: str) -> None:
    session = get_session()
    try:
        session.query(AgentChatState).filter_by(user_id=user_id, agent_id=agent_id, chat_id=chat_id).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


def delete_for_chats(user_id: str, chat_ids: list[str]) -> None:
    """A deleted conversation takes its saved agent state with it."""
    if not chat_ids:
        return
    session = get_session()
    try:
        session.query(AgentChatState).filter(
            AgentChatState.user_id == user_id, AgentChatState.chat_id.in_(chat_ids),
        ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


def purge_state(user_id: str) -> None:
    session = get_session()
    try:
        session.query(AgentChatState).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

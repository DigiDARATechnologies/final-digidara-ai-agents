import time
from datetime import datetime

from app.db import get_session
from app.models import ChatHistoryState, Conversation, ConversationMessage


def _messages_by_conversation(session, user_id: str) -> dict[str, list[ConversationMessage]]:
    rows = (
        session.query(ConversationMessage)
        .filter_by(user_id=user_id)
        .order_by(ConversationMessage.conversation_id, ConversationMessage.position)
        .all()
    )
    grouped: dict[str, list[ConversationMessage]] = {}
    for row in rows:
        grouped.setdefault(row.conversation_id, []).append(row)
    return grouped


def _to_chat(row: Conversation, messages: list[ConversationMessage]) -> dict:
    chat_messages = []
    for message in messages:
        payload = dict(message.message_metadata or {})
        payload.update({
            "role": message.role,
            "text": message.content,
            "time": message.display_time,
        })
        chat_messages.append(payload)
    chat = {
        "id": row.id,
        "agentId": row.agent_id,
        "title": row.title,
        "messages": chat_messages,
        "updatedAt": row.updated_at_ms,
    }
    if row.pinned:
        chat["pinned"] = True
    return chat


def get_history(user_id: str) -> tuple[list[dict], bool]:
    session = get_session()
    try:
        initialized = session.get(ChatHistoryState, user_id) is not None
        rows = (
            session.query(Conversation)
            .filter_by(user_id=user_id, deleted_at=None)
            .order_by(Conversation.updated_at_ms.desc())
            .all()
        )
        messages = _messages_by_conversation(session, user_id)
        return [_to_chat(row, messages.get(row.id, [])) for row in rows], initialized
    finally:
        session.close()


def sync_history(user_id: str, chats: list[dict], deleted_ids: list[str]) -> list[dict]:
    session = get_session()
    try:
        state = session.get(ChatHistoryState, user_id)
        if state is None:
            session.add(ChatHistoryState(user_id=user_id))
        else:
            state.updated_at = datetime.utcnow()

        existing = {
            row.id: row
            for row in session.query(Conversation).filter_by(user_id=user_id).all()
        }

        for chat in chats:
            chat_id = chat["id"]
            incoming_updated_at = int(chat["updatedAt"])
            row = existing.get(chat_id)
            if row is not None and incoming_updated_at < row.updated_at_ms:
                continue
            if row is None:
                row = Conversation(
                    id=chat_id,
                    user_id=user_id,
                    agent_id=chat["agentId"],
                    title=chat["title"],
                    pinned=bool(chat.get("pinned", False)),
                    updated_at_ms=incoming_updated_at,
                )
                session.add(row)
                existing[chat_id] = row
            else:
                row.agent_id = chat["agentId"]
                row.title = chat["title"]
                row.pinned = bool(chat.get("pinned", False))
                row.updated_at = datetime.utcnow()
                row.updated_at_ms = incoming_updated_at
                row.version += 1
                row.deleted_at = None
                session.query(ConversationMessage).filter_by(
                    conversation_id=chat_id,
                    user_id=user_id,
                ).delete(synchronize_session=False)

            for position, message in enumerate(chat["messages"]):
                metadata = {
                    key: value
                    for key, value in message.items()
                    if key not in {"role", "text", "time"}
                }
                session.add(ConversationMessage(
                    conversation_id=chat_id,
                    user_id=user_id,
                    position=position,
                    role=message["role"],
                    content=message["text"],
                    display_time=message["time"],
                    message_metadata=metadata,
                ))

        deleted_at = datetime.utcnow()
        deleted_at_ms = int(time.time() * 1000)
        for chat_id in set(deleted_ids):
            row = existing.get(chat_id)
            if row is None:
                continue
            row.deleted_at = deleted_at
            row.updated_at = deleted_at
            row.updated_at_ms = max(deleted_at_ms, row.updated_at_ms + 1)
            row.version += 1
            session.query(ConversationMessage).filter_by(
                conversation_id=chat_id,
                user_id=user_id,
            ).delete(synchronize_session=False)

        session.commit()
    finally:
        session.close()
    return get_history(user_id)[0]


def purge_history(user_id: str) -> None:
    session = get_session()
    try:
        session.query(ConversationMessage).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.query(Conversation).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.query(ChatHistoryState).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

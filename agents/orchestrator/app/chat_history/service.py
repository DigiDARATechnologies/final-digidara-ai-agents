import logging
import time
from datetime import datetime

from sqlalchemy.exc import IntegrityError, OperationalError

from app.db import get_session
from app.models import ChatHistoryState, Conversation, ConversationArchive, ConversationMessage

# MySQL error codes for "Deadlock found when trying to get lock" and "Lock wait timeout
# exceeded". Two overlapping /chats/sync requests for the same user (a debounced save
# firing twice, two open tabs) each delete-then-insert a conversation's messages; if they
# touch the same rows in a different order, InnoDB picks one to kill. The transaction is
# simply retried from scratch -- neither side did anything wrong.
_DEADLOCK_ERRNOS = {1205, 1213}
_MAX_ATTEMPTS = 3
# A learner deletes chats one at a time; clearing all of them says so (clear_all).
# More in one sync than this is an out-of-date browser working out "deleted" from
# a partial list, not a learner's choice, so it is ignored.
MAX_DELETES_PER_SYNC = 5

logger = logging.getLogger(__name__)


def _is_retryable_deadlock(exc: OperationalError) -> bool:
    orig_args = getattr(getattr(exc, "orig", None), "args", None)
    return bool(orig_args) and orig_args[0] in _DEADLOCK_ERRNOS


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


def _said(messages: list) -> list[tuple[str, str]]:
    """What a list of messages says (role and text), to compare two copies."""
    return [(m.role, m.content) if isinstance(m, ConversationMessage) else (m.get("role"), m.get("text")) for m in messages]


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


def _archive(session, user_id: str, chat_id: str, title: str, stored: list[ConversationMessage]) -> None:
    """Keeps a chat's messages before they are replaced or removed."""
    session.add(ConversationArchive(
        user_id=user_id, conversation_id=chat_id, title=title,
        messages=[{**(m.message_metadata or {}), "role": m.role, "text": m.content,
                   "time": m.display_time} for m in stored],
    ))


def sync_history(user_id: str, chats: list[dict], deleted_ids: list[str], *, clear_all: bool = False, _attempt: int = 1) -> list[dict]:
    if len(set(deleted_ids)) > MAX_DELETES_PER_SYNC and not clear_all:
        logger.warning("chat sync: ignored %d deletions in one sync user=%s", len(set(deleted_ids)), user_id)
        deleted_ids = []
    session = get_session()
    should_retry = False
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
        stored_messages = _messages_by_conversation(session, user_id)

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
                stored = stored_messages.get(chat_id, [])
                stored_said, incoming_said = _said(stored), _said(chat["messages"])
                # Every save sends every chat: an unchanged one is not written
                # again (rewriting them all made saves slow and collide).
                if incoming_updated_at == row.updated_at_ms and row.deleted_at is None and stored_said == incoming_said:
                    continue
                row.agent_id = chat["agentId"]
                row.title = chat["title"]
                row.pinned = bool(chat.get("pinned", False))
                row.updated_at = datetime.utcnow()
                row.updated_at_ms = incoming_updated_at
                row.version += 1
                row.deleted_at = None
                if len(incoming_said) < len(stored_said) and stored_said[:len(incoming_said)] == incoming_said:
                    # An older copy of this chat (another tab or device, or one
                    # saved before a failed sync): it never cuts off the newer
                    # messages the server already has.
                    continue
                if stored_said[:len(stored_said)] != incoming_said[:len(stored_said)]:
                    # A rewrite (an edited message): the replaced messages are
                    # archived, never lost.
                    _archive(session, user_id, chat_id, row.title, stored)
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
            # Kept, so a chat removed by mistake can still be brought back.
            if stored_messages.get(chat_id):
                _archive(session, user_id, chat_id, row.title, stored_messages[chat_id])
            row.deleted_at = deleted_at
            row.updated_at = deleted_at
            row.updated_at_ms = max(deleted_at_ms, row.updated_at_ms + 1)
            row.version += 1
            session.query(ConversationMessage).filter_by(
                conversation_id=chat_id,
                user_id=user_id,
            ).delete(synchronize_session=False)

        session.commit()
    except OperationalError as exc:
        session.rollback()
        if _attempt < _MAX_ATTEMPTS and _is_retryable_deadlock(exc):
            should_retry = True
        else:
            raise
    except IntegrityError:
        # Two overlapping syncs both found a new chat missing and both inserted
        # it (or the same message positions): the slower one hit the duplicate
        # key and used to fail with a 500. Run it again: it now sees the rows
        # the other one wrote and updates them instead.
        session.rollback()
        if _attempt < _MAX_ATTEMPTS:
            should_retry = True
        else:
            raise
    finally:
        session.close()
    if should_retry:
        return sync_history(user_id, chats, deleted_ids, clear_all=clear_all, _attempt=_attempt + 1)
    return get_history(user_id)[0]


def purge_history(user_id: str) -> None:
    session = get_session()
    try:
        session.query(ConversationMessage).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.query(ConversationArchive).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.query(Conversation).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.query(ChatHistoryState).filter_by(user_id=user_id).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()

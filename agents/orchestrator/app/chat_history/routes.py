import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, field_validator

from app.auth.security import get_current_user_id
from app.agent_state import service as agent_state_service
from app.chat_history import service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chats", tags=["chat-history"])


MAX_CHATS = 5000
MAX_MESSAGES = 10_000
MAX_HISTORY_BYTES = 25_000_000
ROLES = {"user", "agent"}


def _clean_message(message: Any) -> dict[str, Any] | None:
    """A message as stored: role, text and time always present. Fields an
    older or buggy client left out are filled in, never a reason to refuse
    the whole history."""
    if not isinstance(message, dict):
        return None
    text = message.get("text")
    if not isinstance(text, str):
        text = "" if text is None else json.dumps(text, ensure_ascii=False) if isinstance(text, (dict, list)) else str(text)
    time = message.get("time")
    return {
        **message,
        "role": message.get("role") if message.get("role") in ROLES else "agent",
        "text": text,
        "time": time[:32] if isinstance(time, str) else "",
    }


def _clean_chat(chat: Any) -> dict[str, Any] | None:
    """None only for a chat that cannot be stored at all (no usable id)."""
    if not isinstance(chat, dict):
        return None
    chat_id = chat.get("id")
    if not isinstance(chat_id, str) or not chat_id or len(chat_id) > 128:
        return None
    agent_id = chat.get("agentId")
    title = chat.get("title")
    updated_at = chat.get("updatedAt")
    messages = chat.get("messages") if isinstance(chat.get("messages"), list) else []
    return {
        **chat,
        "agentId": agent_id[:128] if isinstance(agent_id, str) and agent_id else "general",
        "title": title[:500] if isinstance(title, str) else "",
        "updatedAt": updated_at if isinstance(updated_at, (int, float)) and not isinstance(updated_at, bool) else 0,
        "messages": [m for m in (_clean_message(m) for m in messages[-MAX_MESSAGES:]) if m is not None],
    }


class ChatHistorySync(BaseModel):
    chats: list[Any] = Field(max_length=MAX_CHATS)
    deleted_ids: list[Any] = Field(default_factory=list, max_length=MAX_CHATS)
    # The learner chose "clear all history": only then may many chats go at once.
    clear_all: bool = False
    # Chats the learner edited: only these may end up shorter than the server's copy.
    rewrites: list[str] = Field(default_factory=list, max_length=MAX_CHATS)

    @field_validator("chats")
    @classmethod
    def validate_chats(cls, chats: list[Any]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for raw in chats:
            chat = _clean_chat(raw)
            if chat is None:
                logger.warning("chat sync: skipped a chat without a usable id")
                continue
            # The same chat twice: keep its newest copy.
            if chat["id"] not in by_id or chat["updatedAt"] >= by_id[chat["id"]]["updatedAt"]:
                by_id[chat["id"]] = chat
        cleaned = list(by_id.values())
        if len(json.dumps(cleaned, ensure_ascii=False)) > MAX_HISTORY_BYTES:
            raise ValueError("Chat history is too large.")
        return cleaned

    @field_validator("deleted_ids")
    @classmethod
    def validate_deleted_ids(cls, deleted_ids: list[Any]) -> list[str]:
        return [chat_id for chat_id in deleted_ids if isinstance(chat_id, str) and 0 < len(chat_id) <= 128]


@router.get("")
def get_chat_history(response: Response, user_id: str = Depends(get_current_user_id)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    chats, initialized = service.get_history(user_id)
    return {"chats": chats, "initialized": initialized}


@router.put("/sync")
def sync_chat_history(
    request: ChatHistorySync,
    response: Response,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    chats = service.sync_history(user_id, request.chats, request.deleted_ids, clear_all=request.clear_all, rewrites=set(request.rewrites))
    agent_state_service.delete_for_chats(user_id, request.deleted_ids)
    return {"chats": chats, "initialized": True}

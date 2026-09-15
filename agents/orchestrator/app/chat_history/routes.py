import json
from typing import Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, field_validator

from app.auth.security import get_current_user_id
from app.chat_history import service

router = APIRouter(prefix="/chats", tags=["chat-history"])


class ChatHistorySync(BaseModel):
    chats: list[dict[str, Any]] = Field(max_length=500)
    deleted_ids: list[str] = Field(default_factory=list, max_length=500)

    @field_validator("chats")
    @classmethod
    def validate_chats(cls, chats: list[dict[str, Any]]) -> list[dict[str, Any]]:
        required = {"id", "agentId", "title", "messages", "updatedAt"}
        ids: set[str] = set()
        for chat in chats:
            if not required.issubset(chat):
                raise ValueError("Each chat must include id, agentId, title, messages, and updatedAt.")
            if not isinstance(chat["id"], str) or not chat["id"] or len(chat["id"]) > 128:
                raise ValueError("Each chat must have a valid id.")
            if chat["id"] in ids:
                raise ValueError("Chat ids must be unique.")
            ids.add(chat["id"])
            if not isinstance(chat["agentId"], str) or len(chat["agentId"]) > 128:
                raise ValueError("Each chat must have a valid agentId.")
            if not isinstance(chat["title"], str) or len(chat["title"]) > 500:
                raise ValueError("Each chat must have a valid title.")
            if not isinstance(chat["updatedAt"], (int, float)):
                raise ValueError("Each chat must have a valid updatedAt timestamp.")
            if not isinstance(chat["messages"], list) or len(chat["messages"]) > 2000:
                raise ValueError("Each chat must contain a valid messages list.")
            for message in chat["messages"]:
                if not isinstance(message, dict) or not {"role", "text", "time"}.issubset(message):
                    raise ValueError("Each message must include role, text, and time.")
                if message["role"] not in {"user", "agent"} or not isinstance(message["text"], str):
                    raise ValueError("Each message must have a valid role and text.")
        if len(json.dumps(chats, ensure_ascii=False)) > 10_000_000:
            raise ValueError("Chat history is too large.")
        return chats

    @field_validator("deleted_ids")
    @classmethod
    def validate_deleted_ids(cls, deleted_ids: list[str]) -> list[str]:
        if any(not chat_id or len(chat_id) > 128 for chat_id in deleted_ids):
            raise ValueError("Deleted chat ids must be valid.")
        return deleted_ids


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
    chats = service.sync_history(user_id, request.chats, request.deleted_ids)
    return {"chats": chats, "initialized": True}

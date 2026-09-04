from pydantic import BaseModel
from typing import Optional


class StartChatRequest(BaseModel):
    topic: Optional[str] = None


class SendMessageRequest(BaseModel):
    session_id: str
    message: str

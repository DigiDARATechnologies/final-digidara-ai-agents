from pydantic import BaseModel
from typing import Optional


class StartChatRequest(BaseModel):
    topic: Optional[str] = None


class SendMessageRequest(BaseModel):
    session_id: str
    message: str
    # Question the client is answering; lets the server ignore stale answers.
    question_index: Optional[int] = None

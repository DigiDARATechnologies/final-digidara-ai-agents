from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.agent_state import service
from app.auth.security import get_current_user_id
from app.rate_limit import limiter

router = APIRouter(prefix="/agent-state", tags=["agent-state"])

_WRITE_RATE_LIMIT = "240/minute"


class StateBody(BaseModel):
    state: dict[str, Any]


@router.get("")
def get_agent_state(response: Response, user_id: str = Depends(get_current_user_id)) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return {"states": service.get_all(user_id)}


@router.put("/{agent_id}/{chat_id}")
@limiter.limit(_WRITE_RATE_LIMIT)
def put_agent_state(
    agent_id: str, chat_id: str, body: StateBody, request: Request, response: Response,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    try:
        return service.put_state(user_id, agent_id, chat_id, body.state)
    except service.StateRejected as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.delete("/{agent_id}/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_WRITE_RATE_LIMIT)
def delete_agent_state(
    agent_id: str, chat_id: str, request: Request, user_id: str = Depends(get_current_user_id),
) -> None:
    service.delete_state(user_id, agent_id, chat_id)

"""POST /conductor/interpret: what did the learner mean at this step?"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth.verified import get_verified_user_id
from app.conductor import service
from app.rate_limit import limiter

router = APIRouter(prefix="/conductor", tags=["conductor"])


class ChoiceIn(BaseModel):
    value: str = Field(max_length=200)
    label: str = Field(default="", max_length=300)


class InterpretIn(BaseModel):
    agent_name: str = Field(max_length=64)
    step: str = Field(default="", max_length=60)
    options: list[ChoiceIn] = Field(default_factory=list, max_length=service.MAX_OPTIONS)
    message: str = Field(min_length=1, max_length=500)


# One short LLM turn, only when a learner types at a choice step.
@router.post("/interpret")
@limiter.limit("40/minute")
async def interpret(req: InterpretIn, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    options = [option.model_dump() for option in req.options]
    return await service.interpret(user_id, req.agent_name, req.step, options, req.message)

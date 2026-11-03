"""Boss's briefing for the monitoring accounts. Under /platform-admin/ because
that is already served, but every call is checked for a monitoring account,
which need not be an admin."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.security import get_current_user_id
from app.monitoring import service

router = APIRouter(prefix="/platform-admin/monitoring", tags=["monitoring"])


class Seen(BaseModel):
    as_of: str = Field(max_length=40)


@router.get("/briefing")
def get_briefing(recent: bool = False, user_id: str = Depends(get_current_user_id)) -> dict:
    return service.briefing(user_id, recent=recent)


@router.post("/seen")
def post_seen(request: Seen, user_id: str = Depends(get_current_user_id)) -> dict:
    try:
        service.mark_seen(user_id, request.as_of)
    except ValueError as exc:
        raise HTTPException(400, "as_of must be a time.") from exc
    return {"ok": True}

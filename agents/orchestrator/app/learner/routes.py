"""Learner profile, levels, consent and job readiness (Phase 2)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.auth import service as auth_service
from app.auth.consent import CONSENT_POLICY_VERSION
from app.auth.security import get_current_user_id
from app.auth.verified import get_verified_user_id
from app.learner import levels as level_rules
from app.learner import service
from app.models import User
from app.organizations import service as org_service
from app.readiness import service as readiness_service

router = APIRouter(prefix="/learner", tags=["learner"])


class ProfileIn(BaseModel):
    target_role: str = Field(min_length=2, max_length=200)
    degree: str = Field(default="", max_length=200)
    skills: list[str] = Field(default_factory=list, max_length=60)
    experience: str = "fresher"


class LevelIn(BaseModel):
    level: str


class ConsentIn(BaseModel):
    consent: bool
    share_progress: bool | None = None


def _summary(user_id: str) -> dict:
    user = auth_service.get_by_id(user_id)
    if user is None:
        raise HTTPException(401, "This account no longer exists.")
    return {
        "profile": service.get_profile(user_id),
        "levels": list(service.get_levels(user_id).values()),
        "level_choices": [{"id": level, "label": level_rules.LEVEL_LABELS[level]} for level in level_rules.LEVELS],
        "consent_required": user.consent_accepted_at is None,
        "membership": org_service.my_organization(user_id),
    }


@router.get("/profile")
def get_profile(user_id: str = Depends(get_current_user_id)) -> dict:
    """Readable before email verification, so onboarding can show it."""
    return _summary(user_id)


@router.put("/profile")
def save_profile(req: ProfileIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    service.save_profile(user_id, req.target_role, req.degree, req.skills, req.experience)
    return _summary(user_id)


@router.put("/levels/{agent_name}")
def set_level(agent_name: str, req: LevelIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    try:
        return service.set_level(user_id, agent_name, req.level, "self")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/consent")
def accept_consent(req: ConsentIn, user_id: str = Depends(get_current_user_id)) -> dict:
    """For accounts an organization created: the learner's own acceptance of
    the Privacy Policy and Terms, and their choice to share progress."""
    if not req.consent:
        raise HTTPException(400, "You must accept the Privacy Policy and Terms of Service to continue.")
    session = db.get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            raise HTTPException(401, "This account no longer exists.")
        if user.consent_accepted_at is None:
            user.consent_accepted_at = datetime.utcnow()
            user.consent_policy_version = CONSENT_POLICY_VERSION
            session.commit()
    finally:
        session.close()
    if req.share_progress is not None and org_service.my_organization(user_id) is not None:
        org_service.set_sharing(user_id, req.share_progress)
    return _summary(user_id)


@router.get("/readiness")
async def readiness(refresh: bool = False, user_id: str = Depends(get_verified_user_id)) -> dict:
    user = auth_service.get_by_id(user_id)
    return await readiness_service.get(user, refresh=refresh)


@router.get("/readiness/history")
def readiness_history(user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return readiness_service.history(user_id)

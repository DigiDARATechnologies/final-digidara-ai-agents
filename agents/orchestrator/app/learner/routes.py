"""Learner profile, levels, consent and job readiness (Phase 2)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import db
from app.auth import service as auth_service
from app.auth.consent import CONSENT_POLICY_VERSION
from app.auth.security import get_current_user_id
from app.auth.verified import get_verified_user_id
from app.coach import service as coach_service
from app.memory import service as memory_service
from app.rate_limit import limiter
from app.learner import levels as level_rules
from app.learner import service
from app.models import User
from app.organizations import service as org_service
from app.learner import resume_facts as resume_facts_service
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
    current = service.get_levels(user_id).get(agent_name)
    scored = any(name == agent_name for name, _, _ in readiness_service.AREAS)
    if scored and current and req.level in level_rules.LEVELS and level_rules.is_higher(req.level, current["level"]):
        # Moving up needs half of the current level done; moving down is always allowed.
        progress = readiness_service.level_progress(user_id, agent_name, current["level"])
        if progress is None or progress < level_rules.UNLOCK_PROGRESS:
            done = f"you are at {progress:g}%" if progress is not None else "you have not started it yet"
            raise HTTPException(
                409,
                f"Complete {level_rules.UNLOCK_PROGRESS}% of {level_rules.LEVEL_LABELS[current['level']]} in "
                f"{current['agent_label']} to move up ({done}). At 100% you move up automatically.",
            )
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


@router.get("/resume-facts")
async def resume_facts(user_id: str = Depends(get_verified_user_id)) -> dict:
    """What DigiDARA already knows for this learner's resume (see resume_facts)."""
    return await resume_facts_service.gather(auth_service.get_by_id(user_id))


@router.get("/readiness/history")
def readiness_history(user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return readiness_service.history(user_id)


# --- shared memory (what every agent knows about the learner) ---------------

class MemoryIn(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    kind: str = "note"
    pinned: bool = False


class PinIn(BaseModel):
    pinned: bool


@router.get("/memory")
def list_memory(user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return memory_service.list_for(user_id)


@router.post("/memory", status_code=201)
def add_memory(req: MemoryIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    try:
        # The learner's own memories go to every agent and rank above notes.
        return memory_service.add(user_id, req.text, req.kind, "user", None, 4, req.pinned)
    except memory_service.MemoryInputError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/memory/{memory_id}/pin")
def pin_memory(memory_id: str, req: PinIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    try:
        return memory_service.set_pinned(user_id, memory_id, req.pinned)
    except memory_service.MemoryInputError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/memory/{memory_id}", status_code=204)
def delete_memory(memory_id: str, user_id: str = Depends(get_verified_user_id)) -> Response:
    if not memory_service.forget(user_id, memory_id):
        raise HTTPException(404, "No such memory.")
    return Response(status_code=204)


@router.delete("/memory", status_code=204)
def clear_memory(user_id: str = Depends(get_verified_user_id)) -> Response:
    memory_service.clear(user_id)
    return Response(status_code=204)


# --- AI career plan ---------------------------------------------------------

class PlanIn(BaseModel):
    language: str = "en"


@router.get("/plan")
def get_plan(user_id: str = Depends(get_verified_user_id)) -> dict:
    return {"plan": coach_service.get(user_id)}


@router.post("/plan")
@limiter.limit("6/hour")
async def create_plan(req: PlanIn, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    """Readiness over A2A + profile + memory -> an LLM-written plan."""
    user = auth_service.get_by_id(user_id)
    try:
        plan = await coach_service.generate(user, req.language)
    except coach_service.NoPoints as exc:
        raise HTTPException(402, str(exc)) from exc
    except coach_service.PlanError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"plan": plan}

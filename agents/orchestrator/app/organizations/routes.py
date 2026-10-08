"""Organizations API: register, join, manage members, monitor readiness."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.admin.routes import require_admin
from app.auth import service as auth_service
from app.auth.verified import get_verified_user_id
from app.learner import service as learner_service
from app.organizations import service
from app.organizations.service import OrgError
from app.readiness import service as readiness_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


class CreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    kind: str = "college"


class JoinIn(BaseModel):
    join_code: str = Field(min_length=4, max_length=16)
    share_progress: bool = False


class SharingIn(BaseModel):
    share: bool


class MemberIn(BaseModel):
    name: str = Field(default="", max_length=255)
    email: str = Field(min_length=3, max_length=255)
    external_id: str | None = Field(default=None, max_length=64)


class MembersIn(BaseModel):
    members: list[MemberIn] = Field(min_length=1, max_length=service.MAX_BULK)


class MemberUpdateIn(BaseModel):
    role: str | None = None
    external_id: str | None = None


class LevelIn(BaseModel):
    level: str


def _run(fn, *args):
    try:
        return fn(*args)
    except OrgError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


@router.post("", status_code=201)
def create_organization(req: CreateIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.create, user_id, req.name, req.kind)


@router.get("/me")
def my_organization(user_id: str = Depends(get_verified_user_id)) -> dict:
    return {"membership": service.my_organization(user_id)}


@router.post("/join")
def join_organization(req: JoinIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.join, user_id, req.join_code, req.share_progress)


@router.put("/me/sharing")
def set_sharing(req: SharingIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.set_sharing, user_id, req.share)


@router.delete("/me", status_code=204)
def leave_organization(user_id: str = Depends(get_verified_user_id)) -> Response:
    _run(service.leave, user_id)
    return Response(status_code=204)


@router.get("/all")
def all_organizations(_admin: str = Depends(require_admin)) -> list[dict]:
    """Platform admin only."""
    return service.list_all()


@router.get("/{org_id}/summary")
def organization_summary(org_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.summary, user_id, org_id)


@router.get("/{org_id}/members")
def organization_members(org_id: str, user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return _run(service.members, user_id, org_id)


@router.post("/{org_id}/members")
def add_members(org_id: str, req: MembersIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    rows = [member.model_dump() for member in req.members]
    return {"results": _run(service.add_members, user_id, org_id, rows)}


@router.patch("/{org_id}/members/{member_id}", status_code=204)
def update_member(org_id: str, member_id: str, req: MemberUpdateIn, user_id: str = Depends(get_verified_user_id)) -> Response:
    _run(service.update_member, user_id, org_id, member_id, req.role, req.external_id)
    return Response(status_code=204)


@router.delete("/{org_id}/members/{member_id}", status_code=204)
def remove_member(org_id: str, member_id: str, user_id: str = Depends(get_verified_user_id)) -> Response:
    _run(service.remove_member, user_id, org_id, member_id)
    return Response(status_code=204)


@router.put("/{org_id}/members/{member_id}/levels/{agent_name}")
def set_member_level(org_id: str, member_id: str, agent_name: str, req: LevelIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    member_user_id = _run(service.shared_member_user_id, user_id, org_id, member_id)
    try:
        return learner_service.set_level(member_user_id, agent_name, req.level, "organization")
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{org_id}/members/{member_id}/readiness")
async def refresh_member_readiness(org_id: str, member_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    """Recompute one shared member's readiness (asks every agent over A2A)."""
    member_user_id = _run(service.shared_member_user_id, user_id, org_id, member_id)
    member = auth_service.get_by_id(member_user_id)
    if member is None:
        raise HTTPException(404, "This member's account no longer exists.")
    return await readiness_service.get(member, refresh=True)


@router.post("/{org_id}/join-code")
def rotate_join_code(org_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.rotate_join_code, user_id, org_id)

"""Organizations API: created by DigiDARA's platform admin; learners join
with a code; organization admins manage codes and members and see the
analytics and each learner's details (insights.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.admin.routes import require_admin
from app.auth import service as auth_service
from app.auth.verified import get_verified_user_id
from app.learner import service as learner_service
from app.organizations import classes, insights, service
from app.organizations.service import OrgError
from app.rate_limit import limiter
from app.readiness import service as readiness_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


class CreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    kind: str = "college"


class PlatformCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    kind: str = "college"
    admin_name: str = Field(default="", max_length=255)
    admin_email: str = Field(min_length=3, max_length=255)
    member_limit: int = Field(default=1000, ge=1, le=100000)


class PlatformUpdateIn(BaseModel):
    status: str = "active"
    member_limit: int | None = Field(default=None, ge=1, le=100000)


class JoinIn(BaseModel):
    join_code: str = Field(min_length=4, max_length=16)
    # Ignored: joining is consent to share (kept for older clients).
    share_progress: bool = True
    department: str | None = Field(default=None, max_length=120)
    year: str | None = Field(default=None, max_length=40)
    section: str | None = Field(default=None, max_length=40)


class CodeIn(BaseModel):
    label: str = Field(default="", max_length=120)
    department: str | None = Field(default=None, max_length=120)
    year: str | None = Field(default=None, max_length=40)
    section: str | None = Field(default=None, max_length=40)


class CodeUpdateIn(BaseModel):
    active: bool


class OptionIn(BaseModel):
    kind: str
    value: str = Field(min_length=1, max_length=120)


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
    department: str | None = Field(default=None, max_length=120)
    year: str | None = Field(default=None, max_length=40)
    section: str | None = Field(default=None, max_length=40)


class LevelIn(BaseModel):
    level: str


def _run(fn, *args):
    try:
        return fn(*args)
    except OrgError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


def _filters(department: str | None, year: str | None, section: str | None, code_id: str | None, band: str | None,
             agent: str | None, level: str | None, status: str | None, search: str | None) -> dict:
    return {k: v for k, v in {
        "department": department, "year": year, "section": section, "code_id": code_id, "band": band,
        "agent": agent, "level": level, "status": status, "search": search,
    }.items() if v}


@router.post("", status_code=201)
def create_organization(req: CreateIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    raise HTTPException(403, "Organizations are set up by DigiDARA. Contact us to register yours.")


@router.post("/platform", status_code=201)
def platform_create_organization(req: PlatformCreateIn, admin_id: str = Depends(require_admin)) -> dict:
    """Platform admin only: an organization with its first admin login."""
    return _run(service.create_for_platform, req.name, req.kind, req.admin_name, req.admin_email, req.member_limit, admin_id)


@router.patch("/platform/{org_id}")
def platform_update_organization(org_id: str, req: PlatformUpdateIn, _admin: str = Depends(require_admin)) -> dict:
    return _run(service.set_status, org_id, req.status, req.member_limit)


@router.get("/me")
def my_organization(user_id: str = Depends(get_verified_user_id)) -> dict:
    return {"membership": service.my_organization(user_id)}


@router.get("/me/access-log")
def my_access_log(user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    """Who in my organization opened my details or chats."""
    return insights.my_access_log(user_id)


@router.get("/join-code/{code}")
@limiter.limit("20/minute")
def preview_join_code(code: str, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    if not 4 <= len(code) <= 16:
        raise HTTPException(404, "No organization has that join code.")
    return _run(classes.preview, code)


@router.post("/join")
@limiter.limit("10/minute")
def join_organization(req: JoinIn, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.join, user_id, req.join_code, True, req.department, req.year, req.section)


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


@router.get("/{org_id}/analytics")
def organization_analytics(
    org_id: str, department: str | None = None, year: str | None = None, section: str | None = None,
    code_id: str | None = None, band: str | None = None, agent: str | None = None, level: str | None = None,
    status: str | None = None, search: str | None = Query(default=None, max_length=120),
    user_id: str = Depends(get_verified_user_id),
) -> dict:
    return _run(insights.analytics, user_id, org_id, _filters(department, year, section, code_id, band, agent, level, status, search))


@router.get("/{org_id}/members")
def organization_members(
    org_id: str, department: str | None = None, year: str | None = None, section: str | None = None,
    code_id: str | None = None, band: str | None = None, agent: str | None = None, level: str | None = None,
    status: str | None = None, search: str | None = Query(default=None, max_length=120),
    user_id: str = Depends(get_verified_user_id),
) -> list[dict]:
    rows = _run(service.members, user_id, org_id)
    filters = _filters(department, year, section, code_id, band, agent, level, status, search)
    return insights.filter_members(rows, filters) if filters else rows


@router.get("/{org_id}/members/{member_id}/detail")
def member_detail(org_id: str, member_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(insights.member_detail, user_id, org_id, member_id)


@router.get("/{org_id}/members/{member_id}/conversations/{conversation_id}")
def member_conversation(org_id: str, member_id: str, conversation_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(insights.member_conversation, user_id, org_id, member_id, conversation_id)


@router.get("/{org_id}/access-log")
def organization_access_log(org_id: str, user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return _run(insights.access_log, user_id, org_id)


@router.get("/{org_id}/codes")
def list_codes(org_id: str, user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return _run(classes.list_codes, user_id, org_id)


@router.post("/{org_id}/codes", status_code=201)
def create_code(org_id: str, req: CodeIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(classes.create_code, user_id, org_id, req.label, req.department, req.year, req.section)


@router.patch("/{org_id}/codes/{code_id}")
def update_code(org_id: str, code_id: str, req: CodeUpdateIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(classes.set_code_active, user_id, org_id, code_id, req.active)


@router.get("/{org_id}/options")
def list_options(org_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(classes.options, user_id, org_id)


@router.post("/{org_id}/options")
def add_option(org_id: str, req: OptionIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(classes.add_option, user_id, org_id, req.kind, req.value)


@router.post("/{org_id}/members")
def add_members(org_id: str, req: MembersIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    rows = [member.model_dump() for member in req.members]
    return {"results": _run(service.add_members, user_id, org_id, rows)}


@router.patch("/{org_id}/members/{member_id}", status_code=204)
def update_member(org_id: str, member_id: str, req: MemberUpdateIn, user_id: str = Depends(get_verified_user_id)) -> Response:
    class_fields = {k: v for k, v in req.model_dump(include={"department", "year", "section"}).items() if k in req.model_fields_set}
    _run(service.update_member, user_id, org_id, member_id, req.role, req.external_id, class_fields)
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

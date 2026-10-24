"""Proctoring and assessment-link API (see service.py)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth.verified import get_verified_user_id
from app.organizations import service as org_service
from app.organizations.service import OrgError
from app.proctoring import service
from app.proctoring.service import ProctorError
from app.rate_limit import limiter

router = APIRouter(tags=["proctoring"])


class StartIn(BaseModel):
    agent_name: str = Field(max_length=64)
    ref: str = Field(min_length=1, max_length=128)
    consent: bool = False


class EventIn(BaseModel):
    kind: str = Field(max_length=32)
    detail: str = Field(default="", max_length=255)


class EventsIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=service.MAX_EVENTS_PER_CALL)


class SnapshotIn(BaseModel):
    # A base64 JPEG (optionally a data: URL) of at most 200 KB.
    image: str = Field(min_length=10, max_length=300_000)


class ConsentIn(BaseModel):
    consent: bool = False


class AssessmentIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    kind: str = "mock_interview"
    config: dict = Field(default_factory=dict)
    proctoring: dict = Field(default_factory=dict)
    opens_at: str | None = None
    closes_at: str | None = None
    members_only: bool = True


class ActiveIn(BaseModel):
    active: bool


def _run(fn, *args):
    try:
        return fn(*args)
    except (ProctorError, OrgError) as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


# --- the learner ------------------------------------------------------------

@router.post("/proctoring/sessions", status_code=201)
def start_session(req: StartIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    """A Hard/Professional mock interview or capstone viva starts proctoring."""
    return _run(service.start_practice, user_id, req.agent_name, req.ref, req.consent)


@router.get("/proctoring/sessions/{session_id}")
def session_state(session_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.state, user_id, session_id)


@router.post("/proctoring/sessions/{session_id}/events")
@limiter.limit("60/minute")
def add_events(session_id: str, req: EventsIn, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.record_events, user_id, session_id, [event.model_dump() for event in req.events])


@router.post("/proctoring/sessions/{session_id}/snapshots")
@limiter.limit("6/minute")
def add_snapshot(session_id: str, req: SnapshotIn, request: Request, background: BackgroundTasks,
                 user_id: str = Depends(get_verified_user_id)) -> dict:
    state, check_id = _run(service.add_snapshot, user_id, session_id, req.image)
    if check_id:
        background.add_task(service.check_snapshot, check_id)
    return state


@router.post("/proctoring/sessions/{session_id}/end")
def end_session(session_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.end_session, user_id, session_id)


@router.get("/assessments/{token}")
@limiter.limit("30/minute")
def preview_assessment(token: str, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.preview_assessment, user_id, token)


@router.post("/assessments/{token}/start")
@limiter.limit("10/minute")
def start_assessment(token: str, req: ConsentIn, request: Request, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.start_assessment, user_id, token, req.consent)


# --- the organization's admins ------------------------------------------------

@router.get("/organizations/{org_id}/assessments")
def list_assessments(org_id: str, user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return _run(service.list_assessments, user_id, org_id)


@router.post("/organizations/{org_id}/assessments", status_code=201)
def create_assessment(org_id: str, req: AssessmentIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.create_assessment, user_id, org_id, req.model_dump())


@router.patch("/organizations/{org_id}/assessments/{assessment_id}")
def update_assessment(org_id: str, assessment_id: str, req: ActiveIn, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.set_assessment_active, user_id, org_id, assessment_id, req.active)


@router.get("/organizations/{org_id}/assessments/{assessment_id}/attempts")
def assessment_attempts(org_id: str, assessment_id: str, user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    return _run(service.assessment_attempts, user_id, org_id, assessment_id)


@router.get("/organizations/{org_id}/members/{member_id}/proctoring")
def member_sessions(org_id: str, member_id: str, user_id: str = Depends(get_verified_user_id)) -> list[dict]:
    member_user_id = _run(org_service.shared_member_user_id, user_id, org_id, member_id)
    return _run(service.member_sessions, user_id, org_id, member_user_id)


@router.get("/organizations/{org_id}/proctoring/{session_id}")
def session_detail(org_id: str, session_id: str, user_id: str = Depends(get_verified_user_id)) -> dict:
    return _run(service.session_detail, user_id, org_id, session_id)


@router.get("/organizations/{org_id}/proctoring/{session_id}/snapshots/{snapshot_id}")
def snapshot_image(org_id: str, session_id: str, snapshot_id: str, user_id: str = Depends(get_verified_user_id)) -> Response:
    image = _run(service.snapshot_image, user_id, org_id, session_id, snapshot_id)
    return Response(content=image, media_type="image/jpeg", headers={"cache-control": "private, no-store"})

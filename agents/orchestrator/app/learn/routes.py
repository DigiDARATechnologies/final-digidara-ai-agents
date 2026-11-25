"""Learning Hub API (see service.py). Everything is under /courses/hub so the existing
/courses prefix of the nginx proxy covers it.

Learners: GET /courses/hub/catalog, /search?q=, /{course}, /{course}/lessons/{lesson};
          PUT /courses/hub/{course}/lessons/{lesson}/progress.
SkillDARA admin: GET /platform-admin/courses/hub/licenses; PUT .../licenses/{organization_id}.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.auth.security import get_current_user_id
from app.learn import service
from app.learn.service import LearnError

router = APIRouter(tags=["learning-hub"])


class ProgressIn(BaseModel):
    completed: bool = True


class LicenseIn(BaseModel):
    enabled: bool = True


async def _run(fn, *args):
    try:
        return await run_in_threadpool(fn, *args)
    except LearnError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


# The fixed words (catalog, search) come before /{course}, so they are never read as a course name.
@router.get("/courses/hub/catalog")
async def catalog(user_id: str = Depends(get_current_user_id)) -> dict:
    return await _run(service.catalog, user_id)


@router.get("/courses/hub/search")
async def search(q: str = Query(default="", max_length=80), user_id: str = Depends(get_current_user_id)) -> dict:
    return await _run(service.search, user_id, q)


@router.get("/courses/hub/{course}")
async def outline(course: str, user_id: str = Depends(get_current_user_id)) -> dict:
    return await _run(service.course_outline, user_id, course)


@router.get("/courses/hub/{course}/lessons/{lesson}")
async def lesson(course: str, lesson: str, user_id: str = Depends(get_current_user_id)) -> dict:
    return await _run(service.lesson, user_id, course, lesson)


@router.put("/courses/hub/{course}/lessons/{lesson}/progress")
async def progress(course: str, lesson: str, body: ProgressIn, user_id: str = Depends(get_current_user_id)) -> dict:
    return await _run(service.set_done, user_id, course, lesson, body.completed)


@router.get("/platform-admin/courses/hub/licenses")
async def licenses(user_id: str = Depends(get_current_user_id)) -> list[dict]:
    return await _run(service.licenses, user_id)


@router.put("/platform-admin/courses/hub/licenses/{organization_id}")
async def set_license(organization_id: str, body: LicenseIn, user_id: str = Depends(get_current_user_id)) -> dict:
    return await _run(service.set_license, user_id, organization_id, body.enabled)

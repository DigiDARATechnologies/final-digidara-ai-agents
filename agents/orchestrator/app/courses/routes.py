"""Courses API (see service.py).

Learners: GET /courses, GET /courses/{id}, PUT /courses/lessons/{id}/progress.
SkillDARA admin: /platform-admin/courses... (create, edit, upload, delete).
Files: GET /course-media/{signed token} -- no sign-in header, so the link
itself is the permission (it expires after a few hours).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.auth.security import get_current_user_id
from app.courses import service
from app.courses.service import CourseError

router = APIRouter(tags=["courses"])


class CourseIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    category: str = Field(default="", max_length=80)
    level: str = Field(default="", max_length=20)
    published: bool = False
    position: int | None = None


class LessonIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=5000)
    video_url: str = Field(default="", max_length=500)
    position: int | None = None


class ProgressIn(BaseModel):
    completed: bool = True


def _run(fn, *args):
    try:
        return fn(*args)
    except CourseError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc


# --- learners -----------------------------------------------------------------------

@router.get("/courses")
def list_courses(user_id: str = Depends(get_current_user_id)):
    return {"courses": _run(service.list_courses, user_id)}


@router.get("/courses/{course_id}")
def get_course(course_id: str, user_id: str = Depends(get_current_user_id)):
    return _run(service.get_course, user_id, course_id)


@router.put("/courses/lessons/{lesson_id}/progress")
def set_progress(lesson_id: str, body: ProgressIn, user_id: str = Depends(get_current_user_id)):
    return _run(service.set_completed, user_id, lesson_id, body.completed)


@router.get("/course-media/{token}")
def course_media(token: str):
    path, media_type, name = _run(service.media_file, token)
    inline = media_type.startswith("video/") or media_type in ("application/pdf", "text/plain")
    return FileResponse(path, media_type=media_type, filename=name,
                        content_disposition_type="inline" if inline else "attachment",
                        headers={"Cache-Control": "private, max-age=3600"})


# --- SkillDARA admin ----------------------------------------------------------------

@router.get("/platform-admin/courses")
def admin_courses(user_id: str = Depends(get_current_user_id)):
    _run(service.require_admin, user_id)
    service.clean_stale_uploads()
    return {"courses": _run(service.list_courses, user_id, True), "chunk_bytes": service.UPLOAD_CHUNK_BYTES}


@router.get("/platform-admin/courses/{course_id}")
def admin_course(course_id: str, user_id: str = Depends(get_current_user_id)):
    _run(service.require_admin, user_id)
    return _run(service.get_course, user_id, course_id, True)


@router.post("/platform-admin/courses")
def create_course(body: CourseIn, user_id: str = Depends(get_current_user_id)):
    return _run(service.save_course, user_id, body.model_dump())


@router.put("/platform-admin/courses/{course_id}")
def update_course(course_id: str, body: CourseIn, user_id: str = Depends(get_current_user_id)):
    return _run(service.save_course, user_id, body.model_dump(), course_id)


@router.delete("/platform-admin/courses/{course_id}")
def delete_course(course_id: str, user_id: str = Depends(get_current_user_id)):
    _run(service.delete_course, user_id, course_id)
    return {"deleted": course_id}


@router.post("/platform-admin/courses/{course_id}/lessons")
def create_lesson(course_id: str, body: LessonIn, user_id: str = Depends(get_current_user_id)):
    return _run(service.save_lesson, user_id, course_id, body.model_dump())


@router.put("/platform-admin/courses/{course_id}/lessons/{lesson_id}")
def update_lesson(course_id: str, lesson_id: str, body: LessonIn, user_id: str = Depends(get_current_user_id)):
    return _run(service.save_lesson, user_id, course_id, body.model_dump(), lesson_id)


@router.delete("/platform-admin/courses/lessons/{lesson_id}")
def delete_lesson(lesson_id: str, user_id: str = Depends(get_current_user_id)):
    _run(service.delete_lesson, user_id, lesson_id)
    return {"deleted": lesson_id}


@router.delete("/platform-admin/courses/lessons/{lesson_id}/{kind}")
def remove_file(lesson_id: str, kind: str, user_id: str = Depends(get_current_user_id)):
    return _run(service.remove_lesson_file, user_id, lesson_id, kind)


@router.put("/platform-admin/courses/lessons/{lesson_id}/upload")
async def upload_chunk(
    lesson_id: str,
    request: Request,
    kind: str = Query(...),
    upload_id: str = Query(...),
    index: int = Query(..., ge=0),
    total: int = Query(..., ge=1),
    filename: str = Query(..., max_length=255),
    user_id: str = Depends(get_current_user_id),
):
    """One chunk of a file, sent as the raw request body."""
    data = await request.body()
    return await run_in_threadpool(_run, service.upload_chunk, user_id, lesson_id, kind, upload_id, index, total, filename, data)

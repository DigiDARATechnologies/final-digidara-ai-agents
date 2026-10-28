"""Courses: SkillDARA's admin publishes courses for every learner.

A course has lessons; a lesson has a video (an uploaded file, or a YouTube /
Vimeo link) and notes or a handbook (PDF, Word, PowerPoint or text).

Uploads come in chunks (UPLOAD_CHUNK_BYTES each) so a large video passes any
request-size limit in front of the app. Chunks are written to disk under
COURSE_FILES_DIR/tmp/<upload id>/ (all workers share it) and joined when the
last one arrives. Learners get a signed, expiring /course-media/<token> URL
for each file, because a <video> or a link cannot send the sign-in header.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

from app import db
from app.models import Course, CourseLesson, CourseProgress, User

FILES_DIR = Path(os.environ.get("COURSE_FILES_DIR", "").strip() or Path(__file__).resolve().parents[2] / "course_files")
UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024
LIMITS = {"video": 2 * 1024 ** 3, "notes": 100 * 1024 ** 2}
TYPES = {
    "video": {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".m4v": "video/mp4"},
    "notes": {".pdf": "application/pdf",
              ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
              ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
              ".txt": "text/plain"},
}
MEDIA_TTL_SECONDS = 6 * 3600
_VIDEO_LINK = re.compile(r"^https://(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|vimeo\.com/|player\.vimeo\.com/video/)[\w\-?=&/.]+$")
_UPLOAD_ID = re.compile(r"^[a-f0-9]{32}$")


class CourseError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _clean(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _secret() -> bytes:
    from app.auth.security import JWT_SECRET

    return hashlib.sha256(f"course-media:{JWT_SECRET}".encode()).digest()


# --- signed media links ------------------------------------------------------------

def media_token(lesson_id: str, kind: str, now: float | None = None) -> str:
    expires = int((now or time.time()) + MEDIA_TTL_SECONDS)
    body = f"{lesson_id}:{kind}:{expires}"
    signature = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return base64.urlsafe_b64encode(f"{body}:{signature}".encode()).decode().rstrip("=")


def read_media_token(token: str) -> tuple[str, str]:
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
        lesson_id, kind, expires, signature = raw.split(":")
    except (ValueError, UnicodeDecodeError) as exc:
        raise CourseError(404, "This link is not valid.") from exc
    expected = hmac.new(_secret(), f"{lesson_id}:{kind}:{expires}".encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, signature) or kind not in TYPES:
        raise CourseError(404, "This link is not valid.")
    if int(expires) < time.time():
        raise CourseError(410, "This link has expired. Open the lesson again.")
    return lesson_id, kind


def media_file(token: str) -> tuple[Path, str, str]:
    """(path, media type, download name) for a signed media link."""
    lesson_id, kind = read_media_token(token)
    session = db.get_session()
    try:
        lesson = session.get(CourseLesson, lesson_id)
        course = session.get(Course, lesson.course_id) if lesson is not None else None
        if lesson is None or course is None:
            raise CourseError(404, "This lesson no longer exists.")
        stored, name = (lesson.video_file, lesson.video_name) if kind == "video" else (lesson.notes_file, lesson.notes_name)
    finally:
        session.close()
    path = FILES_DIR / "files" / stored if stored else None
    if path is None or not path.is_file():
        raise CourseError(404, "This file is not available.")
    return path, TYPES[kind].get(path.suffix.lower(), "application/octet-stream"), name or path.name


# --- views --------------------------------------------------------------------------

def _lesson_dict(lesson: CourseLesson, *, admin: bool, done: set[str] | None = None) -> dict:
    item = {
        "id": lesson.id, "title": lesson.title, "description": lesson.description, "position": lesson.position,
        "video_url": lesson.video_url or None,
        "has_video": bool(lesson.video_file), "video_name": lesson.video_name, "video_size": lesson.video_size,
        "has_notes": bool(lesson.notes_file), "notes_name": lesson.notes_name, "notes_size": lesson.notes_size,
        "completed": lesson.id in (done or set()),
    }
    if lesson.video_file:
        item["video_src"] = f"/course-media/{media_token(lesson.id, 'video')}"
    if lesson.notes_file:
        item["notes_src"] = f"/course-media/{media_token(lesson.id, 'notes')}"
    return item


def _course_dict(course: Course, lessons: list[CourseLesson], *, admin: bool, done: set[str] | None = None,
                 full: bool = False) -> dict:
    data = {
        "id": course.id, "title": course.title, "description": course.description, "category": course.category,
        "level": course.level, "published": bool(course.published), "position": course.position,
        "lessons": len(lessons), "completed": sum(1 for lesson in lessons if lesson.id in (done or set())),
        "videos": sum(1 for lesson in lessons if lesson.video_file or lesson.video_url),
        "notes": sum(1 for lesson in lessons if lesson.notes_file),
        "updated_at": course.updated_at.isoformat() if course.updated_at else None,
    }
    if full:
        data["lesson_list"] = [_lesson_dict(lesson, admin=admin, done=done) for lesson in lessons]
    return data


def _lessons(session, course_id: str) -> list[CourseLesson]:
    return session.query(CourseLesson).filter_by(course_id=course_id).order_by(CourseLesson.position, CourseLesson.created_at).all()


def _done(session, user_id: str) -> set[str]:
    return {row.lesson_id for row in session.query(CourseProgress.lesson_id).filter_by(user_id=user_id).all()}


def list_courses(user_id: str, admin: bool = False) -> list[dict]:
    session = db.get_session()
    try:
        query = session.query(Course)
        if not admin:
            query = query.filter(Course.published.is_(True))
        done = _done(session, user_id)
        return [_course_dict(course, _lessons(session, course.id), admin=admin, done=done)
                for course in query.order_by(Course.position, Course.created_at.desc()).all()]
    finally:
        session.close()


def get_course(user_id: str, course_id: str, admin: bool = False) -> dict:
    session = db.get_session()
    try:
        course = session.get(Course, course_id)
        if course is None or (not admin and not course.published):
            raise CourseError(404, "No such course.")
        return _course_dict(course, _lessons(session, course.id), admin=admin, done=_done(session, user_id), full=True)
    finally:
        session.close()


def set_completed(user_id: str, lesson_id: str, completed: bool) -> dict:
    session = db.get_session()
    try:
        lesson = session.get(CourseLesson, lesson_id)
        course = session.get(Course, lesson.course_id) if lesson is not None else None
        if course is None or not course.published:
            raise CourseError(404, "No such lesson.")
        row = session.get(CourseProgress, (user_id, lesson_id))
        if completed and row is None:
            session.add(CourseProgress(user_id=user_id, lesson_id=lesson_id))
        elif not completed and row is not None:
            session.delete(row)
        session.commit()
        return {"lesson_id": lesson_id, "completed": completed}
    finally:
        session.close()


# --- admin: courses and lessons -----------------------------------------------------

def require_admin(user_id: str) -> None:
    session = db.get_session()
    try:
        user = session.get(User, user_id)
        if user is None or not user.is_admin:
            raise CourseError(403, "Only SkillDARA's admin can manage courses.")
    finally:
        session.close()


def save_course(admin_id: str, data: dict, course_id: str | None = None) -> dict:
    require_admin(admin_id)
    title = _clean(data.get("title"), 200)
    if len(title) < 3:
        raise CourseError(400, "Give the course a title.")
    session = db.get_session()
    try:
        course = session.get(Course, course_id) if course_id else Course(created_by=admin_id)
        if course is None:
            raise CourseError(404, "No such course.")
        course.title = title
        course.description = str(data.get("description") or "").strip()[:5000]
        course.category = _clean(data.get("category"), 80)
        course.level = _clean(data.get("level"), 20)
        course.published = bool(data.get("published", course.published or False))
        if isinstance(data.get("position"), int):
            course.position = data["position"]
        course.updated_at = datetime.utcnow()
        session.add(course)
        session.commit()
        return _course_dict(course, _lessons(session, course.id), admin=True, full=True)
    finally:
        session.close()


def delete_course(admin_id: str, course_id: str) -> None:
    require_admin(admin_id)
    session = db.get_session()
    try:
        course = session.get(Course, course_id)
        if course is None:
            raise CourseError(404, "No such course.")
        files = [name for lesson in _lessons(session, course_id) for name in (lesson.video_file, lesson.notes_file) if name]
        session.query(CourseLesson).filter_by(course_id=course_id).delete(synchronize_session=False)
        session.delete(course)
        session.commit()
    finally:
        session.close()
    for name in files:
        _remove_file(name)


def save_lesson(admin_id: str, course_id: str, data: dict, lesson_id: str | None = None) -> dict:
    require_admin(admin_id)
    title = _clean(data.get("title"), 200)
    if len(title) < 2:
        raise CourseError(400, "Give the lesson a title.")
    video_url = str(data.get("video_url") or "").strip()[:500]
    if video_url and not _VIDEO_LINK.match(video_url):
        raise CourseError(400, "Use a YouTube or Vimeo link (https://...), or upload the video instead.")
    session = db.get_session()
    try:
        course = session.get(Course, course_id)
        if course is None:
            raise CourseError(404, "No such course.")
        if lesson_id:
            lesson = session.get(CourseLesson, lesson_id)
            if lesson is None or lesson.course_id != course_id:
                raise CourseError(404, "No such lesson.")
        else:
            count = session.query(CourseLesson).filter_by(course_id=course_id).count()
            if count >= 300:
                raise CourseError(409, "A course can have at most 300 lessons.")
            lesson = CourseLesson(course_id=course_id, position=count + 1)
        lesson.title = title
        lesson.description = str(data.get("description") or "").strip()[:5000]
        lesson.video_url = video_url
        if isinstance(data.get("position"), int):
            lesson.position = data["position"]
        session.add(lesson)
        course.updated_at = datetime.utcnow()
        session.commit()
        return _lesson_dict(lesson, admin=True)
    finally:
        session.close()


def delete_lesson(admin_id: str, lesson_id: str) -> None:
    require_admin(admin_id)
    session = db.get_session()
    try:
        lesson = session.get(CourseLesson, lesson_id)
        if lesson is None:
            raise CourseError(404, "No such lesson.")
        files = [name for name in (lesson.video_file, lesson.notes_file) if name]
        session.delete(lesson)
        session.commit()
    finally:
        session.close()
    for name in files:
        _remove_file(name)


def remove_lesson_file(admin_id: str, lesson_id: str, kind: str) -> dict:
    require_admin(admin_id)
    if kind not in TYPES:
        raise CourseError(400, "Choose video or notes.")
    session = db.get_session()
    try:
        lesson = session.get(CourseLesson, lesson_id)
        if lesson is None:
            raise CourseError(404, "No such lesson.")
        old = lesson.video_file if kind == "video" else lesson.notes_file
        if kind == "video":
            lesson.video_file, lesson.video_name, lesson.video_size = "", "", 0
        else:
            lesson.notes_file, lesson.notes_name, lesson.notes_size = "", "", 0
        session.commit()
        result = _lesson_dict(lesson, admin=True)
    finally:
        session.close()
    if old:
        _remove_file(old)
    return result


# --- admin: chunked uploads ---------------------------------------------------------

def _remove_file(name: str) -> None:
    try:
        (FILES_DIR / "files" / Path(name).name).unlink(missing_ok=True)
    except OSError:
        pass


def upload_chunk(admin_id: str, lesson_id: str, kind: str, upload_id: str, index: int, total: int,
                 filename: str, data: bytes) -> dict:
    """Stores one chunk; joins them when the last one is in and attaches the
    file to the lesson (replacing the previous one)."""
    require_admin(admin_id)
    if kind not in TYPES:
        raise CourseError(400, "Choose video or notes.")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in TYPES[kind]:
        allowed = ", ".join(sorted(TYPES[kind]))
        raise CourseError(400, f"{filename or 'This file'}: use {allowed}.")
    if not _UPLOAD_ID.match(upload_id or ""):
        raise CourseError(400, "Start the upload again.")
    max_chunks = LIMITS[kind] // UPLOAD_CHUNK_BYTES + 1
    if not 1 <= total <= max_chunks or not 0 <= index < total:
        limit_mb = LIMITS[kind] // (1024 * 1024)
        raise CourseError(400, f"Files can be up to {limit_mb} MB.")
    if not data or len(data) > UPLOAD_CHUNK_BYTES:
        raise CourseError(400, "That part of the file was empty or too large.")
    session = db.get_session()
    try:
        if session.get(CourseLesson, lesson_id) is None:
            raise CourseError(404, "No such lesson.")
    finally:
        session.close()
    folder = FILES_DIR / "tmp" / upload_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{index:06d}.part").write_bytes(data)
    parts = sorted(folder.glob("*.part"))
    if len(parts) < total:
        return {"received": len(parts), "total": total, "done": False}

    # The last chunk: join them, check the size, attach the file.
    (FILES_DIR / "files").mkdir(parents=True, exist_ok=True)
    stored = f"{lesson_id}-{kind}-{uuid.uuid4().hex[:8]}{suffix}"
    target = FILES_DIR / "files" / stored
    size = 0
    with target.open("wb") as out:
        for part in parts[:total]:
            with part.open("rb") as chunk:
                shutil.copyfileobj(chunk, out)
            size += part.stat().st_size
    shutil.rmtree(folder, ignore_errors=True)
    if size > LIMITS[kind]:
        target.unlink(missing_ok=True)
        raise CourseError(413, f"Files can be up to {LIMITS[kind] // (1024 * 1024)} MB.")
    session = db.get_session()
    try:
        lesson = session.get(CourseLesson, lesson_id)
        if lesson is None:
            target.unlink(missing_ok=True)
            raise CourseError(404, "No such lesson.")
        name = _clean(Path(filename).name, 255)
        if kind == "video":
            old = lesson.video_file
            lesson.video_file, lesson.video_name, lesson.video_size = stored, name, size
        else:
            old = lesson.notes_file
            lesson.notes_file, lesson.notes_name, lesson.notes_size = stored, name, size
        session.commit()
        result = _lesson_dict(lesson, admin=True)
    finally:
        session.close()
    if old:
        _remove_file(old)
    return {"received": total, "total": total, "done": True, "lesson": result}


def clean_stale_uploads(max_age_seconds: int = 24 * 3600) -> None:
    """Chunks of uploads that never finished, older than a day."""
    root = FILES_DIR / "tmp"
    if not root.is_dir():
        return
    cutoff = time.time() - max_age_seconds
    for folder in root.iterdir():
        try:
            if folder.is_dir() and folder.stat().st_mtime < cutoff:
                shutil.rmtree(folder, ignore_errors=True)
        except OSError:
            pass

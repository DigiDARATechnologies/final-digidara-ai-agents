"""Courses: SkillDARA's admin publishes lessons with videos and notes."""
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.courses import routes as course_routes
from app.courses import service as course_service
from app.models import User


def auth(user_id):
    return {"authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def api(database, monkeypatch, tmp_path):
    monkeypatch.setattr(course_service, "FILES_DIR", tmp_path)
    monkeypatch.setattr(course_service, "UPLOAD_CHUNK_BYTES", 4)
    with database() as session:
        session.add(User(id="platform", name="SkillDARA", email="p@example.test", email_verified=True, is_admin=True))
        session.add(User(id="learner", name="Learner", email="l@example.test", email_verified=True))
        session.commit()
    app = FastAPI()
    app.include_router(course_routes.router)
    with TestClient(app) as client:
        yield client


def _course(api, published=True):
    course = api.post("/platform-admin/courses", headers=auth("platform"),
                      json={"title": "Python basics", "category": "Programming", "published": published}).json()
    lesson = api.post(f"/platform-admin/courses/{course['id']}/lessons", headers=auth("platform"),
                      json={"title": "Variables"}).json()
    return course, lesson


def _upload(api, lesson_id, kind, filename, data):
    upload_id = uuid.uuid4().hex
    chunks = [data[i:i + 4] for i in range(0, len(data), 4)]
    result = None
    for index, chunk in enumerate(chunks):
        result = api.put(f"/platform-admin/courses/lessons/{lesson_id}/upload", headers=auth("platform"),
                         params={"kind": kind, "upload_id": upload_id, "index": index, "total": len(chunks),
                                 "filename": filename}, content=chunk)
        assert result.status_code == 200, result.text
    return result.json()


def test_only_the_platform_admin_manages_courses(api):
    response = api.post("/platform-admin/courses", headers=auth("learner"), json={"title": "Sneaky course"})
    assert response.status_code == 403
    assert api.get("/platform-admin/courses", headers=auth("learner")).status_code == 403


def test_learners_see_published_courses_and_watch_uploaded_video(api):
    course, lesson = _course(api)
    draft, _ = _course(api, published=False)
    done = _upload(api, lesson["id"], "video", "intro.mp4", b"0123456789abcdef-video")
    assert done["done"] and done["lesson"]["video_size"] == 22
    _upload(api, lesson["id"], "notes", "handbook.pdf", b"%PDF-1.4 notes")

    listed = api.get("/courses", headers=auth("learner")).json()["courses"]
    assert [item["id"] for item in listed] == [course["id"]]
    assert api.get(f"/courses/{draft['id']}", headers=auth("learner")).status_code == 404

    detail = api.get(f"/courses/{course['id']}", headers=auth("learner")).json()
    item = detail["lesson_list"][0]
    assert item["has_video"] and item["has_notes"]
    video = api.get(item["video_src"])
    assert video.status_code == 200 and video.content == b"0123456789abcdef-video"
    assert video.headers["content-type"] == "video/mp4"
    part = api.get(item["video_src"], headers={"range": "bytes=0-3"})
    assert part.status_code == 206 and part.content == b"0123"
    notes = api.get(item["notes_src"])
    assert notes.content == b"%PDF-1.4 notes" and "inline" in notes.headers["content-disposition"]

    assert api.put(f"/courses/lessons/{lesson['id']}/progress", headers=auth("learner"),
                   json={"completed": True}).status_code == 200
    assert api.get("/courses", headers=auth("learner")).json()["courses"][0]["completed"] == 1


def test_media_links_are_signed_and_expire(api, monkeypatch):
    _, lesson = _course(api)
    _upload(api, lesson["id"], "video", "intro.mp4", b"video")
    token = course_service.media_token(lesson["id"], "video")
    assert api.get(f"/course-media/{token[:-2]}xx").status_code == 404
    old = course_service.media_token(lesson["id"], "video", now=1_000)
    assert api.get(f"/course-media/{old}").status_code == 410


def test_uploads_reject_wrong_types_and_links(api):
    course, lesson = _course(api)
    response = api.put(f"/platform-admin/courses/lessons/{lesson['id']}/upload", headers=auth("platform"),
                       params={"kind": "video", "upload_id": uuid.uuid4().hex, "index": 0, "total": 1,
                               "filename": "virus.exe"}, content=b"MZ")
    assert response.status_code == 400
    bad = api.put(f"/platform-admin/courses/{course['id']}/lessons/{lesson['id']}", headers=auth("platform"),
                  json={"title": "Variables", "video_url": "https://evil.example/video"})
    assert bad.status_code == 400
    good = api.put(f"/platform-admin/courses/{course['id']}/lessons/{lesson['id']}", headers=auth("platform"),
                   json={"title": "Variables", "video_url": "https://www.youtube.com/watch?v=abc123"})
    assert good.status_code == 200 and good.json()["video_url"].endswith("abc123")


def test_replacing_and_deleting_removes_files(api, tmp_path):
    course, lesson = _course(api)
    _upload(api, lesson["id"], "video", "one.mp4", b"first")
    _upload(api, lesson["id"], "video", "two.mp4", b"second")
    assert len(list((tmp_path / "files").iterdir())) == 1
    assert api.delete(f"/platform-admin/courses/{course['id']}", headers=auth("platform")).status_code == 200
    assert list((tmp_path / "files").iterdir()) == []

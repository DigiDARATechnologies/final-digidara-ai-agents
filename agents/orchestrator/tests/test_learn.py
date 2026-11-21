"""Learning Hub: the content files, who may read them, and the API."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.security import create_access_token
from app.courses import routes as course_routes
from app.learn import routes as learn_routes
from app.learn import service
from app.models import LearnLicense, Organization, OrganizationMember, Payment, User


def auth(user_id):
    return {"authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def api(database):
    with database() as session:
        session.add_all([
            User(id="platform", name="SkillDARA", email="p@example.test", email_verified=True, is_admin=True),
            User(id="free", name="Free", email="f@example.test", email_verified=True),            # never bought
            User(id="buyer", name="Buyer", email="b@example.test", email_verified=True),          # bought, has coins
            User(id="empty", name="Empty", email="e@example.test", email_verified=True, token_balance=0),   # bought, no coins left
            User(id="student", name="Student", email="s@example.test", email_verified=True, token_balance=0),
        ])
        session.commit()      # real MySQL enforces foreign keys, so parents are saved before the rows that point at them
        session.add_all([
            Payment(id="p1", user_id="buyer", plan_id="basic", amount=399, razorpay_order_id="o1", status="paid"),
            Payment(id="p2", user_id="empty", plan_id="basic", amount=399, razorpay_order_id="o2", status="paid"),
        ])
        session.add(Organization(id="college", name="Test College", join_code="COLLEGE1"))
        session.commit()
        session.add(OrganizationMember(id="m1", organization_id="college", user_id="student", role="member"))
        session.commit()
    service.reload()
    app = FastAPI()
    app.include_router(course_routes.router)     # the existing video courses stay mounted beside it
    app.include_router(learn_routes.router)
    with TestClient(app) as client:
        yield client


# --- the content files ---------------------------------------------------------------

def test_the_content_files_are_consistent():
    assert service.validate_content() == []


def test_every_live_course_has_lessons_and_planned_courses_have_none():
    courses = service._load()["courses"]
    live = [c for c in courses.values() if c["status"] == "live"]
    assert len(live) >= 8 and all(c["lessons"] for c in live)
    assert all(not c["lessons"] for c in courses.values() if c["status"] == "soon")


def test_front_matter_is_read():
    meta, body = service.parse_front_matter("---\ntitle: A: b\nminutes: 4\ntakeaways:\n- one\n- two\n---\nHello\n")
    assert meta == {"title": "A: b", "minutes": "4", "takeaways": ["one", "two"]}
    assert body == "Hello\n"
    with pytest.raises(ValueError):
        service.parse_front_matter("no front matter")


def test_reading_time_defaults_to_the_word_count():
    assert service._minutes({}, "word " * 400) == 3
    assert service._minutes({"minutes": "7"}, "x") == 7


def test_the_checker_reports_broken_content(monkeypatch, tmp_path):
    import json
    (tmp_path / "_catalog.json").write_text(json.dumps({"tracks": [{"id": "technical", "title": "T"}], "paths": [{"id": "p", "title": "P", "courses": ["ghost"]}]}))
    folder = tmp_path / "demo" / "intro"
    folder.mkdir(parents=True)
    (tmp_path / "demo" / "course.json").write_text(json.dumps({
        "slug": "demo", "title": "Demo", "track": "technical",
        "chapters": [{"id": "intro", "title": "Intro", "lessons": ["bad", "listed"]}]}))
    (folder / "bad.md").write_text("---\ntitle: Bad\n---\n```python\nprint(1)\n:::tip\nnever closed\n")
    (folder / "listed.md").write_text("---\ntitle: Fine\nsummary: ok\n---\nText\n")
    (folder / "orphan.md").write_text("---\ntitle: Orphan\nsummary: x\n---\nText\n")
    monkeypatch.setattr(service, "CONTENT", tmp_path)
    service.reload()
    try:
        problems = service.validate_content()
    finally:
        monkeypatch.undo()
        service.reload()
    text = " | ".join(problems)
    assert "demo/bad: unclosed code fence" in text
    assert "demo/bad: 1 callouts opened, 0 closed" in text
    assert "demo/bad: no summary" in text
    assert "demo/orphan: file is not listed" in text
    assert "path p: unknown course ghost" in text


# --- who may read ---------------------------------------------------------------------

def test_a_learner_who_never_bought_coins_is_locked(api):
    assert service.access_for("free") == {"unlocked": False, "reason": "no_purchase"}


def test_a_buyer_with_coins_left_is_unlocked(api):
    assert service.access_for("buyer") == {"unlocked": True, "reason": "coins"}


def test_when_the_coins_run_out_it_locks_and_a_new_purchase_opens_it_again(api, database):
    assert service.access_for("empty") == {"unlocked": False, "reason": "no_coins"}
    with database() as session:
        session.get(User, "empty").token_balance = 5000
        session.commit()
    assert service.access_for("empty")["unlocked"] is True


def test_an_unpaid_payment_does_not_count(api, database):
    with database() as session:
        session.add(Payment(id="p3", user_id="free", plan_id="basic", amount=399, razorpay_order_id="o3", status="created"))
        session.commit()
    assert service.access_for("free")["reason"] == "no_purchase"


def test_admins_always_have_access(api):
    assert service.access_for("platform") == {"unlocked": True, "reason": "admin"}


def test_a_licensed_college_opens_it_for_its_members_without_coins(api, database):
    assert service.access_for("student")["unlocked"] is False
    with database() as session:
        session.add(LearnLicense(organization_id="college"))
        session.commit()
    assert service.access_for("student") == {"unlocked": True, "reason": "college"}


def test_a_suspended_college_licence_does_not_count(api, database):
    with database() as session:
        session.add(LearnLicense(organization_id="college"))
        session.get(Organization, "college").status = "suspended"
        session.commit()
    assert service.access_for("student")["unlocked"] is False


# --- the API ----------------------------------------------------------------------------

def test_a_locked_learner_gets_the_rule_and_no_lessons(api):
    catalog = api.get("/courses/hub/catalog", headers=auth("free")).json()
    assert catalog["access"] == {"unlocked": False, "reason": "no_purchase"}
    assert catalog["tracks"] == [] and catalog["paths"] == []
    assert api.get("/courses/hub/python", headers=auth("free")).status_code == 402
    locked = api.get("/courses/hub/python/lessons/what-is-python", headers=auth("free"))
    assert locked.status_code == 402 and "Buy coins" in locked.json()["detail"]
    assert "print(" not in locked.text


def test_the_coins_over_message_differs_from_the_never_bought_one(api):
    never = api.get("/courses/hub/python", headers=auth("free")).json()["detail"]
    over = api.get("/courses/hub/python", headers=auth("empty")).json()["detail"]
    assert never != over and "over" in over


def test_sign_in_is_required(api):
    assert api.get("/courses/hub/catalog").status_code in (401, 403)


def test_the_catalog_has_tracks_paths_and_planned_courses(api):
    catalog = api.get("/courses/hub/catalog", headers=auth("buyer")).json()
    assert catalog["access"]["unlocked"] is True
    tracks = {t["id"]: t for t in catalog["tracks"]}
    assert set(tracks) == {"technical", "data-ai", "aptitude", "interview", "communication", "projects"}
    python = next(c for c in tracks["technical"]["courses"] if c["slug"] == "python")
    assert python["status"] == "live" and python["lessons"] >= 13 and python["minutes"] > 0
    assert any(c["status"] == "soon" for c in tracks["technical"]["courses"])      # planned courses are listed too
    assert {c["slug"] for c in tracks["communication"]["courses"]} >= {"professional-writing", "interview-communication"}
    assert {c["slug"] for c in tracks["projects"]["courses"]} >= {"python-projects", "portfolio-and-github"}
    statuses = [c["status"] for c in tracks["technical"]["courses"]]
    assert statuses == sorted(statuses, key=lambda s: s != "live")     # live courses come first
    assert {p["id"] for p in catalog["paths"]} >= {"full-stack-python", "placement-ready"}


def test_a_course_outline_lists_chapters_and_lessons_without_their_text(api):
    outline = api.get("/courses/hub/python", headers=auth("buyer")).json()
    assert outline["title"] == "Python" and outline["chapters"][0]["id"] == "start"
    first = outline["chapters"][0]["lessons"][0]
    assert first["id"] == "what-is-python" and first["title"] == "What is Python?" and first["done"] is False
    assert "body" not in first


def test_a_lesson_comes_with_its_text_and_its_neighbours(api):
    data = api.get("/courses/hub/python/lessons/first-program", headers=auth("buyer")).json()
    assert data["lesson"]["title"] == "Your first program" and "print(" in data["lesson"]["body"]
    assert data["lesson"]["number"] == 2 and data["lesson"]["of"] == 15
    assert data["previous"]["id"] == "what-is-python" and data["next"]["id"] == "variables-and-types"
    first = api.get("/courses/hub/python/lessons/what-is-python", headers=auth("buyer")).json()
    assert first["previous"] is None
    last = api.get("/courses/hub/python/lessons/modules-and-virtual-environments", headers=auth("buyer")).json()
    assert last["next"] is None


def test_unknown_courses_and_lessons_are_404(api):
    assert api.get("/courses/hub/nope", headers=auth("buyer")).status_code == 404
    assert api.get("/courses/hub/python/lessons/nope", headers=auth("buyer")).status_code == 404
    assert api.put("/courses/hub/python/lessons/nope/progress", headers=auth("buyer"), json={}).status_code == 404


def test_the_fixed_words_are_not_read_as_a_course_name(api):
    assert api.get("/courses/hub/search?q=python", headers=auth("buyer")).status_code == 200
    assert api.get("/courses/hub/catalog", headers=auth("buyer")).status_code == 200


def test_progress_is_saved_and_counted(api):
    h = auth("buyer")
    done = api.put("/courses/hub/python/lessons/first-program/progress", headers=h, json={"completed": True}).json()
    assert done["completed"] is True
    outline = api.get("/courses/hub/python", headers=h).json()
    assert outline["completed"] == 1 and outline["chapters"][0]["lessons"][1]["done"] is True
    assert api.get("/courses/hub/python/lessons/first-program", headers=h).json()["lesson"]["done"] is True
    api.put("/courses/hub/python/lessons/first-program/progress", headers=h, json={"completed": False})
    assert api.get("/courses/hub/python", headers=h).json()["completed"] == 0
    api.put("/courses/hub/python/lessons/first-program/progress", headers=h, json={"completed": True})
    assert api.get("/courses/hub/python", headers=auth("platform")).json()["completed"] == 0   # not shared between learners


def test_progress_needs_access(api):
    assert api.put("/courses/hub/python/lessons/first-program/progress", headers=auth("free"), json={}).status_code == 402


def test_search_finds_lessons_by_title_and_text(api):
    h = auth("buyer")
    by_title = api.get("/courses/hub/search", params={"q": "joins"}, headers=h).json()["results"]
    assert by_title and by_title[0]["course"] == "sql" and by_title[0]["lesson"] == "joins"
    by_text = api.get("/courses/hub/search", params={"q": "flexbox"}, headers=h).json()["results"]
    assert any(r["course"] == "html-css" for r in by_text)
    assert api.get("/courses/hub/search", params={"q": "  "}, headers=h).json()["results"] == []
    assert api.get("/courses/hub/search", params={"q": "zzzqqq"}, headers=h).json()["results"] == []


def test_search_is_locked_for_unpaid_learners(api):
    assert api.get("/courses/hub/search", params={"q": "python"}, headers=auth("free")).status_code == 402


def test_interview_courses_are_question_sets(api):
    data = api.get("/courses/hub/interview-python/lessons/python-basics-qa", headers=auth("buyer")).json()
    assert data["lesson"]["kind"] == "qa" and "### Q [" in data["lesson"]["body"]


def test_only_the_admin_manages_licences(api):
    assert api.get("/platform-admin/courses/hub/licenses", headers=auth("buyer")).status_code == 403
    assert api.put("/platform-admin/courses/hub/licenses/college", headers=auth("buyer"), json={"enabled": True}).status_code == 403
    rows = api.get("/platform-admin/courses/hub/licenses", headers=auth("platform")).json()
    assert rows == [{"organization_id": "college", "name": "Test College", "kind": "college", "licensed": False}]
    assert api.put("/platform-admin/courses/hub/licenses/college", headers=auth("platform"), json={"enabled": True}).json()["licensed"] is True
    assert api.get("/courses/hub/catalog", headers=auth("student")).json()["access"] == {"unlocked": True, "reason": "college"}
    api.put("/platform-admin/courses/hub/licenses/college", headers=auth("platform"), json={"enabled": False})
    assert api.get("/courses/hub/catalog", headers=auth("student")).json()["access"]["unlocked"] is False
    assert api.put("/platform-admin/courses/hub/licenses/missing", headers=auth("platform"), json={"enabled": True}).status_code == 404


def test_the_existing_video_courses_still_work_beside_the_hub(api):
    assert api.get("/courses", headers=auth("buyer")).status_code == 200

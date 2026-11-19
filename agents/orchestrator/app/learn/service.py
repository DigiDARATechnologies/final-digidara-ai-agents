"""Learning Hub: static tutorials, interview questions and aptitude lessons.

The lessons are Markdown files in this repository (app/learn/content), not rows an admin
uploads, so they go through review and CI like code. Layout:

    content/_catalog.json                       the tracks and the learning paths
    content/<course>/course.json                title, track, level, chapters (in order)
    content/<course>/<chapter>/<lesson>.md      front matter, then the lesson

The lessons are only sent to people who may read them (see `access_for`): SkillDARA's admin,
members of an organization with a licence, and learners who bought coins and still have some.
A locked learner gets the rule and nothing else, so the text cannot be read from the page.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from app import db
from app.models import LearnLicense, LearnProgress, Organization, OrganizationMember, Payment, User

CONTENT = Path(__file__).resolve().parent / "content"
LIVE, SOON = "live", "soon"
_WORDS_PER_MINUTE = 180
_FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.S)
_KEY = re.compile(r"^([A-Za-z_]+):[ \t]*(.*)$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,78}$")


class LearnError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


# --- reading the files --------------------------------------------------------------

def parse_front_matter(text: str) -> tuple[dict, str]:
    """`---` block of `key: value` lines (a key with no value takes the `- item` lines under it), then the body."""
    match = _FRONT.match(text.lstrip("﻿"))
    if not match:
        raise ValueError("a lesson must start with a --- front matter block")
    meta: dict = {}
    current: str | None = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith("- ") and current is not None and isinstance(meta.get(current), list):
            meta[current].append(line[2:].strip())
            continue
        key = _KEY.match(line)
        if not key:
            raise ValueError(f"cannot read front matter line: {line!r}")
        name, value = key.group(1), key.group(2).strip()
        meta[name] = value if value else []
        current = name
    return meta, match.group(2).strip("\n") + "\n"


def _minutes(meta: dict, body: str) -> int:
    try:
        return max(1, int(meta.get("minutes", "")))
    except (TypeError, ValueError):
        return max(1, math.ceil(len(body.split()) / _WORDS_PER_MINUTE))


@lru_cache(maxsize=1)
def _load() -> dict:
    """Every course, with its lessons in reading order. Read once: the files only change with a release."""
    catalog = json.loads((CONTENT / "_catalog.json").read_text(encoding="utf-8"))
    courses: dict[str, dict] = {}
    for folder in sorted(p for p in CONTENT.iterdir() if p.is_dir()):
        spec_file = folder / "course.json"
        if not spec_file.is_file():
            continue
        spec = json.loads(spec_file.read_text(encoding="utf-8"))
        slug = spec["slug"]
        chapters, lessons, by_id = [], [], {}
        for chapter in spec.get("chapters", []):
            ids = []
            for lesson_id in chapter["lessons"]:
                path = folder / chapter["id"] / f"{lesson_id}.md"
                meta, body = parse_front_matter(path.read_text(encoding="utf-8"))
                lesson = {
                    "id": lesson_id, "chapter": chapter["id"], "chapter_title": chapter["title"],
                    "title": meta.get("title", lesson_id), "summary": meta.get("summary", ""),
                    "takeaways": meta.get("takeaways", []) if isinstance(meta.get("takeaways", []), list) else [],
                    "kind": meta.get("kind", "article"), "minutes": _minutes(meta, body), "body": body,
                    "position": len(lessons),
                }
                lessons.append(lesson)
                by_id[lesson_id] = lesson
                ids.append(lesson_id)
            chapters.append({"id": chapter["id"], "title": chapter["title"], "summary": chapter.get("summary", ""), "lessons": ids})
        courses[slug] = {**spec, "status": spec.get("status", LIVE if lessons else SOON), "chapters": chapters, "lessons": lessons, "by_id": by_id}
    return {"catalog": catalog, "courses": courses}


def reload() -> None:
    _load.cache_clear()


def _course_summary(course: dict, done: set[tuple[str, str]]) -> dict:
    total = len(course["lessons"])
    finished = sum(1 for lesson in course["lessons"] if (course["slug"], lesson["id"]) in done)
    return {
        "slug": course["slug"], "title": course["title"], "track": course["track"], "level": course.get("level", ""),
        "summary": course.get("summary", ""), "icon": course.get("icon", ""), "color": course.get("color", "#2851d8"),
        "status": course["status"], "kind": course.get("kind", "tutorial"),
        "lessons": total, "chapters": len(course["chapters"]), "minutes": sum(lesson["minutes"] for lesson in course["lessons"]),
        "completed": finished,
    }


# --- who may read -------------------------------------------------------------------

def access_for(user_id: str) -> dict:
    """{"unlocked": bool, "reason": ...}. Open to admins, to members of an organization with a
    licence, and to learners who have paid for coins AND still have coins left. The 25 free signup
    coins alone do not open it."""
    session = db.get_session()
    try:
        user = session.get(User, user_id)
        if user is None:
            raise LearnError(401, "This account no longer exists.")
        if user.is_admin:
            return {"unlocked": True, "reason": "admin"}
        licensed = (
            session.query(LearnLicense.organization_id)
            .join(OrganizationMember, OrganizationMember.organization_id == LearnLicense.organization_id)
            .join(Organization, Organization.id == LearnLicense.organization_id)
            .filter(OrganizationMember.user_id == user_id, Organization.status == "active").first()
        )
        if licensed is not None:
            return {"unlocked": True, "reason": "college"}
        bought = session.query(Payment.id).filter(Payment.user_id == user_id, Payment.status == "paid", Payment.amount > 0).first()
        if bought is None:
            return {"unlocked": False, "reason": "no_purchase"}
        if (user.token_balance or 0) <= 0:
            return {"unlocked": False, "reason": "no_coins"}
        return {"unlocked": True, "reason": "coins"}
    finally:
        session.close()


def _require_access(user_id: str) -> dict:
    access = access_for(user_id)
    if not access["unlocked"]:
        raise LearnError(402, "The Learning Hub opens with coins. Buy coins to read the lessons." if access["reason"] == "no_purchase"
                         else "Your coins are over. Buy coins to keep reading.")
    return access


def _done(user_id: str) -> set[tuple[str, str]]:
    session = db.get_session()
    try:
        return {(row.course, row.lesson) for row in session.query(LearnProgress).filter(LearnProgress.user_id == user_id).all()}
    finally:
        session.close()


# --- the reader's API ---------------------------------------------------------------

def catalog(user_id: str) -> dict:
    access = access_for(user_id)
    if not access["unlocked"]:
        return {"access": access, "tracks": [], "paths": []}
    data = _load()
    done = _done(user_id)
    summaries = {slug: _course_summary(course, done) for slug, course in data["courses"].items()}
    tracks = []
    for track in data["catalog"]["tracks"]:
        items = [s for s in summaries.values() if s["track"] == track["id"]]
        items.sort(key=lambda s: (s["status"] != LIVE, data["courses"][s["slug"]].get("order", 99), s["title"]))
        tracks.append({"id": track["id"], "title": track["title"], "blurb": track.get("blurb", ""), "courses": items})
    paths = []
    for path in data["catalog"].get("paths", []):
        steps = [summaries[slug] for slug in path["courses"] if slug in summaries]
        paths.append({"id": path["id"], "title": path["title"], "summary": path.get("summary", ""), "courses": steps})
    return {"access": access, "tracks": tracks, "paths": paths}


def _outline(course: dict, done: set[tuple[str, str]]) -> dict:
    lessons = course["by_id"]
    return {
        **_course_summary(course, done), "outcomes": course.get("outcomes", []),
        "chapters": [
            {"id": ch["id"], "title": ch["title"], "summary": ch["summary"], "lessons": [
                {"id": lid, "title": lessons[lid]["title"], "minutes": lessons[lid]["minutes"], "kind": lessons[lid]["kind"],
                 "done": (course["slug"], lid) in done}
                for lid in ch["lessons"]]}
            for ch in course["chapters"]
        ],
    }


def _course(slug: str) -> dict:
    course = _load()["courses"].get(slug)
    if course is None:
        raise LearnError(404, "No such course.")
    return course


def course_outline(user_id: str, slug: str) -> dict:
    _require_access(user_id)
    return _outline(_course(slug), _done(user_id))


def lesson(user_id: str, slug: str, lesson_id: str) -> dict:
    _require_access(user_id)
    course = _course(slug)
    item = course["by_id"].get(lesson_id)
    if item is None:
        raise LearnError(404, "No such lesson.")
    lessons = course["lessons"]

    def ref(other: dict | None) -> dict | None:
        return None if other is None else {"id": other["id"], "title": other["title"], "chapter_title": other["chapter_title"]}

    done = _done(user_id)
    return {
        "course": {"slug": course["slug"], "title": course["title"], "track": course["track"], "color": course.get("color", "#2851d8")},
        "lesson": {k: item[k] for k in ("id", "chapter", "chapter_title", "title", "summary", "takeaways", "kind", "minutes", "body")}
                  | {"done": (slug, lesson_id) in done, "number": item["position"] + 1, "of": len(lessons)},
        "previous": ref(lessons[item["position"] - 1] if item["position"] > 0 else None),
        "next": ref(lessons[item["position"] + 1] if item["position"] + 1 < len(lessons) else None),
    }


def set_done(user_id: str, slug: str, lesson_id: str, completed: bool) -> dict:
    _require_access(user_id)
    if lesson_id not in _course(slug)["by_id"]:
        raise LearnError(404, "No such lesson.")
    session = db.get_session()
    try:
        row = session.get(LearnProgress, (user_id, slug, lesson_id))
        if completed and row is None:
            session.add(LearnProgress(user_id=user_id, course=slug, lesson=lesson_id))
        elif not completed and row is not None:
            session.delete(row)
        session.commit()
        return {"course": slug, "lesson": lesson_id, "completed": completed}
    finally:
        session.close()


def search(user_id: str, query: str, limit: int = 20) -> dict:
    """Lessons whose title, summary or text has every word of the query; titles first."""
    _require_access(user_id)
    words = [w for w in re.findall(r"[a-z0-9+#.]+", query.lower()) if w]
    if not words:
        return {"query": query, "results": []}
    hits = []
    for course in _load()["courses"].values():
        for item in course["lessons"]:
            title, rest = item["title"].lower(), f"{item['summary']} {item['body']}".lower()
            if not all(w in title or w in rest for w in words):
                continue
            rank = 0 if all(w in title for w in words) else 1
            mentions = sum(rest.count(w) for w in words)
            first = next((rest.find(w) for w in words if w in rest), -1)
            snippet = "" if first < 0 else re.sub(r"\s+", " ", item["body"][max(0, first - 40): first + 120]).strip()
            hits.append((rank, len(item["title"]) if rank == 0 else 0, -mentions, course["title"], item["position"], {
                "course": course["slug"], "course_title": course["title"], "lesson": item["id"], "title": item["title"],
                "chapter_title": item["chapter_title"], "snippet": snippet}))
    hits.sort(key=lambda h: h[:5])      # title matches first (shorter titles first), then the most mentions
    return {"query": query, "results": [h[5] for h in hits[:limit]]}


# --- SkillDARA admin: which colleges have a licence ----------------------------------

def _require_admin(user_id: str) -> None:
    session = db.get_session()
    try:
        user = session.get(User, user_id)
        if user is None or not user.is_admin:
            raise LearnError(403, "Only SkillDARA's admin can manage Learning Hub licences.")
    finally:
        session.close()


def licenses(admin_id: str) -> list[dict]:
    _require_admin(admin_id)
    session = db.get_session()
    try:
        licensed = {row.organization_id for row in session.query(LearnLicense).all()}
        return [{"organization_id": org.id, "name": org.name, "kind": org.kind, "licensed": org.id in licensed}
                for org in session.query(Organization).order_by(Organization.name).all()]
    finally:
        session.close()


def set_license(admin_id: str, organization_id: str, enabled: bool) -> dict:
    _require_admin(admin_id)
    session = db.get_session()
    try:
        if session.get(Organization, organization_id) is None:
            raise LearnError(404, "No such organization.")
        row = session.get(LearnLicense, organization_id)
        if enabled and row is None:
            session.add(LearnLicense(organization_id=organization_id))
        elif not enabled and row is not None:
            session.delete(row)
        session.commit()
        return {"organization_id": organization_id, "licensed": enabled}
    finally:
        session.close()


# --- checking the files (used by tests and CI) ---------------------------------------

def validate_content() -> list[str]:
    """Problems with the content files; an empty list means they are consistent."""
    problems: list[str] = []
    try:
        data = _load()
    except Exception as exc:  # a broken file should name itself, not crash the checker
        return [f"content does not load: {exc}"]
    track_ids = {t["id"] for t in data["catalog"]["tracks"]}
    for slug, course in data["courses"].items():
        if not _SLUG.match(slug):
            problems.append(f"{slug}: bad slug")
        if course["track"] not in track_ids:
            problems.append(f"{slug}: unknown track {course['track']!r}")
        if course["status"] == LIVE and not course["lessons"]:
            problems.append(f"{slug}: marked live but has no lessons")
        seen: set[str] = set()
        for lesson_item in course["lessons"]:
            lid = lesson_item["id"]
            if lid in seen:
                problems.append(f"{slug}/{lid}: duplicate lesson id")
            seen.add(lid)
            if not _SLUG.match(lid):
                problems.append(f"{slug}/{lid}: bad lesson id")
            body = lesson_item["body"]
            if body.count("```") % 2:
                problems.append(f"{slug}/{lid}: unclosed code fence")
            opens = len(re.findall(r"^:::[a-z]+", body, re.M))
            closes = len(re.findall(r"^:::\s*$", body, re.M))
            if opens != closes:
                problems.append(f"{slug}/{lid}: {opens} callouts opened, {closes} closed")
            if not lesson_item["summary"]:
                problems.append(f"{slug}/{lid}: no summary")
        on_disk = {p.stem for p in (CONTENT / slug).glob("*/*.md")}
        for orphan in sorted(on_disk - seen):
            problems.append(f"{slug}/{orphan}: file is not listed in course.json")
    for path in data["catalog"].get("paths", []):
        for slug in path["courses"]:
            if slug not in data["courses"]:
                problems.append(f"path {path['id']}: unknown course {slug}")
    return problems

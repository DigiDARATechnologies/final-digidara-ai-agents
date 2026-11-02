"""Job-readiness leaderboards: the top learners by readiness score.

Two groups. Students: learners, ranked by their own job readiness. Staff:
an organization's staff, ranked on their students (those who joined with
their join codes or are on their uploaded list): 70% the students' average
job readiness, 30% the share of them active in the last two weeks.
Who sees what:
  - a student: the students board of their organization and of the platform,
  - staff: their organization's staff board,
  - an owner or admin: their organization's students and staff boards,
  - SkillDARA's platform admin: everything.

A staff member's own job readiness is not part of their staff score; it comes
back beside their rank (me.own_readiness) so they can see the two apart.

Scores are each learner's latest readiness for their current target role,
scored by today's rules (readiness_service.scored). Inside an organization a
student appears only if they share their progress with it (their consent);
anyone can hide themselves from every board. Names are shortened to the first
name and an initial.

The top 3 of each board is remembered (LeaderboardTop) with the time each
person entered it, so someone who just broke into the top 3 is marked new.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.learner.service import clean_text
from app.models import (
    LeaderboardOptOut,
    LeaderboardTop,
    LearnerProfile,
    Organization,
    OrganizationMember,
    ReadinessSnapshot,
    User,
)
from app.readiness import service as readiness_service

GROUPS = ("students", "staff")
SCOPES = ("platform", "organization")
STAFF_ROLES = ("owner", "admin", "staff")
TOP = 3
LIST_LIMIT = 50
# How long someone who broke into the top 3 is shown as new.
NEW_FOR = timedelta(days=3)
# Staff are ranked on their students: readiness weight, the rest is activity.
STAFF_READINESS_WEIGHT = 0.7
ACTIVE_WINDOW = timedelta(days=14)
# Every learner's score, reused for this long across requests.
CACHE_SECONDS = 60
_cache: dict = {"at": 0.0, "scores": {}}


class LeaderboardError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _short_name(name: str | None) -> str:
    parts = (name or "").split()
    if not parts:
        return "A learner"
    return parts[0][:40] + (f" {parts[-1][0].upper()}." if len(parts) > 1 else "")


def clear_cache() -> None:
    _cache.update({"at": 0.0, "scores": {}})


def _all_scores() -> dict[str, tuple[float, datetime]]:
    """user id -> (readiness score, when it was reached) for everyone with a
    readiness score for their current target role."""
    now = time.monotonic()
    if now - _cache["at"] < CACHE_SECONDS:
        return _cache["scores"]
    session = db.get_session()
    try:
        roles = {user_id: clean_text(role) for user_id, role in session.query(LearnerProfile.user_id, LearnerProfile.target_role).all()}
        latest = (session.query(ReadinessSnapshot.user_id, ReadinessSnapshot.role_key,
                                func.max(ReadinessSnapshot.computed_at).label("at"))
                  .group_by(ReadinessSnapshot.user_id, ReadinessSnapshot.role_key).subquery())
        rows = (session.query(ReadinessSnapshot)
                .join(latest, (ReadinessSnapshot.user_id == latest.c.user_id) & (ReadinessSnapshot.role_key == latest.c.role_key)
                      & (ReadinessSnapshot.computed_at == latest.c.at))
                .all())
    finally:
        session.close()
    best: dict[str, ReadinessSnapshot] = {}
    for row in rows:
        if row.role_key not in (roles.get(row.user_id, ""), ""):
            continue            # a snapshot for a role the learner has left
        current = best.get(row.user_id)
        if current is None or row.computed_at > current.computed_at:
            best[row.user_id] = row
    scores = {}
    for user_id, row in best.items():
        overall = readiness_service.scored(row)["overall"] if isinstance((row.areas or {}).get("areas"), list) else row.overall
        if overall is not None:
            scores[user_id] = (float(overall), row.computed_at)
    _cache.update({"at": now, "scores": scores})
    return scores


def _viewer(session, user_id: str) -> tuple[User, OrganizationMember | None]:
    user = session.get(User, user_id)
    if user is None:
        raise LeaderboardError(401, "This account no longer exists.")
    return user, session.query(OrganizationMember).filter_by(user_id=user_id).first()


def allowed_groups(user: User, member: OrganizationMember | None) -> list[str]:
    if user.is_admin or (member is not None and member.role in ("owner", "admin")):
        return list(GROUPS)
    if member is not None and member.role == "staff":
        return ["staff"]
    return ["students"]


def allowed_scopes(user: User, member: OrganizationMember | None) -> list[str]:
    """Students: their organization and the whole platform. Staff, owners and
    admins: their own organization only. SkillDARA admins: everything."""
    if user.is_admin:
        return ["platform", "organization"] if member is not None else ["platform"]
    if member is not None and member.role in STAFF_ROLES:
        return ["organization"]
    return ["organization", "platform"] if member is not None else ["platform"]


def _staff_scores(session, org_id: str, hidden: set[str], scores: dict) -> list[tuple[str, float, datetime, dict]]:
    """Each staff member of the organization, scored on their students: 70%
    their students' average job readiness (no score yet counts as 0) and 30%
    the share of their students active in the last 14 days."""
    from app.organizations import service as org_service

    staff = session.query(OrganizationMember).filter_by(organization_id=org_id, role="staff").all()
    students = {m.user_id: m for m in session.query(OrganizationMember)
                .filter_by(organization_id=org_id, role="member").all() if m.progress_shared_at is not None}
    since = datetime.utcnow() - ACTIVE_WINDOW
    last_active = org_service._last_active(session, list(students))
    rows = []
    for person in staff:
        if person.user_id in hidden:
            continue
        mine = [uid for uid in org_service.staff_students(session, person.user_id, org_id) if uid in students]
        readiness = [scores[uid][0] if uid in scores else 0.0 for uid in mine]
        average = sum(readiness) / len(readiness) if readiness else 0.0
        active = sum(1 for uid in mine if last_active.get(uid) and last_active[uid] >= since)
        active_percent = 100.0 * active / len(mine) if mine else 0.0
        score = round(STAFF_READINESS_WEIGHT * average + (1 - STAFF_READINESS_WEIGHT) * active_percent, 1)
        rows.append((person.user_id, score, person.created_at or datetime.utcnow(),
                     {"students": len(mine), "average_readiness": round(average, 1), "active_percent": round(active_percent)}))
    return rows


def _sync_top(session, board: str, top_ids: list[str]) -> dict[str, datetime]:
    """Remembers this board's top 3 and returns when each entered it. The
    first time a board is seen, its top 3 is not new (nobody broke in)."""
    rows = {r.user_id: r for r in session.query(LeaderboardTop).filter_by(board=board).all()}
    seeded = bool(rows)
    now = datetime.utcnow()
    for user_id, row in rows.items():
        if user_id not in top_ids:
            session.delete(row)
    for user_id in top_ids:
        if user_id not in rows:
            rows[user_id] = LeaderboardTop(board=board, user_id=user_id, entered_at=now if seeded else datetime(2000, 1, 1))
            session.add(rows[user_id])
    session.commit()
    return {user_id: rows[user_id].entered_at for user_id in top_ids}


def board(viewer_id: str, scope: str = "auto", group: str | None = None) -> dict:
    """scope "auto": the viewer's organization when they are in one, else the platform."""
    if scope not in SCOPES + ("auto",):
        raise LeaderboardError(400, "Scope must be platform or organization.")
    scores = _all_scores()
    session = db.get_session()
    try:
        user, member = _viewer(session, viewer_id)
        groups = allowed_groups(user, member)
        scopes = allowed_scopes(user, member)
        group = group or groups[0]
        if group not in GROUPS:
            raise LeaderboardError(400, "Group must be students or staff.")
        if group not in groups:
            raise LeaderboardError(403, "This leaderboard is for organization admins and staff." if group == "staff"
                                   else "This leaderboard is for students and organization admins.")
        if scope == "auto":
            scope = scopes[0]
        if scope not in scopes:
            if scope == "organization":
                raise LeaderboardError(404, "Join an organization to see its leaderboard.")
            raise LeaderboardError(403, "Your leaderboard is your organization's.")
        if group == "staff" and scope != "organization":
            raise LeaderboardError(400, "The staff leaderboard is per organization.")
        org = session.get(Organization, member.organization_id) if member is not None else None

        members = session.query(OrganizationMember)
        if scope == "organization":
            members = members.filter(OrganizationMember.organization_id == org.id)
        membership = {m.user_id: m for m in members.all()}
        hidden = {row.user_id for row in session.query(LeaderboardOptOut.user_id).all()}
        platform_admins = {row.id for row in session.query(User.id).filter(User.is_admin.is_(True)).all()}

        details: dict[str, dict] = {}
        candidates = []
        if group == "staff":
            for user_id, score, since, detail in _staff_scores(session, org.id, hidden, scores):
                candidates.append((user_id, score, since))
                details[user_id] = detail
        else:
            for user_id, (score, reached_at) in scores.items():
                if user_id in hidden or user_id in platform_admins:
                    continue
                m = membership.get(user_id)
                if m is not None and m.role in STAFF_ROLES:
                    continue
                if scope == "organization" and (m is None or m.progress_shared_at is None):
                    continue       # inside an organization, only learners who share their progress
                candidates.append((user_id, score, reached_at))
        # Higher score first; on a tie, whoever reached it first.
        candidates.sort(key=lambda c: (-c[1], c[2]))

        ranked_ids = [c[0] for c in candidates[:LIST_LIMIT]]
        # Plain values now: saving the top 3 below expires every loaded row.
        names = {uid: name for uid, name in session.query(User.id, User.name).filter(User.id.in_(ranked_ids)).all()} if ranked_ids else {}
        org_of = {uid: membership[uid].organization_id for uid in ranked_ids if uid in membership}
        org_names = {o.id: o.name for o in session.query(Organization).filter(Organization.id.in_(set(org_of.values()))).all()} if org_of else {}
        viewer_org = {"id": org.id, "name": org.name} if org else None
        board_key = f"platform:{group}" if scope == "platform" else f"org:{org.id}:{group}"
        entered = _sync_top(session, board_key, [uid for uid, score, _ in candidates[:TOP] if score > 0])
    finally:
        session.close()

    now = datetime.utcnow()
    from app.learner import avatar

    pictures = avatar.thumbs(ranked_ids)

    def entry(rank: int, user_id: str, score: float) -> dict:
        item = {
            "rank": rank, "user_id": user_id, "name": _short_name(names.get(user_id, "")),
            "avatar": pictures.get(user_id),
            "score": round(score, 1), "band": readiness_service.band_for(score, 1),
            "organization": org_names.get(org_of.get(user_id, "")) if scope == "platform" else None,
            "is_me": user_id == viewer_id,
        }
        if user_id in details:
            item["staff"] = details[user_id]
        if user_id in entered:
            item["entered_top_at"] = entered[user_id].isoformat()
            item["new_in_top"] = now - entered[user_id] < NEW_FOR
        return item

    entries = [entry(i + 1, uid, score) for i, (uid, score, _) in enumerate(candidates[:LIST_LIMIT])]
    me = next(({"rank": i + 1, "score": round(score, 1)} for i, (uid, score, _) in enumerate(candidates) if uid == viewer_id), None)
    if me and group == "staff" and viewer_id in scores:
        me["own_readiness"] = round(scores[viewer_id][0], 1)
    return {
        "scope": scope, "group": group, "allowed_groups": groups, "allowed_scopes": scopes,
        "organization": viewer_org,
        "top": entries[:TOP], "entries": entries, "total": len(candidates),
        "me": me, "hidden": viewer_id in hidden,
    }


def set_hidden(user_id: str, hidden: bool) -> dict:
    session = db.get_session()
    try:
        row = session.get(LeaderboardOptOut, user_id)
        if hidden and row is None:
            session.add(LeaderboardOptOut(user_id=user_id))
        elif not hidden and row is not None:
            session.delete(row)
        session.commit()
    finally:
        session.close()
    return {"hidden": hidden}

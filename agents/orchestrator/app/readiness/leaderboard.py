"""Job-readiness leaderboards: the top learners by readiness score.

Two groups: students (learners, members of an organization or not) and staff
(an organization's staff, admins and owners). Two scopes: the whole platform,
or one organization. Who sees what:
  - a student sees the students board,
  - staff see the staff board,
  - an organization's owner or admin, and SkillDARA's platform admin, see both.

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


def board(viewer_id: str, scope: str = "platform", group: str | None = None) -> dict:
    if scope not in SCOPES:
        raise LeaderboardError(400, "Scope must be platform or organization.")
    scores = _all_scores()
    session = db.get_session()
    try:
        user, member = _viewer(session, viewer_id)
        groups = allowed_groups(user, member)
        group = group or groups[0]
        if group not in GROUPS:
            raise LeaderboardError(400, "Group must be students or staff.")
        if group not in groups:
            raise LeaderboardError(403, "This leaderboard is for organization admins and staff." if group == "staff"
                                   else "This leaderboard is for students and organization admins.")
        org = session.get(Organization, member.organization_id) if member is not None else None
        if scope == "organization" and org is None:
            raise LeaderboardError(404, "Join an organization to see its leaderboard.")

        members = session.query(OrganizationMember)
        if scope == "organization":
            members = members.filter(OrganizationMember.organization_id == org.id)
        membership = {m.user_id: m for m in members.all()}
        hidden = {row.user_id for row in session.query(LeaderboardOptOut.user_id).all()}
        platform_admins = {row.id for row in session.query(User.id).filter(User.is_admin.is_(True)).all()}

        candidates = []
        for user_id, (score, reached_at) in scores.items():
            if user_id in hidden or user_id in platform_admins:
                continue
            m = membership.get(user_id)
            is_staff = m is not None and m.role in STAFF_ROLES
            if group == "staff" and not is_staff:
                continue
            if group == "students" and is_staff:
                continue
            if scope == "organization":
                if m is None:
                    continue
                if group == "students" and m.progress_shared_at is None:
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
        entered = _sync_top(session, board_key, ranked_ids[:TOP])
    finally:
        session.close()

    now = datetime.utcnow()

    def entry(rank: int, user_id: str, score: float) -> dict:
        item = {
            "rank": rank, "user_id": user_id, "name": _short_name(names.get(user_id, "")),
            "score": round(score, 1), "band": readiness_service.band_for(score, 1),
            "organization": org_names.get(org_of.get(user_id, "")) if scope == "platform" else None,
            "is_me": user_id == viewer_id,
        }
        if user_id in entered:
            item["entered_top_at"] = entered[user_id].isoformat()
            item["new_in_top"] = now - entered[user_id] < NEW_FOR
        return item

    entries = [entry(i + 1, uid, score) for i, (uid, score, _) in enumerate(candidates[:LIST_LIMIT])]
    me = next(({"rank": i + 1, "score": round(score, 1)} for i, (uid, score, _) in enumerate(candidates) if uid == viewer_id), None)
    return {
        "scope": scope, "group": group, "allowed_groups": groups,
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

"""The learning dashboard: one page of numbers, shaped by who is looking.

  - a learner sees their own learning,
  - staff see the students they look after (organizations.service.staff_students),
  - an organization's owner or admin sees all of its students,
  - SkillDARA's platform admin sees the whole platform.
Staff, admins and the platform admin can also switch to their own learning.

Numbers: job readiness (latest score for the current target role), activity
(agent requests from TokenUsageEvent), and the organization's assessment
links (Assessment) with each learner's attempt (ProctorSession, with a
knowledge test's score from KnowledgeAttempt): upcoming, open, submitted or
missed. Inside an organization only students who share their progress count.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.models import (
    Assessment,
    KnowledgeAttempt,
    Organization,
    OrganizationMember,
    ProctorSession,
    TokenUsageEvent,
    User,
)
from app.readiness import service as readiness_service

MONTHS = 6
PEOPLE_LIMIT = 50
ACTIVE_DAYS = 7
STAFF_ROLES = ("owner", "admin", "staff")


class DashboardError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _views(user: User, member: OrganizationMember | None) -> list[str]:
    if member is not None and member.role in ("owner", "admin"):
        return ["organization", "me"]
    if member is not None and member.role == "staff":
        return ["students", "me"]
    if user.is_admin:
        return ["platform", "me"]
    return ["me"]


def _people(session, view: str, user: User, member: OrganizationMember | None) -> tuple[list[str] | None, str]:
    """The learners the view covers (None: everyone on the platform) and its label."""
    from app.organizations import service as org_service

    if view == "me":
        return [user.id], "Your learning"
    if view == "platform":
        return None, "Whole platform"
    org = session.get(Organization, member.organization_id)
    students = {m.user_id for m in session.query(OrganizationMember)
                .filter_by(organization_id=org.id, role="member").all() if m.progress_shared_at is not None}
    if view == "students":
        mine = org_service.staff_students(session, user.id, org.id) & students
        return sorted(mine), f"Your students at {org.name}"
    return sorted(students), org.name


def _month_keys(now: datetime) -> list[str]:
    keys, year, month = [], now.year, now.month
    for _ in range(MONTHS):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def _assessments(session, view: str, user: User, member: OrganizationMember | None, people: list[str] | None) -> list[Assessment]:
    query = session.query(Assessment)
    if view == "platform":
        return query.all()
    if view == "students":
        return query.filter_by(organization_id=member.organization_id, created_by=user.id).all()
    if view == "organization":
        return query.filter_by(organization_id=member.organization_id).all()
    # A learner: their organization's assessment links.
    if member is None:
        return []
    return query.filter_by(organization_id=member.organization_id, active=True).all()


def _score_percent(session_row: ProctorSession, knowledge: dict) -> float | None:
    attempt = knowledge.get(session_row.id)
    if attempt is not None and attempt.max_score:
        return round(100.0 * (attempt.score or 0) / attempt.max_score, 1)
    result = session_row.result or {}
    score, top = result.get("score"), result.get("max")
    if isinstance(score, (int, float)) and isinstance(top, (int, float)) and top:
        return round(100.0 * score / top, 1)
    return None


def build(viewer_id: str, view: str | None = None) -> dict:
    now = datetime.utcnow()
    session = db.get_session()
    try:
        user = session.get(User, viewer_id)
        if user is None:
            raise DashboardError(401, "This account no longer exists.")
        member = session.query(OrganizationMember).filter_by(user_id=viewer_id).first()
        views = _views(user, member)
        view = view or views[0]
        if view not in views:
            raise DashboardError(403, "This view is not available for your account.")
        people, label = _people(session, view, user, member)
        person_filter = (lambda column: column.in_(people or [""])) if people is not None else None

        # Activity: agent requests per month, per agent, and who was active lately.
        months = _month_keys(now)
        since = datetime(int(months[0][:4]), int(months[0][5:]), 1)
        events = session.query(TokenUsageEvent.user_id, TokenUsageEvent.agent_name, TokenUsageEvent.created_at) \
            .filter(TokenUsageEvent.created_at >= since)
        if person_filter is not None:
            events = events.filter(person_filter(TokenUsageEvent.user_id))
        requests_by_month: Counter = Counter()
        agents_30d: Counter = Counter()
        last_seen: dict[str, datetime] = {}
        for uid, agent, when in events.all():
            requests_by_month[when.strftime("%Y-%m")] += 1
            if when >= now - timedelta(days=30):
                agents_30d[agent or "other"] += 1
            if uid not in last_seen or when > last_seen[uid]:
                last_seen[uid] = when
        active_recent = sum(1 for when in last_seen.values() if when >= now - timedelta(days=ACTIVE_DAYS))

        # Assessments: each learner of the view against each link of their organization.
        links = _assessments(session, view, user, member, people)
        link_ids = [a.id for a in links]
        sittings = session.query(ProctorSession).filter(ProctorSession.assessment_id.in_(link_ids or [""]))
        if person_filter is not None:
            sittings = sittings.filter(person_filter(ProctorSession.user_id))
        sittings = sittings.all()
        knowledge = {k.proctor_session_id: k for k in session.query(KnowledgeAttempt)
                     .filter(KnowledgeAttempt.proctor_session_id.in_([s.id for s in sittings] or [""])).all()}
        best: dict[tuple[str, str], ProctorSession] = {}
        for sitting in sittings:
            key = (sitting.user_id, sitting.assessment_id)
            current = best.get(key)
            if current is None or (sitting.status == "completed" and current.status != "completed") \
                    or (sitting.status == current.status and sitting.started_at > current.started_at):
                best[key] = sitting
        org_people: dict[str, set[str]] = defaultdict(set)
        member_rows = session.query(OrganizationMember.organization_id, OrganizationMember.user_id) \
            .filter(OrganizationMember.role == "member")
        if people is not None:
            member_rows = member_rows.filter(OrganizationMember.user_id.in_(people or [""]))
        for org_id, uid in member_rows.all():
            org_people[org_id].add(uid)
        if view == "me":
            org_people = defaultdict(set, {member.organization_id: {user.id}}) if member is not None else defaultdict(set)

        status = Counter()
        scores: list[float] = []
        assigned_by_month: Counter = Counter()
        attempted_by_month: Counter = Counter()
        per_person: dict[str, Counter] = defaultdict(Counter)
        recent_items = []
        for link in links:
            learners = org_people.get(link.organization_id, set())
            created_month = (link.created_at or now).strftime("%Y-%m")
            for uid in learners:
                assigned_by_month[created_month] += 1
                sitting = best.get((uid, link.id))
                if sitting is not None and sitting.status in ("completed", "terminated"):
                    state = "submitted"
                    attempted_by_month[(sitting.started_at or now).strftime("%Y-%m")] += 1
                    percent = _score_percent(sitting, knowledge)
                    if percent is not None:
                        scores.append(percent)
                elif sitting is not None:
                    state = "in_progress"
                    attempted_by_month[(sitting.started_at or now).strftime("%Y-%m")] += 1
                elif link.opens_at and now < link.opens_at:
                    state = "upcoming"
                elif (link.closes_at and now > link.closes_at) or not link.active:
                    state = "missed"
                else:
                    state = "open"
                status[state] += 1
                per_person[uid][state] += 1
                if view == "me":
                    recent_items.append({
                        "title": link.title, "status": state,
                        "score": _score_percent(sitting, knowledge) if sitting is not None else None,
                        "closes_at": link.closes_at.isoformat() if link.closes_at else None,
                        "opens_at": link.opens_at.isoformat() if link.opens_at else None,
                    })
        assigned = sum(status.values())
        due = assigned - status["upcoming"]

        # Job readiness.
        snapshots = readiness_service.latest_for(people) if people is not None else {}
        if people is None:
            from app.readiness import leaderboard

            overall_by_user = {uid: score for uid, (score, _) in leaderboard._all_scores().items()}
            area_sums: dict[str, list[float]] = {}
        else:
            overall_by_user, area_sums = {}, defaultdict(list)
            for uid, snapshot in snapshots.items():
                if not isinstance((snapshot.areas or {}).get("areas"), list):
                    # An old snapshot without its areas: its stored overall is all there is.
                    if snapshot.overall is not None:
                        overall_by_user[uid] = float(snapshot.overall)
                    continue
                current = readiness_service.scored(snapshot)
                if current["overall"] is not None:
                    overall_by_user[uid] = current["overall"]
                for area in current["areas"]:
                    if area.get("status") == "assessed" and area.get("score") is not None:
                        area_sums[area.get("label") or area["agent_name"]].append(float(area["score"]))
        readiness_avg = round(sum(overall_by_user.values()) / len(overall_by_user), 1) if overall_by_user else None

        rows = []
        if view != "me" and people is not None:
            names = dict(session.query(User.id, User.name).filter(User.id.in_(people or [""])).all())
            for uid in people:
                counts = per_person.get(uid, Counter())
                rows.append({
                    "user_id": uid, "name": names.get(uid, ""), "readiness": overall_by_user.get(uid),
                    "submitted": counts["submitted"], "assigned": sum(counts.values()),
                    "last_active_at": last_seen[uid].isoformat() if uid in last_seen else None,
                })
            rows.sort(key=lambda r: (-(r["readiness"] or -1), r["name"]))

        people_count = len(people) if people is not None else session.query(func.count(User.id)).filter(User.is_admin.is_(False)).scalar()
    finally:
        session.close()

    return {
        "view": view, "views": views, "label": label, "people": people_count,
        "kpis": {
            "readiness": readiness_avg,
            "assessments": assigned,
            "submitted": status["submitted"],
            "submission_rate": round(100.0 * status["submitted"] / due, 1) if due else None,
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "active_recently": active_recent,
            "active_days": ACTIVE_DAYS,
            "requests_30d": sum(agents_30d.values()),
        },
        "monthly": [{"month": m, "requests": requests_by_month[m], "assigned": assigned_by_month[m],
                     "attempted": attempted_by_month[m]} for m in months],
        "status": {key: status[key] for key in ("upcoming", "open", "in_progress", "submitted", "missed")},
        "agents": [{"agent": name, "requests": count} for name, count in agents_30d.most_common(8)],
        "areas": sorted(({"label": label_, "average": round(sum(v) / len(v), 1)} for label_, v in area_sums.items() if v),
                        key=lambda a: -a["average"]),
        "assessments": sorted(recent_items, key=lambda i: (i["status"] != "open", i["title"]))[:20],
        "learners": rows[:PEOPLE_LIMIT],
        "generated_at": now.isoformat(),
    }

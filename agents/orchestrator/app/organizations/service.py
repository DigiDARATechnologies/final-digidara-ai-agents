"""Organizations: a college or company registers, adds its learners, and
monitors their readiness and levels.

Two ways in for a learner: an admin creates the account (bulk add, with a
one-time password the admin hands over), or the learner joins with the
organization's join code. Joining is the learner's consent (DPDP Act 2023):
the join screen says the organization's admins will see their readiness,
levels, activity and chats, and the time of joining (or, for an account the
organization created, of the learner's own first sign-in) is recorded in
progress_shared_at. Leaving the organization ends the sharing. A member who
joined before this rule, without agreeing, stays private until they agree.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime

from app import db
from app.auth.security import hash_password
from app.learner import levels as level_rules
from app.learner import service as learner_service
from app.models import Organization, OrganizationMember, OrgJoinCode, User
from app.readiness import service as readiness_service

ROLES = ("owner", "admin", "member")
ADMIN_ROLES = ("owner", "admin")
KINDS = ("college", "training_institute", "company", "other")
MAX_BULK = 200
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class OrgError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _new_join_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


def _temporary_password() -> str:
    return secrets.token_urlsafe(9)


def _org_dict(org: Organization, member_count: int | None = None) -> dict:
    return {
        "id": org.id, "name": org.name, "kind": org.kind, "join_code": org.join_code,
        "member_limit": org.member_limit, "member_count": member_count, "status": org.status or "active",
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


def _class_of(member: OrganizationMember) -> dict:
    return {"department": member.department, "year": member.year, "section": member.section}


def _membership(session, user_id: str) -> OrganizationMember | None:
    return session.query(OrganizationMember).filter_by(user_id=user_id).first()


def _count(session, org_id: str) -> int:
    return session.query(OrganizationMember).filter_by(organization_id=org_id).count()


def my_organization(user_id: str) -> dict | None:
    session = db.get_session()
    try:
        member = _membership(session, user_id)
        if member is None:
            return None
        org = session.get(Organization, member.organization_id)
        data = _org_dict(org, _count(session, org.id))
        if member.role not in ADMIN_ROLES:
            data.pop("join_code")
        return {
            "organization": data, "role": member.role, "member_id": member.id,
            "external_id": member.external_id,
            "progress_shared": member.progress_shared_at is not None,
            **_class_of(member),
        }
    finally:
        session.close()


def create_for_platform(name: str, kind: str, admin_name: str, admin_email: str, member_limit: int, created_by: str) -> dict:
    """Only DigiDARA's platform admin creates organizations, each with its
    first admin login (the owner). A new owner account gets a one-time
    password, returned here once; an existing account is made the owner."""
    name = " ".join(name.split())[:255]
    email = admin_email.strip().lower()
    if len(name) < 2:
        raise OrgError(400, "Enter the organization's name.")
    if not _EMAIL.match(email):
        raise OrgError(400, "Enter a valid email for the organization's admin.")
    session = db.get_session()
    try:
        user = session.query(User).filter_by(email=email).first()
        password = None
        if user is None:
            password = _temporary_password()
            user = User(name=" ".join(admin_name.split())[:255] or email.split("@")[0], email=email,
                        password_hash=hash_password(password))
            session.add(user)
            session.flush()
        elif _membership(session, user.id) is not None:
            raise OrgError(409, f"{email} already belongs to an organization.")
        org = Organization(name=name, kind=kind if kind in KINDS else "other", join_code=_new_join_code(),
                           created_by=created_by, member_limit=max(1, min(int(member_limit or 1000), 100000)))
        session.add(org)
        session.flush()
        session.add(OrgJoinCode(organization_id=org.id, code=org.join_code, label="General", created_by=created_by))
        session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
        session.commit()
        result = {
            "organization": _org_dict(org, 1),
            "admin": {"name": user.name, "email": email, "status": "created" if password else "attached",
                      "temporary_password": password},
        }
    finally:
        session.close()
    return result


def set_status(org_id: str, status: str, member_limit: int | None = None) -> dict:
    """Platform admin: suspend or reactivate an organization, or change its limit."""
    if status not in ("active", "suspended"):
        raise OrgError(400, "Status must be active or suspended.")
    session = db.get_session()
    try:
        org = session.get(Organization, org_id)
        if org is None:
            raise OrgError(404, "No such organization.")
        org.status = status
        if member_limit is not None:
            org.member_limit = max(1, min(int(member_limit), 100000))
        session.commit()
        return _org_dict(org, _count(session, org.id))
    finally:
        session.close()


def find_code(session, code: str) -> tuple[Organization, OrgJoinCode | None]:
    """The organization (and its join code row) for a code someone typed."""
    entry = session.query(OrgJoinCode).filter_by(code=code).first()
    if entry is not None:
        if not entry.active:
            raise OrgError(410, "This join code is no longer active. Ask your organization for a new one.")
        org = session.get(Organization, entry.organization_id)
    else:
        # Codes from before join codes had their own table.
        org = session.query(Organization).filter_by(join_code=code).first()
    if org is None:
        raise OrgError(404, "No organization has that join code.")
    if (org.status or "active") != "active":
        raise OrgError(403, "This organization is not accepting members right now.")
    return org, entry


def clean_class_value(value: str | None, limit: int) -> str | None:
    cleaned = " ".join(str(value or "").split())[:limit]
    return cleaned or None


def join(user_id: str, join_code: str, share_progress: bool = True, department: str | None = None,
         year: str | None = None, section: str | None = None) -> dict:
    """Joining is consent to share (see the module docstring); share_progress
    is accepted for older clients and ignored. A code that carries a class
    places the learner there; otherwise their own choices are used."""
    from app.organizations import classes

    code = join_code.strip().upper()
    session = db.get_session()
    try:
        if _membership(session, user_id) is not None:
            raise OrgError(409, "You already belong to an organization.")
        org, entry = find_code(session, code)
        if _count(session, org.id) >= org.member_limit:
            raise OrgError(409, "This organization has reached its member limit.")
        chosen = {
            "department": entry.department if entry and entry.department else clean_class_value(department, 120),
            "year": entry.year if entry and entry.year else clean_class_value(year, 40),
            "section": entry.section if entry and entry.section else clean_class_value(section, 40),
        }
        session.add(OrganizationMember(
            organization_id=org.id, user_id=user_id, role="member", progress_shared_at=datetime.utcnow(),
            join_code_id=entry.id if entry else None, **chosen,
        ))
        classes.remember_options(session, org.id, chosen)
        session.commit()
    finally:
        session.close()
    return my_organization(user_id)


def set_sharing(user_id: str, share: bool) -> dict:
    session = db.get_session()
    try:
        member = _membership(session, user_id)
        if member is None:
            raise OrgError(404, "You are not part of an organization.")
        member.progress_shared_at = datetime.utcnow() if share else None
        session.commit()
    finally:
        session.close()
    return my_organization(user_id)


def leave(user_id: str) -> None:
    session = db.get_session()
    try:
        member = _membership(session, user_id)
        if member is None:
            raise OrgError(404, "You are not part of an organization.")
        if member.role == "owner":
            owners = session.query(OrganizationMember).filter_by(organization_id=member.organization_id, role="owner").count()
            if owners <= 1:
                raise OrgError(409, "Make another member an owner before leaving, or delete the organization.")
        session.delete(member)
        session.commit()
    finally:
        session.close()


def _require_admin(session, user_id: str, org_id: str) -> OrganizationMember:
    """This organization's owner or admin -- or DigiDARA's platform admin,
    who acts as an owner of every organization."""
    member = _membership(session, user_id)
    org = session.get(Organization, org_id)
    if org is None:
        raise OrgError(404, "No such organization.")
    if member is not None and member.organization_id == org_id and member.role in ADMIN_ROLES:
        if (org.status or "active") != "active":
            raise OrgError(403, "This organization is suspended. Contact DigiDARA.")
        return member
    user = session.get(User, user_id)
    if user is not None and user.is_admin:
        # Not added to the session: it only carries the owner role.
        return OrganizationMember(organization_id=org_id, user_id=user_id, role="owner")
    raise OrgError(403, "Only this organization's admins can do that.")


def require_admin(user_id: str, org_id: str) -> str:
    """Raises unless the user may manage this organization; returns their role."""
    session = db.get_session()
    try:
        return _require_admin(session, user_id, org_id).role
    finally:
        session.close()


def _member_in_org(session, org_id: str, member_id: str) -> OrganizationMember:
    member = session.get(OrganizationMember, member_id)
    if member is None or member.organization_id != org_id:
        raise OrgError(404, "No such member in this organization.")
    return member


def add_members(admin_id: str, org_id: str, rows: list[dict]) -> list[dict]:
    """Create (or attach) member accounts. A new account gets a one-time
    password, returned here once for the admin to hand over; the learner
    accepts the platform consent and chooses whether to share progress at
    first sign-in."""
    if not rows:
        raise OrgError(400, "Add at least one member.")
    if len(rows) > MAX_BULK:
        raise OrgError(400, f"Add at most {MAX_BULK} members at a time.")
    session = db.get_session()
    results: list[dict] = []
    try:
        _require_admin(session, admin_id, org_id)
        org = session.get(Organization, org_id)
        room = org.member_limit - _count(session, org_id)
        for row in rows:
            email = str(row.get("email") or "").strip().lower()
            name = " ".join(str(row.get("name") or "").split())[:255] or email.split("@")[0]
            external_id = (str(row.get("external_id") or "").strip()[:64]) or None
            if not _EMAIL.match(email):
                results.append({"email": email, "status": "invalid_email"})
                continue
            if room <= 0:
                results.append({"email": email, "status": "limit_reached"})
                continue
            user = session.query(User).filter_by(email=email).first()
            password = None
            if user is None:
                password = _temporary_password()
                # consent_accepted_at stays empty: the learner gives their own
                # consent at first sign-in (POST /learner/consent).
                user = User(name=name, email=email, password_hash=hash_password(password))
                session.add(user)
                session.flush()
                status = "created"
            else:
                existing = _membership(session, user.id)
                if existing is not None:
                    results.append({"email": email, "status": "already_in_organization" if existing.organization_id == org_id else "in_another_organization"})
                    continue
                status = "attached"
            session.add(OrganizationMember(organization_id=org_id, user_id=user.id, role="member", external_id=external_id))
            room -= 1
            results.append({"email": email, "name": name, "status": status, "temporary_password": password})
        session.commit()
    finally:
        session.close()
    return results


def _last_active(session, user_ids: list[str]) -> dict[str, datetime]:
    """Each learner's latest activity: an agent call or a chat update."""
    from sqlalchemy import func

    from app.models import Conversation, TokenUsageEvent

    if not user_ids:
        return {}
    latest: dict[str, datetime] = {}
    for model, column in ((TokenUsageEvent, TokenUsageEvent.created_at), (Conversation, Conversation.updated_at)):
        for user_id, when in (session.query(model.user_id, func.max(column)).filter(model.user_id.in_(user_ids))
                              .group_by(model.user_id).all()):
            if when and (user_id not in latest or when > latest[user_id]):
                latest[user_id] = when
    return latest


def members(admin_id: str, org_id: str) -> list[dict]:
    session = db.get_session()
    try:
        _require_admin(session, admin_id, org_id)
        rows = (
            session.query(OrganizationMember, User)
            .join(User, User.id == OrganizationMember.user_id)
            .filter(OrganizationMember.organization_id == org_id)
            .order_by(User.name).all()
        )
        codes = {c.id: c for c in session.query(OrgJoinCode).filter_by(organization_id=org_id).all()}
        shared_ids = [m.user_id for m, _ in rows if m.progress_shared_at is not None]
        last_active = _last_active(session, shared_ids)
    finally:
        session.close()
    snapshots = readiness_service.latest_for(shared_ids)
    result = []
    for member, user in rows:
        code = codes.get(member.join_code_id or "")
        entry = {
            "member_id": member.id, "user_id": user.id, "name": user.name, "email": user.email,
            "role": member.role, "external_id": member.external_id,
            "joined_at": member.created_at.isoformat() if member.created_at else None,
            "progress_shared": member.progress_shared_at is not None,
            "has_signed_in": user.consent_accepted_at is not None,
            **_class_of(member),
            "join_code": {"id": code.id, "code": code.code, "label": code.label} if code else None,
            "last_active_at": last_active[user.id].isoformat() if user.id in last_active else None,
        }
        if member.progress_shared_at is not None:
            snapshot = snapshots.get(user.id)
            entry["readiness"] = None if snapshot is None else {
                "overall": snapshot.overall, "band": snapshot.band,
                "band_label": readiness_service.BAND_LABELS.get(snapshot.band, snapshot.band),
                "computed_at": snapshot.computed_at.isoformat(),
                "areas": readiness_service.area_scores(snapshot),
            }
            entry["levels"] = {name: data["level"] for name, data in learner_service.get_levels(user.id).items()}
            entry["profile"] = learner_service.get_profile(user.id)
        result.append(entry)
    return result


def summary(admin_id: str, org_id: str) -> dict:
    """Counts for the dashboard header: members by readiness band, and by
    level for each agent (shared members only)."""
    rows = members(admin_id, org_id)
    shared = [r for r in rows if r["progress_shared"]]
    bands: dict[str, int] = {}
    for row in shared:
        band = (row.get("readiness") or {}).get("band", "not_started")
        bands[band] = bands.get(band, 0) + 1
    by_level: dict[str, dict[str, int]] = {
        agent: {level: 0 for level in level_rules.LEVELS} for agent in level_rules.LEVELED_AGENTS
    }
    for row in shared:
        for agent, level in (row.get("levels") or {}).items():
            if agent in by_level and level in by_level[agent]:
                by_level[agent][level] += 1
    scores = [r["readiness"]["overall"] for r in shared if r.get("readiness") and r["readiness"]["overall"] is not None]
    return {
        "members": len(rows), "sharing": len(shared), "signed_in": sum(1 for r in rows if r["has_signed_in"]),
        "average_readiness": round(sum(scores) / len(scores), 1) if scores else None,
        "bands": bands, "levels": by_level,
        "band_labels": readiness_service.BAND_LABELS, "level_labels": level_rules.LEVEL_LABELS,
        "agent_labels": level_rules.LEVELED_AGENTS,
    }


def update_member(admin_id: str, org_id: str, member_id: str, role: str | None, external_id: str | None,
                  class_fields: dict | None = None) -> None:
    from app.organizations import classes

    session = db.get_session()
    try:
        admin = _require_admin(session, admin_id, org_id)
        member = _member_in_org(session, org_id, member_id)
        if class_fields:
            for field, limit in (("department", 120), ("year", 40), ("section", 40)):
                if field in class_fields:
                    setattr(member, field, clean_class_value(class_fields[field], limit))
            classes.remember_options(session, org_id, _class_of(member))
        if role is not None:
            if role not in ROLES:
                raise OrgError(400, f"Role must be one of: {', '.join(ROLES)}.")
            if admin.role != "owner":
                raise OrgError(403, "Only an owner can change roles.")
            if member.role == "owner" and role != "owner":
                owners = session.query(OrganizationMember).filter_by(organization_id=org_id, role="owner").count()
                if owners <= 1:
                    raise OrgError(409, "An organization needs at least one owner.")
            member.role = role
        if external_id is not None:
            member.external_id = external_id.strip()[:64] or None
        session.commit()
    finally:
        session.close()


def remove_member(admin_id: str, org_id: str, member_id: str) -> None:
    """Takes the learner out of the organization; their account stays."""
    session = db.get_session()
    try:
        _require_admin(session, admin_id, org_id)
        member = _member_in_org(session, org_id, member_id)
        if member.role == "owner":
            raise OrgError(409, "Change this owner's role before removing them.")
        session.delete(member)
        session.commit()
    finally:
        session.close()


def shared_member_user_id(admin_id: str, org_id: str, member_id: str) -> str:
    """The member's user id, only if they share their progress with the org."""
    session = db.get_session()
    try:
        _require_admin(session, admin_id, org_id)
        member = _member_in_org(session, org_id, member_id)
        if member.progress_shared_at is None:
            raise OrgError(403, "This member has not agreed to share their progress.")
        return member.user_id
    finally:
        session.close()


def rotate_join_code(admin_id: str, org_id: str) -> dict:
    session = db.get_session()
    try:
        admin = _require_admin(session, admin_id, org_id)
        if admin.role != "owner":
            raise OrgError(403, "Only an owner can change the join code.")
        org = session.get(Organization, org_id)
        org.join_code = _new_join_code()
        session.commit()
    finally:
        session.close()
    return my_organization(admin_id)


def list_all() -> list[dict]:
    """Every organization with its owners, for the platform admin."""
    session = db.get_session()
    try:
        result = []
        for org in session.query(Organization).order_by(Organization.name).all():
            owners = (session.query(User.name, User.email).join(OrganizationMember, OrganizationMember.user_id == User.id)
                      .filter(OrganizationMember.organization_id == org.id, OrganizationMember.role.in_(ADMIN_ROLES)).all())
            codes = session.query(OrgJoinCode).filter_by(organization_id=org.id, active=True).count()
            result.append({**_org_dict(org, _count(session, org.id)), "active_codes": codes,
                           "admins": [{"name": name, "email": email} for name, email in owners]})
        return result
    finally:
        session.close()


def export_data(user_id: str) -> dict | None:
    data = my_organization(user_id)
    if data is None:
        return None
    data["organization"].pop("join_code", None)
    return data


def purge(user_id: str) -> None:
    from app.models import OrgAccessLog

    session = db.get_session()
    try:
        session.query(OrgAccessLog).filter_by(subject_user_id=user_id).delete()
        session.query(OrganizationMember).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()

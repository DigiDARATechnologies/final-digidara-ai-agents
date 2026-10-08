"""Organizations: a college or company registers, adds its learners, and
monitors their readiness and levels.

Two ways in for a learner: an admin creates the account (bulk add, with a
one-time password the admin hands over), or the learner joins with the
organization's join code. Either way the organization only sees a member's
readiness and levels after that member agrees to share them -- their own
consent, recorded in progress_shared_at (DPDP Act 2023).
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime

from app import db
from app.auth.security import hash_password
from app.learner import levels as level_rules
from app.learner import service as learner_service
from app.models import Organization, OrganizationMember, User
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
        "member_limit": org.member_limit, "member_count": member_count,
        "created_at": org.created_at.isoformat() if org.created_at else None,
    }


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
        }
    finally:
        session.close()


def create(user_id: str, name: str, kind: str) -> dict:
    name = " ".join(name.split())[:255]
    if len(name) < 2:
        raise OrgError(400, "Enter the organization's name.")
    session = db.get_session()
    try:
        if _membership(session, user_id) is not None:
            raise OrgError(409, "You already belong to an organization. Leave it before registering a new one.")
        org = Organization(name=name, kind=kind if kind in KINDS else "other", join_code=_new_join_code(), created_by=user_id)
        session.add(org)
        session.flush()
        session.add(OrganizationMember(organization_id=org.id, user_id=user_id, role="owner"))
        session.commit()
    finally:
        session.close()
    return my_organization(user_id)


def join(user_id: str, join_code: str, share_progress: bool) -> dict:
    code = join_code.strip().upper()
    session = db.get_session()
    try:
        if _membership(session, user_id) is not None:
            raise OrgError(409, "You already belong to an organization.")
        org = session.query(Organization).filter_by(join_code=code).first()
        if org is None:
            raise OrgError(404, "No organization has that join code.")
        if _count(session, org.id) >= org.member_limit:
            raise OrgError(409, "This organization has reached its member limit.")
        session.add(OrganizationMember(
            organization_id=org.id, user_id=user_id, role="member",
            progress_shared_at=datetime.utcnow() if share_progress else None,
        ))
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
    member = _membership(session, user_id)
    if member is None or member.organization_id != org_id or member.role not in ADMIN_ROLES:
        raise OrgError(403, "Only this organization's admins can do that.")
    return member


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
    finally:
        session.close()
    shared_ids = [m.user_id for m, _ in rows if m.progress_shared_at is not None]
    snapshots = readiness_service.latest_for(shared_ids)
    result = []
    for member, user in rows:
        entry = {
            "member_id": member.id, "user_id": user.id, "name": user.name, "email": user.email,
            "role": member.role, "external_id": member.external_id,
            "joined_at": member.created_at.isoformat() if member.created_at else None,
            "progress_shared": member.progress_shared_at is not None,
            "has_signed_in": user.consent_accepted_at is not None,
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


def update_member(admin_id: str, org_id: str, member_id: str, role: str | None, external_id: str | None) -> None:
    session = db.get_session()
    try:
        admin = _require_admin(session, admin_id, org_id)
        member = _member_in_org(session, org_id, member_id)
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
    """Every organization, for the platform admin."""
    session = db.get_session()
    try:
        return [_org_dict(org, _count(session, org.id)) for org in session.query(Organization).order_by(Organization.name).all()]
    finally:
        session.close()


def export_data(user_id: str) -> dict | None:
    data = my_organization(user_id)
    if data is None:
        return None
    data["organization"].pop("join_code", None)
    return data


def purge(user_id: str) -> None:
    session = db.get_session()
    try:
        session.query(OrganizationMember).filter_by(user_id=user_id).delete()
        session.commit()
    finally:
        session.close()

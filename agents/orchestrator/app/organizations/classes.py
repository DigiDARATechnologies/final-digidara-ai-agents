"""Join codes and classes: an organization's departments, years and sections.

An organization admin creates as many join codes as they need. A code can
carry a class (department, year, section -- each optional): everyone who
joins with it is placed there. With a code that leaves them open, the
learner picks from three optional dropdowns, each of which can take a new
value ("+ Add new"); new values are remembered for the next learner and for
the admin's filters.
"""
from __future__ import annotations

from sqlalchemy import func

from app import db
from app.models import Organization, OrganizationMember, OrgJoinCode, OrgOption
from app.organizations.service import (
    OrgError,
    _new_join_code,
    _require_admin,
    clean_class_value,
    find_code,
)

KINDS = ("department", "year", "section")
LIMITS = {"department": 120, "year": 40, "section": 40}
# Offered before an organization has added its own.
DEFAULT_OPTIONS = {
    "department": [],
    "year": ["1st year", "2nd year", "3rd year", "4th year"],
    "section": ["A", "B", "C"],
}
MAX_CODES = 500


def remember_options(session, org_id: str, values: dict) -> None:
    """Adds any new department/year/section value to the organization's lists."""
    for kind in KINDS:
        value = values.get(kind)
        if not value:
            continue
        exists = session.query(OrgOption).filter(
            OrgOption.organization_id == org_id, OrgOption.kind == kind, func.lower(OrgOption.value) == value.lower(),
        ).first()
        if exists is None:
            session.add(OrgOption(organization_id=org_id, kind=kind, value=value))


def _options(session, org_id: str) -> dict[str, list[str]]:
    rows = session.query(OrgOption).filter_by(organization_id=org_id).order_by(OrgOption.value).all()
    result = {kind: list(DEFAULT_OPTIONS[kind]) for kind in KINDS}
    for row in rows:
        if row.kind in result and row.value.lower() not in {v.lower() for v in result[row.kind]}:
            result[row.kind].append(row.value)
    return result


def options(user_id: str, org_id: str) -> dict[str, list[str]]:
    session = db.get_session()
    try:
        _require_admin(session, user_id, org_id)
        return _options(session, org_id)
    finally:
        session.close()


def add_option(user_id: str, org_id: str, kind: str, value: str) -> dict[str, list[str]]:
    if kind not in KINDS:
        raise OrgError(400, "Choose department, year or section.")
    cleaned = clean_class_value(value, LIMITS[kind])
    if not cleaned:
        raise OrgError(400, f"Enter the {kind}.")
    session = db.get_session()
    try:
        _require_admin(session, user_id, org_id)
        remember_options(session, org_id, {kind: cleaned})
        session.commit()
        return _options(session, org_id)
    finally:
        session.close()


def _ensure_general_code(session, org: Organization) -> None:
    """Organizations from before join codes had their own table keep their code."""
    if org.join_code and session.query(OrgJoinCode).filter_by(code=org.join_code).first() is None:
        session.add(OrgJoinCode(organization_id=org.id, code=org.join_code, label="General"))
        session.flush()


def _code_dict(entry: OrgJoinCode, members: int) -> dict:
    return {
        "id": entry.id, "code": entry.code, "label": entry.label or "", "department": entry.department,
        "year": entry.year, "section": entry.section, "active": bool(entry.active), "members": members,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def list_codes(user_id: str, org_id: str) -> list[dict]:
    session = db.get_session()
    try:
        _require_admin(session, user_id, org_id)
        _ensure_general_code(session, session.get(Organization, org_id))
        session.commit()
        counts = dict(
            session.query(OrganizationMember.join_code_id, func.count(OrganizationMember.id))
            .filter(OrganizationMember.organization_id == org_id).group_by(OrganizationMember.join_code_id).all()
        )
        codes = session.query(OrgJoinCode).filter_by(organization_id=org_id).order_by(OrgJoinCode.created_at).all()
        return [_code_dict(entry, counts.get(entry.id, 0)) for entry in codes]
    finally:
        session.close()


def create_code(user_id: str, org_id: str, label: str, department: str | None, year: str | None, section: str | None) -> dict:
    values = {
        "department": clean_class_value(department, 120),
        "year": clean_class_value(year, 40),
        "section": clean_class_value(section, 40),
    }
    session = db.get_session()
    try:
        _require_admin(session, user_id, org_id)
        if session.query(OrgJoinCode).filter_by(organization_id=org_id).count() >= MAX_CODES:
            raise OrgError(409, f"An organization can have at most {MAX_CODES} join codes.")
        code = _new_join_code()
        while session.query(OrgJoinCode).filter_by(code=code).first() is not None:
            code = _new_join_code()
        default_label = " · ".join(v for v in values.values() if v) or "General"
        entry = OrgJoinCode(organization_id=org_id, code=code, label=clean_class_value(label, 120) or default_label,
                            created_by=user_id, **values)
        session.add(entry)
        remember_options(session, org_id, values)
        session.commit()
        return _code_dict(entry, 0)
    finally:
        session.close()


def set_code_active(user_id: str, org_id: str, code_id: str, active: bool) -> dict:
    session = db.get_session()
    try:
        _require_admin(session, user_id, org_id)
        entry = session.get(OrgJoinCode, code_id)
        if entry is None or entry.organization_id != org_id:
            raise OrgError(404, "No such join code in this organization.")
        entry.active = active
        session.commit()
        members = session.query(OrganizationMember).filter_by(join_code_id=entry.id).count()
        return _code_dict(entry, members)
    finally:
        session.close()


def preview(code: str) -> dict:
    """What a learner sees after typing a code, before joining: the
    organization's name, the class the code places them in, and the
    dropdown choices for anything it leaves open."""
    session = db.get_session()
    try:
        org, entry = find_code(session, code.strip().upper())
        return {
            "organization": {"name": org.name, "kind": org.kind},
            "code": {
                "label": entry.label if entry else "General",
                "department": entry.department if entry else None,
                "year": entry.year if entry else None,
                "section": entry.section if entry else None,
            },
            "options": _options(session, org.id),
        }
    finally:
        session.close()

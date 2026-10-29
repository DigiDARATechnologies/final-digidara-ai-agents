"""An organization's student list, and who may join.

Staff upload a list of students (an Excel .xlsx or a .csv with name, mobile
and email columns) and make join codes. A learner signs in and enters a join
code: if their verified email is on the list of the staff member who made
that code, they join at once; anyone else becomes a join request, with no
access and nothing shared, until staff approve or decline it. An owner's or
admin's code matches any list in the organization.

Joining with a code is the learner's consent: they saw on the join screen
what the organization can see. Approving a request counts too: they agreed
when they asked. Staff see only their own lists, codes and requests.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime

from app import db
from app.models import Organization, OrganizationMember, OrgJoinCode, OrgJoinRequest, OrgRosterEntry, User
from app.organizations.service import (
    OrgError,
    _EMAIL,
    _count,
    _membership,
    is_full,
    _require_admin,
    clean_class_value,
)

MAX_ROWS = 5000
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
_HEADERS = {
    "email": ("email", "e-mail", "mail", "email id", "emailid", "email address"),
    "name": ("name", "student name", "full name", "student"),
    "mobile": ("mobile", "mobile number", "mobile no", "phone", "phone number", "contact", "contact number", "whatsapp"),
}


# --- reading the uploaded file -------------------------------------------------

def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)        # Excel stores 9876543210 as 9876543210.0
    return " ".join(str(value).split())


def _column_map(header: list[str]) -> dict[str, int] | None:
    """Which column holds email, name and mobile; None when the first row is
    not a header (then the columns are guessed from the data). A row with an
    email address in it is data, even when the address contains "mail"."""
    if any("@" in h for h in header):
        return None
    names = [re.sub(r"[^a-z ]", "", h.lower()).strip() for h in header]
    found = {}
    for field, aliases in _HEADERS.items():
        for index, name in enumerate(names):
            if name in aliases or (field == "email" and "mail" in name) or (field == "mobile" and ("mobile" in name or "phone" in name)):
                found.setdefault(field, index)
                break
    return found if "email" in found else None


def _guess_columns(rows: list[list[str]]) -> dict[str, int]:
    """No header: the column with @ is the email, the one with 10+ digits the
    mobile, and the first other text column the name."""
    sample = rows[:20]
    width = max((len(r) for r in sample), default=0)
    found: dict[str, int] = {}
    for index in range(width):
        values = [r[index] for r in sample if index < len(r) and r[index]]
        if not values:
            continue
        if "email" not in found and sum("@" in v for v in values) >= len(values) / 2:
            found["email"] = index
        elif "mobile" not in found and sum(len(re.sub(r"\D", "", v)) >= 10 for v in values) >= len(values) / 2:
            found["mobile"] = index
        elif "name" not in found:
            found["name"] = index
    return found


def parse_upload(filename: str, data: bytes) -> list[dict]:
    """Rows of {name, mobile, email} from an .xlsx or .csv file."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise OrgError(413, "The file is larger than 5 MB.")
    name = (filename or "").lower()
    if name.endswith(".xlsx") or data[:2] == b"PK":
        rows = _xlsx_rows(data)
    elif name.endswith((".csv", ".txt")):
        text = data.decode("utf-8-sig", errors="replace")
        rows = [[_cell(c) for c in row] for row in csv.reader(io.StringIO(text))]
    elif name.endswith(".xls"):
        raise OrgError(400, "Old .xls files are not supported. In Excel choose File > Save As > Excel Workbook (.xlsx), or CSV.")
    else:
        raise OrgError(400, "Upload an Excel (.xlsx) or CSV file.")
    rows = [r for r in rows if any(r)]
    if not rows:
        raise OrgError(400, "The file has no rows.")
    columns = _column_map(rows[0])
    if columns is not None:
        rows = rows[1:]
    else:
        columns = _guess_columns(rows)
        if "email" not in columns:
            raise OrgError(400, "No email column found. Add a header row with Name, Mobile and Email.")
    if len(rows) > MAX_ROWS:
        raise OrgError(400, f"Upload at most {MAX_ROWS} students at a time.")

    def pick(row: list[str], field: str) -> str:
        index = columns.get(field)
        return row[index] if index is not None and index < len(row) else ""

    return [{"name": pick(r, "name"), "mobile": pick(r, "mobile"), "email": pick(r, "email")} for r in rows]


def _xlsx_rows(data: bytes) -> list[list[str]]:
    from openpyxl import load_workbook

    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - any unreadable workbook is the user's file, not a server error
        raise OrgError(400, "This Excel file could not be read. Save it again as .xlsx or CSV.") from exc
    try:
        sheet = book.worksheets[0]
        rows = []
        for row in sheet.iter_rows(values_only=True):
            rows.append([_cell(c) for c in row])
            if len(rows) > MAX_ROWS + 1:
                break
        return rows
    finally:
        book.close()


# --- the list --------------------------------------------------------------

def _clean_mobile(value: str) -> str:
    digits = re.sub(r"[^\d+]", "", value or "")
    return digits[:32]


def upload(staff_id: str, org_id: str, rows: list[dict]) -> dict:
    """Adds the rows to the organization's list (an email already there gets
    the new name and mobile), and lets listed learners who already have a
    verified account in no organization join now."""
    session = db.get_session()
    try:
        _require_admin(session, staff_id, org_id)
        existing = {e.email: e for e in session.query(OrgRosterEntry).filter_by(organization_id=org_id).all()}
        added = updated = 0
        invalid: list[dict] = []
        seen: set[str] = set()
        for number, row in enumerate(rows, start=2):
            email = str(row.get("email") or "").strip().lower()
            if not _EMAIL.match(email) or len(email) > 255:
                invalid.append({"row": number, "email": email, "reason": "not a valid email"})
                continue
            if email in seen:
                continue
            seen.add(email)
            name = " ".join(str(row.get("name") or "").split())[:255]
            mobile = _clean_mobile(str(row.get("mobile") or ""))
            entry = existing.get(email)
            if entry is None:
                session.add(OrgRosterEntry(organization_id=org_id, email=email, name=name, mobile=mobile, uploaded_by=staff_id))
                added += 1
            else:
                entry.name = name or entry.name
                entry.mobile = mobile or entry.mobile
                # A student is on one list: the latest staff member to upload them.
                entry.uploaded_by = staff_id
                updated += 1
        session.commit()
    finally:
        session.close()
    approved = _approve_listed_requests(org_id, seen)
    return {"added": added, "updated": updated, "invalid": invalid[:200], "invalid_count": len(invalid),
            "joined": 0, "approved": approved}


def entries(staff_id: str, org_id: str) -> list[dict]:
    """The list, with where each student stands."""
    session = db.get_session()
    try:
        viewer = _require_admin(session, staff_id, org_id)
        rows = session.query(OrgRosterEntry).filter_by(organization_id=org_id)
        if viewer.role == "staff":
            rows = rows.filter_by(uploaded_by=staff_id)        # staff see the lists they uploaded
        rows = rows.order_by(OrgRosterEntry.name).all()
        emails = [r.email for r in rows]
        users = {u.email: u for u in session.query(User).filter(User.email.in_(emails)).all()} if emails else {}
        user_ids = [u.id for u in users.values()]
        members = {m.user_id: m for m in session.query(OrganizationMember).filter(OrganizationMember.user_id.in_(user_ids)).all()} if user_ids else {}
        result = []
        for r in rows:
            user = users.get(r.email)
            member = members.get(user.id) if user else None
            status = ("joined" if member and member.organization_id == org_id else "other_organization" if member
                      else "not_signed_up" if user is None else "waiting")
            result.append({"id": r.id, "name": r.name, "email": r.email, "mobile": r.mobile, "status": status,
                           "uploaded_by": r.uploaded_by, "added_at": r.created_at.isoformat() if r.created_at else None})
        return result
    finally:
        session.close()


def remove_entry(staff_id: str, org_id: str, entry_id: str) -> None:
    """Takes an email off the list. A student who already joined stays."""
    session = db.get_session()
    try:
        viewer = _require_admin(session, staff_id, org_id)
        entry = session.get(OrgRosterEntry, entry_id)
        if entry is None or entry.organization_id != org_id or (viewer.role == "staff" and entry.uploaded_by != staff_id):
            raise OrgError(404, "That student is not on the list.")
        session.delete(entry)
        session.commit()
    finally:
        session.close()


def _code_owner(session, org_id: str, code: OrgJoinCode | None) -> str | None:
    """The staff member whose list a join code checks: its creator when they
    are staff; None (any list in the organization) for an owner's or admin's
    code, or the organization's general code."""
    if code is None or not code.created_by:
        return None
    creator = session.query(OrganizationMember).filter_by(user_id=code.created_by, organization_id=org_id).first()
    return code.created_by if creator is not None and creator.role == "staff" else None


def is_listed(session, org_id: str, user: User, code: OrgJoinCode | None = None) -> bool:
    """On the student list behind this join code, with an email the learner
    has proved. A staff member's code matches only the list they uploaded."""
    if not user.email_verified and not user.google_id:
        return False
    query = session.query(OrgRosterEntry).filter_by(organization_id=org_id, email=(user.email or "").lower())
    owner = _code_owner(session, org_id, code)
    if owner is not None:
        query = query.filter_by(uploaded_by=owner)
    return query.first() is not None


# --- joining -----------------------------------------------------------------

def _add_member(session, org: Organization, user_id: str, shared: bool, fields: dict | None = None, code_id: str | None = None) -> bool:
    if _membership(session, user_id) is not None or is_full(org, _count(session, org.id)):
        return False
    session.add(OrganizationMember(organization_id=org.id, user_id=user_id, role="member",
                                   progress_shared_at=datetime.utcnow() if shared else None,
                                   join_code_id=code_id, **(fields or {})))
    drop_request(session, user_id)
    return True


def _approve_listed_requests(org_id: str, emails: set[str]) -> int:
    """A waiting request from someone now on the list is approved."""
    session = db.get_session()
    try:
        ids = []
        for request, user in (session.query(OrgJoinRequest, User).join(User, User.id == OrgJoinRequest.user_id)
                              .filter(OrgJoinRequest.organization_id == org_id).all()):
            code = session.get(OrgJoinCode, request.join_code_id) if request.join_code_id else None
            # Only a request whose own join code now finds the learner on its list.
            if (user.email or "").lower() in emails and is_listed(session, org_id, user, code):
                ids.append(request.id)
    finally:
        session.close()
    approved = 0
    for request_id in ids:
        try:
            _decide(None, org_id, request_id, True)
            approved += 1
        except OrgError:
            pass
    return approved


def request_to_join(session, org: Organization, user_id: str, code: OrgJoinCode | None, fields: dict) -> None:
    existing = session.query(OrgJoinRequest).filter_by(user_id=user_id).first()
    if existing is not None:
        if existing.organization_id == org.id:
            raise OrgError(409, "Your request to join is already waiting for approval.")
        session.delete(existing)        # asking a different organization replaces the old request
        session.flush()
    session.add(OrgJoinRequest(organization_id=org.id, user_id=user_id, join_code_id=code.id if code else None, **fields))


def drop_request(session, user_id: str) -> None:
    session.query(OrgJoinRequest).filter_by(user_id=user_id).delete()


def pending_for(user_id: str) -> dict | None:
    """The learner's own waiting request, for their Organization page."""
    session = db.get_session()
    try:
        request = session.query(OrgJoinRequest).filter_by(user_id=user_id).first()
        if request is None:
            return None
        org = session.get(Organization, request.organization_id)
        return {"id": request.id, "organization": {"id": org.id, "name": org.name} if org else None,
                "requested_at": request.created_at.isoformat() if request.created_at else None}
    finally:
        session.close()


def cancel_request(user_id: str) -> None:
    session = db.get_session()
    try:
        drop_request(session, user_id)
        session.commit()
    finally:
        session.close()


def requests(staff_id: str, org_id: str) -> list[dict]:
    session = db.get_session()
    try:
        viewer = _require_admin(session, staff_id, org_id)
        query = (session.query(OrgJoinRequest, User).join(User, User.id == OrgJoinRequest.user_id)
                 .filter(OrgJoinRequest.organization_id == org_id))
        if viewer.role == "staff":
            # Staff decide on requests made with their own join codes.
            mine = [c.id for c in session.query(OrgJoinCode.id).filter_by(organization_id=org_id, created_by=staff_id).all()]
            query = query.filter(OrgJoinRequest.join_code_id.in_(mine or [""]))
        rows = query.order_by(OrgJoinRequest.created_at).all()
        codes = {c.id: c.code for c in session.query(OrgJoinCode).filter_by(organization_id=org_id).all()}
        return [{"id": r.id, "name": u.name, "email": u.email, "department": r.department, "year": r.year,
                 "section": r.section, "join_code": codes.get(r.join_code_id or ""),
                 "requested_at": r.created_at.isoformat() if r.created_at else None} for r, u in rows]
    finally:
        session.close()


def decide(staff_id: str, org_id: str, request_id: str, approve: bool) -> None:
    _decide(staff_id, org_id, request_id, approve)


def _decide(staff_id: str | None, org_id: str, request_id: str, approve: bool) -> None:
    from app.organizations import classes

    session = db.get_session()
    try:
        viewer = _require_admin(session, staff_id, org_id) if staff_id is not None else None
        request = session.get(OrgJoinRequest, request_id)
        if request is None or request.organization_id != org_id:
            raise OrgError(404, "That request is no longer waiting.")
        if viewer is not None and viewer.role == "staff":
            code = session.get(OrgJoinCode, request.join_code_id) if request.join_code_id else None
            if code is None or code.created_by != staff_id:
                raise OrgError(404, "That request was made with another staff member's join code.")
        if approve:
            org = session.get(Organization, org_id)
            fields = {"department": clean_class_value(request.department, 120), "year": clean_class_value(request.year, 40),
                      "section": clean_class_value(request.section, 40)}
            if _membership(session, request.user_id) is not None:
                session.delete(request)
            elif not _add_member(session, org, request.user_id, shared=True, fields=fields, code_id=request.join_code_id):
                raise OrgError(409, "This organization has reached its member limit.")
            else:
                classes.remember_options(session, org_id, fields)
        else:
            session.delete(request)
        session.commit()
    finally:
        session.close()


def template_xlsx() -> bytes:
    """The student list template: the three columns with two example rows."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    book = Workbook()
    sheet = book.active
    sheet.title = "Students"
    sheet.append(["Name", "Mobile", "Email"])
    sheet.append(["Priya Kumar", "9876543210", "priya.kumar@example.com"])
    sheet.append(["Arun S", "9123456780", "arun.s@example.com"])
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2851D8")
    for column, width in (("A", 28), ("B", 18), ("C", 36)):
        sheet.column_dimensions[column].width = width
    # Mobile numbers as text, so Excel keeps leading zeros and does not show 9.87E+09.
    for row in sheet.iter_rows(min_row=2, min_col=2, max_col=2):
        for cell in row:
            cell.number_format = "@"
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()

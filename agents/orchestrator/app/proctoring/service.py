"""Proctoring for Hard/Professional mock interviews and capstone vivas, and
assessment links that organization admins hand out.

A proctored sitting (ProctorSession) starts only after the learner agrees on
the consent screen (DPDP): the browser then watches for leaving the tab or
full screen and for copy/paste, and sends a small webcam still now and then.
Each still is checked for faces (no face, more than one, a phone) by the
vision model. Every finding is a ProctorEvent with a penalty; the integrity
score is 100 minus the penalties. Leaving the tab or full screen, and
reloading the page mid-test, are warnings: one more than the session allows
ends the test.

An assessment is a mock interview an organization admin configures (round,
role or topic, number of questions, level, which checks run) and shares as a
link. The gateway applies the admin's settings to the interview the learner
starts, and records the interview's score here when it ends, so neither can
be changed from the browser.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from app import db
from app.learner import levels as level_rules
from app.models import (
    Assessment,
    Organization,
    OrganizationMember,
    OrgAccessLog,
    ProctorEvent,
    ProctorSession,
    ProctorSnapshot,
    User,
)
# A module, not names: organizations -> readiness -> gateway -> here is a cycle,
# so its names are looked up when called, never at import.
from app.organizations import service as org_service

logger = logging.getLogger("orchestrator.proctoring")

PROCTORED_AGENTS = ("mock_interview_agent", "capstone_project_agent")
CHECKS = ("tab", "fullscreen", "copy_paste", "webcam", "face")
DEFAULT_MAX_WARNINGS = 3
# Every check on: Hard/Professional practice sittings.
FULL_SETTINGS = {**{check: True for check in CHECKS}, "max_warnings": DEFAULT_MAX_WARNINGS}

# Points off the integrity score for each finding, and which check it belongs to.
PENALTIES: dict[str, tuple[int, str]] = {
    "focus_lost": (5, "tab"),
    "fullscreen_exit": (5, "fullscreen"),
    "copy": (3, "copy_paste"),
    "cut": (3, "copy_paste"),
    "paste": (3, "copy_paste"),
    "context_menu": (1, "copy_paste"),
    "camera_off": (10, "webcam"),
    "camera_blocked": (10, "webcam"),
    "no_face": (5, "face"),
    "multiple_faces": (10, "face"),
    "phone": (10, "face"),
    # Reloading or reopening the page mid-test (always checked).
    "session_resumed": (5, ""),
}
# Findings the learner controls; one more than max_warnings ends the test.
WARNING_KINDS = frozenset({"focus_lost", "fullscreen_exit", "session_resumed"})

MAX_EVENTS_PER_CALL = 50
MAX_EVENTS_PER_SESSION = 500
MAX_SNAPSHOT_BYTES = 200_000
MAX_SNAPSHOTS_PER_SESSION = 120
SNAPSHOT_RETENTION_DAYS = 30
# An assessment the learner opened but has not started an interview for yet:
# the next interview they start within this time is the assessment's.
ATTACH_WINDOW = timedelta(minutes=30)

ROUND_TYPES = ("technical", "hr")
QUESTION_COUNTS = (5, 10, 15)
KINDS = ("mock_interview", "knowledge_test")
# The proctored session's agent for each kind of assessment.
KIND_AGENTS = {"mock_interview": "mock_interview_agent", "knowledge_test": "knowledge_test_agent"}
# Agent calls whose response the gateway hands to after_agent_call.
RESULT_ACTIONS = {
    "mock_interview_agent": frozenset({"start_interview", "end_interview", "exit_interview"}),
    "capstone_project_agent": frozenset({"submit_viva_answer", "viva_time_up"}),
}


class ProctorError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _now() -> datetime:
    return datetime.utcnow()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def _clean(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


# --- settings ---------------------------------------------------------------

def clean_settings(raw: dict | None) -> dict:
    """The admin's proctoring choices with sane values. Face checks need the webcam."""
    raw = raw or {}
    settings = {check: bool(raw.get(check, True)) for check in CHECKS}
    if not settings["webcam"]:
        settings["face"] = False
    try:
        max_warnings = int(raw.get("max_warnings", DEFAULT_MAX_WARNINGS))
    except (TypeError, ValueError):
        max_warnings = DEFAULT_MAX_WARNINGS
    settings["max_warnings"] = max(1, min(max_warnings, 10))
    return settings


def _clean_config(raw: dict | None) -> dict:
    raw = raw or {}
    round_type = raw.get("round_type") if raw.get("round_type") in ROUND_TYPES else "technical"
    try:
        num_questions = int(raw.get("num_questions", 10))
    except (TypeError, ValueError):
        num_questions = 10
    if num_questions not in QUESTION_COUNTS:
        raise ProctorError(400, "Choose 5, 10 or 15 questions.")
    level = raw.get("level") if raw.get("level") in level_rules.LEVELS else "medium"
    role_name = _clean(raw.get("role_name"), 150)
    subject = _clean(raw.get("subject"), 150)
    if round_type == "technical" and not role_name and not subject:
        raise ProctorError(400, "Enter the job role or the topic for the technical interview.")
    if round_type == "hr":
        subject = ""
    elif role_name:
        subject = ""
    return {"round_type": round_type, "role_name": role_name, "subject": subject,
            "num_questions": num_questions, "level": level}


def _parse_time(value: object) -> datetime | None:
    """An ISO time from the browser (with or without a zone) as naive UTC."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProctorError(400, "Enter a valid date and time.") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


# --- learner side -------------------------------------------------------------

def _session_dict(ps: ProctorSession) -> dict:
    settings = clean_settings(ps.settings)
    return {
        "id": ps.id, "agent_name": ps.agent_name, "ref": ps.ref, "assessment_id": ps.assessment_id,
        "settings": settings, "status": ps.status, "warnings": ps.warnings,
        "max_warnings": settings["max_warnings"], "integrity": ps.integrity,
        "warnings_left": max(0, settings["max_warnings"] - ps.warnings),
        "terminated": ps.status == "terminated",
    }


def _own_session(session, user_id: str, session_id: str) -> ProctorSession:
    ps = session.get(ProctorSession, session_id)
    if ps is None or ps.user_id != user_id:
        raise ProctorError(404, "No such proctored session.")
    return ps


def _add_event(session, ps: ProctorSession, kind: str, detail: str = "") -> bool:
    """Adds one finding (if its check is on) and updates the score. True when added."""
    penalty, check = PENALTIES[kind]
    settings = clean_settings(ps.settings)
    if check and not settings.get(check):
        return False
    session.add(ProctorEvent(session_id=ps.id, kind=kind, detail=_clean(detail, 255), penalty=penalty))
    ps.integrity = max(0, (ps.integrity if ps.integrity is not None else 100) - penalty)
    if kind in WARNING_KINDS:
        ps.warnings = (ps.warnings or 0) + 1
        if ps.status == "active" and ps.warnings > settings["max_warnings"]:
            ps.status = "terminated"
            ps.ended_at = _now()
    return True


def start_practice(user_id: str, agent_name: str, ref: str, consent: bool) -> dict:
    """A Hard/Professional interview or viva begins proctoring. Opening the
    same interview again (a reload) continues its session, with a warning."""
    if agent_name not in PROCTORED_AGENTS:
        raise ProctorError(400, "This agent is not proctored.")
    if not consent:
        raise ProctorError(400, "Agree to proctoring to start.")
    ref = _clean(ref, 128)
    if not ref:
        raise ProctorError(400, "Missing what is being proctored.")
    session = db.get_session()
    try:
        existing = (session.query(ProctorSession)
                    .filter_by(user_id=user_id, agent_name=agent_name, ref=ref)
                    .order_by(ProctorSession.started_at.desc()).first())
        if existing is not None:
            if existing.status == "active":
                _add_event(session, existing, "session_resumed", "The page was reloaded or reopened.")
                session.commit()
            return _session_dict(existing)
        ps = ProctorSession(user_id=user_id, agent_name=agent_name, ref=ref, settings=dict(FULL_SETTINGS))
        session.add(ps)
        session.commit()
        return _session_dict(ps)
    finally:
        session.close()


def record_events(user_id: str, session_id: str, events: list[dict]) -> dict:
    session = db.get_session()
    try:
        ps = _own_session(session, user_id, session_id)
        if ps.status == "active":
            count = session.query(ProctorEvent).filter_by(session_id=ps.id).count()
            for event in events[:MAX_EVENTS_PER_CALL]:
                kind = str(event.get("kind") or "")
                if kind not in PENALTIES or kind == "session_resumed" or count >= MAX_EVENTS_PER_SESSION:
                    continue
                if _add_event(session, ps, kind, str(event.get("detail") or "")):
                    count += 1
                if ps.status != "active":
                    break
            session.commit()
        return _session_dict(ps)
    finally:
        session.close()


def end_session(user_id: str, session_id: str) -> dict:
    session = db.get_session()
    try:
        ps = _own_session(session, user_id, session_id)
        if ps.status == "active":
            ps.status = "completed"
            ps.ended_at = _now()
            session.commit()
        return _session_dict(ps)
    finally:
        session.close()


def state(user_id: str, session_id: str) -> dict:
    session = db.get_session()
    try:
        return _session_dict(_own_session(session, user_id, session_id))
    finally:
        session.close()


def _decode_jpeg(image: str) -> bytes:
    data = image.split(",", 1)[1] if image.startswith("data:") else image
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProctorError(400, "The snapshot is not a valid image.") from exc
    if not raw.startswith(b"\xff\xd8") or len(raw) > MAX_SNAPSHOT_BYTES:
        raise ProctorError(400, "The snapshot must be a JPEG under 200 KB.")
    return raw


def add_snapshot(user_id: str, session_id: str, image: str) -> tuple[dict, str | None]:
    """Stores one webcam still. Returns the session state and the snapshot id
    to face-check (None when face checks are off or nothing was stored)."""
    raw = _decode_jpeg(image)
    purge_old_snapshots()
    session = db.get_session()
    try:
        ps = _own_session(session, user_id, session_id)
        settings = clean_settings(ps.settings)
        if ps.status != "active" or not settings["webcam"]:
            return _session_dict(ps), None
        if session.query(ProctorSnapshot).filter_by(session_id=ps.id).count() >= MAX_SNAPSHOTS_PER_SESSION:
            return _session_dict(ps), None
        snapshot = ProctorSnapshot(session_id=ps.id, image=raw)
        session.add(snapshot)
        session.commit()
        return _session_dict(ps), snapshot.id if settings["face"] else None
    finally:
        session.close()


FACE_PROMPT = (
    "You check one webcam still from a proctored online interview. Reply with JSON only: "
    '{"faces": <number of human faces visible>, "phone": <true if a phone or second screen is '
    'clearly being used>, "note": "<under 12 words>"}. Count only real faces, not photos on a wall.'
)


def _vision_check(raw: bytes) -> dict:
    import litellm

    from app import config

    url = "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
    response = litellm.completion(
        model=config.LLM_MODEL, temperature=0, max_tokens=80,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": [
            {"type": "text", "text": FACE_PROMPT},
            {"type": "image_url", "image_url": {"url": url, "detail": "low"}},
        ]}],
    )
    return json.loads(response.choices[0].message.content or "{}")


def check_snapshot(snapshot_id: str) -> None:
    """Runs after the upload returns: asks the vision model about the still
    and records no face / several faces / a phone as findings."""
    session = db.get_session()
    try:
        snapshot = session.get(ProctorSnapshot, snapshot_id)
        if snapshot is None:
            return
        raw = snapshot.image
    finally:
        session.close()
    try:
        found = _vision_check(raw)
        faces = max(0, min(int(found.get("faces", 1)), 20))
        phone = bool(found.get("phone"))
        note = _clean(found.get("note"), 255)
    except Exception:
        logger.warning("proctoring face check failed for snapshot %s", snapshot_id, exc_info=True)
        return
    session = db.get_session()
    try:
        snapshot = session.get(ProctorSnapshot, snapshot_id)
        if snapshot is None:
            return
        snapshot.faces = faces
        snapshot.note = note
        ps = session.get(ProctorSession, snapshot.session_id)
        # Photos are only taken while the test runs, so a finding counts even
        # when the check finishes after the test ended.
        if ps is not None:
            if faces == 0:
                _add_event(session, ps, "no_face", note or "No face in the camera.")
            elif faces > 1:
                _add_event(session, ps, "multiple_faces", note or f"{faces} faces in the camera.")
            if phone:
                _add_event(session, ps, "phone", note or "A phone or second screen was seen.")
        session.commit()
    finally:
        session.close()


_last_purge = 0.0
_purge_lock = threading.Lock()


def purge_old_snapshots(force: bool = False) -> int:
    """Deletes webcam stills older than SNAPSHOT_RETENTION_DAYS, at most once an hour."""
    global _last_purge
    with _purge_lock:
        if not force and time.monotonic() - _last_purge < 3600:
            return 0
        _last_purge = time.monotonic()
    session = db.get_session()
    try:
        cutoff = _now() - timedelta(days=SNAPSHOT_RETENTION_DAYS)
        deleted = session.query(ProctorSnapshot).filter(ProctorSnapshot.created_at < cutoff).delete(synchronize_session=False)
        session.commit()
        return int(deleted or 0)
    except Exception:
        logger.warning("proctoring snapshot purge failed", exc_info=True)
        session.rollback()
        return 0
    finally:
        session.close()


# --- assessment links: learner side ------------------------------------------

def _assessment_by_token(session, token: str) -> Assessment:
    assessment = session.query(Assessment).filter_by(token=_clean(token, 64)).first()
    if assessment is None:
        raise ProctorError(404, "This assessment link is not valid.")
    return assessment


def _window_state(assessment: Assessment, org: Organization | None) -> str:
    now = _now()
    if not assessment.active or org is None or (org.status or "active") != "active":
        return "inactive"
    if assessment.opens_at and now < assessment.opens_at:
        return "not_open"
    if assessment.closes_at and now > assessment.closes_at:
        return "closed"
    return "open"


def _config_view(config: dict) -> dict:
    if config.get("test_id"):
        return dict(config)
    level = config.get("level", "medium")
    return {**config, "level_label": level_rules.LEVEL_LABELS.get(level, level.title())}


def _attempt_view(ps: ProctorSession | None) -> dict | None:
    if ps is None:
        return None
    return {"session_id": ps.id, "status": ps.status, "integrity": ps.integrity, "warnings": ps.warnings,
            "result": ps.result, "started_at": _iso(ps.started_at), "ended_at": _iso(ps.ended_at)}


def preview_assessment(user_id: str, token: str) -> dict:
    """What the learner sees on opening the link, before starting."""
    session = db.get_session()
    try:
        assessment = _assessment_by_token(session, token)
        org = session.get(Organization, assessment.organization_id)
        window = _window_state(assessment, org)
        attempt = (session.query(ProctorSession).filter_by(user_id=user_id, assessment_id=assessment.id)
                   .order_by(ProctorSession.started_at.desc()).first())
        member = session.query(OrganizationMember).filter_by(user_id=user_id).first()
        is_member = member is not None and member.organization_id == assessment.organization_id
        reason = ""
        if window == "inactive":
            reason = "This assessment is closed by the organization."
        elif window == "not_open":
            reason = "This assessment has not opened yet."
        elif window == "closed":
            reason = "This assessment has closed."
        elif assessment.members_only and not is_member:
            reason = f"This assessment is only for members of {org.name}. Join the organization first."
        elif attempt is not None and attempt.status != "active":
            reason = "You have already taken this assessment."
        return {
            "title": assessment.title, "kind": assessment.kind,
            "organization": org.name if org else "",
            "config": _config_view(assessment.config or {}),
            "proctoring": clean_settings(assessment.proctoring),
            "opens_at": _iso(assessment.opens_at), "closes_at": _iso(assessment.closes_at),
            "window": window, "can_start": not reason, "reason": reason,
            "attempt": _attempt_view(attempt),
        }
    finally:
        session.close()


def start_assessment(user_id: str, token: str, consent: bool) -> dict:
    """Starts (or continues) the learner's one attempt at an assessment."""
    if not consent:
        raise ProctorError(400, "Agree to the assessment rules and proctoring to start.")
    preview = preview_assessment(user_id, token)
    attempt = preview["attempt"]
    if not preview["can_start"]:
        raise ProctorError(409 if attempt else 403, preview["reason"])
    session = db.get_session()
    try:
        assessment = _assessment_by_token(session, token)
        if attempt and attempt["status"] == "active":
            ps = session.get(ProctorSession, attempt["session_id"])
            _add_event(session, ps, "session_resumed", "The assessment was reopened.")
        else:
            ps = ProctorSession(user_id=user_id, agent_name=KIND_AGENTS.get(assessment.kind, "mock_interview_agent"), ref="",
                                assessment_id=assessment.id, level=(assessment.config or {}).get("level", ""),
                                settings=clean_settings(assessment.proctoring))
            session.add(ps)
        session.commit()
        return {**_session_dict(ps), "assessment": {
            "title": assessment.title, "config": _config_view(assessment.config or {})}}
    finally:
        session.close()


# --- gateway hooks --------------------------------------------------------------

def _open_assessment_session(session, user_id: str) -> ProctorSession | None:
    """The learner's assessment attempt still waiting for its interview."""
    return (session.query(ProctorSession)
            .filter(ProctorSession.user_id == user_id, ProctorSession.agent_name == "mock_interview_agent",
                    ProctorSession.assessment_id.isnot(None), ProctorSession.status == "active",
                    ProctorSession.ref == "", ProctorSession.started_at >= _now() - ATTACH_WINDOW)
            .order_by(ProctorSession.started_at.desc()).first())


def apply_assessment(user_id: str, agent_name: str, envelope: dict) -> None:
    """Before forwarding: a mock interview started during an assessment
    attempt gets the admin's round, role/topic, question count and level,
    whatever the browser sent."""
    if agent_name != "mock_interview_agent" or envelope.get("action") != "start_interview":
        return
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        return
    session = db.get_session()
    try:
        ps = _open_assessment_session(session, user_id)
        if ps is None:
            return
        assessment = session.get(Assessment, ps.assessment_id)
        config = (assessment.config if assessment else None) or {}
    finally:
        session.close()
    round_type = config.get("round_type", "technical")
    payload.pop("role_name", None)
    payload.pop("subject", None)
    payload.pop("resolved_subjects", None)
    payload["round_type"] = round_type
    payload["num_questions"] = config.get("num_questions", 10)
    payload["difficulty"] = level_rules.AGENT_DIFFICULTY["mock_interview_agent"].get(config.get("level", "medium"), "intermediate")
    if round_type == "hr":
        payload["interview_mode"] = "course"
    elif config.get("role_name"):
        payload["interview_mode"] = "role"
        payload["role_name"] = config["role_name"]
    else:
        payload["interview_mode"] = "custom_topic"
        payload["subject"] = config.get("subject", "")


def after_agent_call(user_id: str, agent_name: str, action: str, payload: dict, data: dict) -> None:
    """After a successful call: ties a new assessment interview to its attempt
    and records interview and viva results on the proctored session."""
    if agent_name not in PROCTORED_AGENTS or not isinstance(data, dict):
        return
    payload = payload if isinstance(payload, dict) else {}
    session = db.get_session()
    try:
        if agent_name == "mock_interview_agent":
            if action == "start_interview" and data.get("interview_id"):
                ps = _open_assessment_session(session, user_id)
                if ps is not None:
                    ps.ref = str(data["interview_id"])
                    session.commit()
                return
            if action not in ("end_interview", "exit_interview") or not payload.get("interview_id"):
                return
            ps = (session.query(ProctorSession)
                  .filter_by(user_id=user_id, agent_name=agent_name, ref=str(payload["interview_id"]))
                  .order_by(ProctorSession.started_at.desc()).first())
            if ps is None:
                return
            ps.result = {
                "score": data.get("total_marks"), "max": data.get("max_marks"),
                "overall": data.get("overall_score"), "ended_early": action == "exit_interview",
            }
        else:
            if action not in ("submit_viva_answer", "viva_time_up") or data.get("viva_passed") is None:
                return
            submission = _clean(payload.get("submission_id"), 100)
            if not submission:
                return
            ps = (session.query(ProctorSession)
                  .filter(ProctorSession.user_id == user_id, ProctorSession.agent_name == agent_name,
                          ProctorSession.ref.like(f"{submission}:%"))
                  .order_by(ProctorSession.started_at.desc()).first())
            if ps is None:
                return
            ps.result = {"label": data.get("viva_rating"), "passed": bool(data.get("viva_passed"))}
        if ps.status == "active":
            ps.status = "completed"
            ps.ended_at = _now()
        session.commit()
    finally:
        session.close()


# --- organization admin side ---------------------------------------------------

def _assessment_dict(assessment: Assessment, attempts: int = 0) -> dict:
    return {
        "id": assessment.id, "title": assessment.title, "kind": assessment.kind,
        "config": _config_view(assessment.config or {}), "proctoring": clean_settings(assessment.proctoring),
        "path": f"/assessment/{assessment.token}", "opens_at": _iso(assessment.opens_at),
        "closes_at": _iso(assessment.closes_at), "members_only": bool(assessment.members_only),
        "active": bool(assessment.active), "attempts": attempts, "created_at": _iso(assessment.created_at),
    }


def _admin(session, user_id: str, org_id: str) -> None:
    try:
        org_service._require_admin(session, user_id, org_id)
    except org_service.OrgError as exc:
        raise ProctorError(exc.status_code, exc.message) from exc


def list_assessments(user_id: str, org_id: str) -> list[dict]:
    from sqlalchemy import func

    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        rows = session.query(Assessment).filter_by(organization_id=org_id).order_by(Assessment.created_at.desc()).all()
        counts = dict(session.query(ProctorSession.assessment_id, func.count(ProctorSession.id))
                      .filter(ProctorSession.assessment_id.in_([a.id for a in rows] or [""]))
                      .group_by(ProctorSession.assessment_id).all())
        return [_assessment_dict(a, counts.get(a.id, 0)) for a in rows]
    finally:
        session.close()


def create_assessment(user_id: str, org_id: str, data: dict) -> dict:
    title = _clean(data.get("title"), 200)
    if len(title) < 3:
        raise ProctorError(400, "Give the assessment a title.")
    kind = data.get("kind") or "mock_interview"
    if kind not in KINDS:
        raise ProctorError(400, "Choose a mock interview or a knowledge test.")
    opens_at, closes_at = _parse_time(data.get("opens_at")), _parse_time(data.get("closes_at"))
    if opens_at and closes_at and closes_at <= opens_at:
        raise ProctorError(400, "The closing time must be after the opening time.")
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
    finally:
        session.close()
    if kind == "knowledge_test":
        from app.knowledge import service as knowledge_service

        try:
            config = knowledge_service.assessment_config(org_id, (data.get("config") or {}).get("test_id"))
        except knowledge_service.KnowledgeError as exc:
            raise ProctorError(exc.status_code, exc.message) from exc
    else:
        config = _clean_config(data.get("config"))
    session = db.get_session()
    try:
        if session.query(Assessment).filter_by(organization_id=org_id).count() >= 1000:
            raise ProctorError(409, "An organization can have at most 1000 assessments.")
        assessment = Assessment(
            organization_id=org_id, created_by=user_id, title=title, kind=kind, config=config,
            proctoring=clean_settings(data.get("proctoring")), token=secrets.token_urlsafe(18),
            opens_at=opens_at, closes_at=closes_at, members_only=bool(data.get("members_only", True)),
        )
        session.add(assessment)
        session.commit()
        return _assessment_dict(assessment)
    finally:
        session.close()


def _org_assessment(session, org_id: str, assessment_id: str) -> Assessment:
    assessment = session.get(Assessment, assessment_id)
    if assessment is None or assessment.organization_id != org_id:
        raise ProctorError(404, "No such assessment in this organization.")
    return assessment


def set_assessment_active(user_id: str, org_id: str, assessment_id: str, active: bool) -> dict:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        assessment = _org_assessment(session, org_id, assessment_id)
        assessment.active = active
        session.commit()
        return _assessment_dict(assessment)
    finally:
        session.close()


def _summary_row(ps: ProctorSession, user: User | None) -> dict:
    return {
        "session_id": ps.id, "user_id": ps.user_id, "name": user.name if user else "",
        "email": user.email if user else "", "agent_name": ps.agent_name, "ref": ps.ref,
        "status": ps.status, "integrity": ps.integrity, "warnings": ps.warnings, "result": ps.result,
        "started_at": _iso(ps.started_at), "ended_at": _iso(ps.ended_at),
        "assessment_id": ps.assessment_id,
    }


def assessment_attempts(user_id: str, org_id: str, assessment_id: str) -> list[dict]:
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        _org_assessment(session, org_id, assessment_id)
        rows = (session.query(ProctorSession, User).outerjoin(User, User.id == ProctorSession.user_id)
                .filter(ProctorSession.assessment_id == assessment_id)
                .order_by(ProctorSession.started_at.desc()).limit(2000).all())
        return [_summary_row(ps, user) for ps, user in rows]
    finally:
        session.close()


def member_sessions(user_id: str, org_id: str, member_user_id: str) -> list[dict]:
    """A consenting member's proctored practice sittings (Hard/Professional
    interviews and vivas) and their attempts at this organization's links."""
    session = db.get_session()
    try:
        _admin(session, user_id, org_id)
        org_assessments = {a.id for a in session.query(Assessment.id).filter_by(organization_id=org_id).all()}
        rows = (session.query(ProctorSession).filter_by(user_id=member_user_id)
                .order_by(ProctorSession.started_at.desc()).limit(100).all())
        user = session.get(User, member_user_id)
        return [_summary_row(ps, user) for ps in rows
                if ps.assessment_id is None or ps.assessment_id in org_assessments]
    finally:
        session.close()


def _session_for_admin(session, admin_id: str, org_id: str, session_id: str) -> ProctorSession:
    _admin(session, admin_id, org_id)
    ps = session.get(ProctorSession, session_id)
    if ps is None:
        raise ProctorError(404, "No such proctored session.")
    if ps.assessment_id:
        assessment = session.get(Assessment, ps.assessment_id)
        if assessment is not None and assessment.organization_id == org_id:
            return ps
    else:
        member = session.query(OrganizationMember).filter_by(user_id=ps.user_id).first()
        if member is not None and member.organization_id == org_id and member.progress_shared_at is not None:
            return ps
    raise ProctorError(404, "No such proctored session.")


def session_detail(admin_id: str, org_id: str, session_id: str) -> dict:
    session = db.get_session()
    try:
        ps = _session_for_admin(session, admin_id, org_id, session_id)
        user = session.get(User, ps.user_id)
        events = (session.query(ProctorEvent).filter_by(session_id=ps.id)
                  .order_by(ProctorEvent.created_at).all())
        snapshots = (session.query(ProctorSnapshot.id, ProctorSnapshot.faces, ProctorSnapshot.note,
                                   ProctorSnapshot.created_at)
                     .filter_by(session_id=ps.id).order_by(ProctorSnapshot.created_at).all())
        session.add(OrgAccessLog(organization_id=org_id, viewer_id=admin_id, subject_user_id=ps.user_id,
                                 action="proctoring", target=ps.id))
        session.commit()
        return {
            **_summary_row(ps, user), "settings": clean_settings(ps.settings),
            "events": [{"kind": e.kind, "detail": e.detail, "penalty": e.penalty, "at": _iso(e.created_at)} for e in events],
            "snapshots": [{"id": sid, "faces": faces, "note": note, "at": _iso(at)} for sid, faces, note, at in snapshots],
            "retention_days": SNAPSHOT_RETENTION_DAYS,
        }
    finally:
        session.close()


def snapshot_image(admin_id: str, org_id: str, session_id: str, snapshot_id: str) -> bytes:
    session = db.get_session()
    try:
        ps = _session_for_admin(session, admin_id, org_id, session_id)
        snapshot = session.get(ProctorSnapshot, snapshot_id)
        if snapshot is None or snapshot.session_id != ps.id:
            raise ProctorError(404, "This snapshot was deleted or does not exist.")
        return snapshot.image
    finally:
        session.close()

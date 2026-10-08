"""Strategy F adapter for the existing mock-interview REST API.

Mirrors agents/aptitude_agent/backend/app/routes/invoke.py: business logic
stays in the original blueprints, this only translates the shared
``{action, payload}`` envelope into internal Flask requests via
``current_app.test_client()``.

The one thing this module didn't already have is an identity boundary (see
session_auth.py) -- every action below that touches a specific student
substitutes the session-token-verified ``student_id`` into the request
itself, so a client can never reach another student's interview, profile,
or history by passing a different id in the payload.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
from io import BytesIO

from flask import Blueprint, current_app, jsonify, request

import db
import privacy
from session_auth import InvalidSessionToken, issue_session_token, student_id_from_token
from settings import ALLOWED_AUDIO_TYPES, MAX_AUDIO_UPLOAD_BYTES

bp = Blueprint("invoke", __name__)
logger = logging.getLogger("mock_interview.invoke")

AGENT_NAME = "mock_interview_agent"

# action -> (method, path template). "{student_id}" is filled in from the
# verified session token, never from the caller's payload.
STUDENT_SCOPED_ROUTES = {
    "profile": ("GET", "/api/profile/{student_id}"),
    "update_profile": ("PUT", "/api/profile/{student_id}"),
    "dashboard": ("GET", "/api/dashboard/{student_id}"),
    "history": ("GET", "/api/history/{student_id}"),
    "daily_usage": ("GET", "/api/daily_usage/{student_id}"),
    "active_interview": ("GET", "/api/active_interview/{student_id}"),
}

# action -> (method, path). These act on an interview the caller names in the
# payload. The underlying routes have no per-owner check of their own, so
# _dispatch() verifies the interview belongs to the session's student first.
GENERAL_ROUTES = {
    "start_interview": ("POST", "/api/start_interview"),
    "submit_answer": ("POST", "/api/submit_answer"),
    "end_interview": ("POST", "/api/end_interview"),
    "exit_interview": ("POST", "/api/exit_interview"),
}


INTERVIEW_SCOPED_ACTIONS = {
    "submit_answer", "end_interview", "exit_interview",
    "history_detail", "record_focus_event", "download_report", "transcribe_audio",
    "transcribe_preview",
}


def _error(message: str, code: str, status: int):
    return jsonify(error=message, code=code), status


def _ensure_session(payload: dict):
    verified_user_id = str(request.headers.get("X-DigiDARA-User-ID") or "").strip()
    requested_user_id = str(payload.get("user_id") or "").strip()
    if not verified_user_id or requested_user_id != verified_user_id:
        return _error("Verified DigiDARA identity is required", "unverified_identity", 401)
    email = str(payload.get("email") or "").strip().lower()
    name = str(payload.get("name") or "Learner").strip()[:100] or "Learner"
    if not email or "@" not in email or len(email) > 150:
        return _error("A valid email is required", "invalid_email", 400)

    student, _ = db.query("SELECT id FROM students WHERE email = %s", (email,), fetchone=True)
    if student is None:
        _, student_id = db.query(
            "INSERT INTO students (name, email) VALUES (%s, %s)", (name, email),
        )
    else:
        student_id = student["id"]
        db.query("UPDATE students SET name = %s WHERE id = %s", (name, student_id))

    token = issue_session_token(student_id)
    return jsonify({"sessionToken": token, "student_id": student_id})


def _personal_data(action: str, payload: dict):
    # Gateway-verified identity only; the email is the orchestrator's own
    # account record, so this never trusts a browser-supplied identity.
    if not str(request.headers.get("X-DigiDARA-User-ID") or "").strip():
        return _error("Verified DigiDARA identity is required", "unverified_identity", 401)
    email = str(payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return _error("A valid email is required", "invalid_email", 400)
    if action == "export_user_data":
        return jsonify(privacy.export_student(email))
    return jsonify(privacy.erase_student(email))


SUMMARY_RECENT_INTERVIEWS = 5
BULLET_CHARS = " -*•"


def _text_items(value) -> list[str]:
    """strengths/weaknesses are stored as a JSON list or as plain text."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item for item in (line.strip(BULLET_CHARS) for line in str(value).replace(";", "\n").splitlines()) if item]


def _student_summary(payload: dict):
    """Phase 2 readiness skill (digidara.student_summary.v1). The gateway
    puts the verified account's own email in the payload for this action.
    Score: the latest completed interviews' overall score, out of 10 -> 100."""
    if not str(request.headers.get("X-DigiDARA-User-ID") or "").strip():
        return _error("Verified DigiDARA identity is required", "unverified_identity", 401)
    empty = {"schema": "digidara.student_summary.v1", "score": None, "activity_count": 0,
             "last_activity_at": None, "strengths": [], "gaps": [], "metrics": {}}
    email = str(payload.get("email") or "").strip().lower()
    student, _ = db.query("SELECT id FROM students WHERE email = %s", (email,), fetchone=True) if email else (None, None)
    if student is None:
        return jsonify(empty)
    rows, _ = db.query(
        "SELECT overall_score, technical_accuracy, communication_clarity, confidence, strengths, weaknesses, ended_at "
        "FROM interviews WHERE student_id = %s AND status = 'completed' AND overall_score IS NOT NULL "
        "ORDER BY ended_at DESC, id DESC",
        (student["id"],), fetch=True,
    )
    rows = rows or []
    if not rows:
        return jsonify(empty)
    recent = rows[:SUMMARY_RECENT_INTERVIEWS]

    def average(column):
        values = [float(r[column]) for r in recent if r.get(column) is not None]
        return round(sum(values) / len(values) * 10, 1) if values else None

    latest = recent[0]
    ended = latest.get("ended_at")
    return jsonify({
        "schema": "digidara.student_summary.v1",
        "score": average("overall_score"),
        "activity_count": len(rows),
        "last_activity_at": ended.isoformat() if hasattr(ended, "isoformat") else None,
        "strengths": _text_items(latest.get("strengths"))[:3],
        "gaps": _text_items(latest.get("weaknesses"))[:3],
        "metrics": {
            "interviews_completed": len(rows),
            "technical_accuracy": average("technical_accuracy"),
            "communication_clarity": average("communication_clarity"),
            "confidence": average("confidence"),
        },
    })


def _usage_summary(payload: dict):
    """The signed-in student's own AI usage, in the same shape every other agent
    returns for the Settings > Usage screen. Without a valid session there is
    no student to report on, so the totals are zero -- never other learners'."""
    try:
        student_id = student_id_from_token(str(payload.get("sessionToken") or ""))
    except InvalidSessionToken:
        student_id = None
    totals, rows = {}, []
    if student_id is not None:
        totals, _ = db.query(
            "SELECT COUNT(*) AS total_requests, COALESCE(SUM(total_tokens), 0) AS total_tokens, "
            "COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens, COALESCE(SUM(completion_tokens), 0) AS completion_tokens "
            "FROM ai_usage_records WHERE student_id = %s",
            (student_id,),
            fetchone=True,
        )
        rows, _ = db.query(
            "SELECT request_type, COUNT(*) AS request_count FROM ai_usage_records WHERE student_id = %s GROUP BY request_type",
            (student_id,),
            fetch=True,
        )
    totals = totals or {}
    return jsonify(
        agent_name=AGENT_NAME,
        total_requests=int(totals.get("total_requests") or 0),
        total_tokens=int(totals.get("total_tokens") or 0),
        prompt_tokens=int(totals.get("prompt_tokens") or 0),
        completion_tokens=int(totals.get("completion_tokens") or 0),
        by_request_type={row["request_type"]: int(row["request_count"]) for row in (rows or [])},
    )


def _owns_interview(student_id: int, interview_id) -> bool:
    try:
        interview_id = int(interview_id)
    except (TypeError, ValueError):
        return False
    row, _ = db.query("SELECT student_id FROM interviews WHERE id = %s", (interview_id,), fetchone=True)
    return bool(row) and int(row["student_id"]) == student_id


def _dispatch(action: str, payload: dict):
    token = str(payload.pop("sessionToken", "") or "")
    try:
        student_id = student_id_from_token(token)
    except InvalidSessionToken:
        return _error("A valid sessionToken is required", "session_required", 401)

    if action in INTERVIEW_SCOPED_ACTIONS and not _owns_interview(student_id, payload.get("interview_id")):
        # Same response for "not yours" and "doesn't exist" so ids can't be probed.
        return _error("Interview not found.", "interview_not_found", 404)

    client = current_app.test_client()

    if action in STUDENT_SCOPED_ROUTES:
        method, path_template = STUDENT_SCOPED_ROUTES[action]
        path = path_template.format(student_id=student_id)
        body = {key: value for key, value in payload.items() if key != "student_id"}
        if method == "GET":
            response = client.get(path, query_string=body)
        else:
            response = client.open(path, method=method, json=body)
        return response

    if action == "history_detail":
        interview_id = payload.get("interview_id")
        if not interview_id:
            return _error("interview_id is required", "interview_id_required", 400)
        return client.get(f"/api/history/detail/{int(interview_id)}")

    if action == "record_focus_event":
        interview_id = payload.get("interview_id")
        if not interview_id:
            return _error("interview_id is required", "interview_id_required", 400)
        body = {key: value for key, value in payload.items() if key != "interview_id"}
        return client.open(f"/api/interviews/{int(interview_id)}/focus-events", method="POST", json=body)

    if action == "download_report":
        interview_id = payload.get("interview_id")
        if not interview_id:
            return _error("interview_id is required", "interview_id_required", 400)
        pdf = client.get(f"/api/interviews/{int(interview_id)}/report-pdf")
        if pdf.status_code != 200:
            return pdf
        return jsonify(content_type="application/pdf", filename="interview-report.pdf", data=base64.b64encode(pdf.data).decode("ascii"))

    # transcribe_preview: the answer so far, shown live while the candidate is
    # still speaking on a phone. Same checks; nothing is saved.
    if action in {"transcribe_audio", "transcribe_preview"}:
        audio_type = str(payload.get("audio_type") or "audio/webm").split(";", 1)[0].lower()
        if audio_type not in ALLOWED_AUDIO_TYPES:
            return _error("Use a WebM, OGG, M4A, MP3, or WAV recording.", "invalid_audio_type", 400)
        encoded_audio = payload.get("audio_data")
        if not isinstance(encoded_audio, str) or not encoded_audio:
            return _error("audio_data is required", "audio_required", 400)
        # Reject oversized data before allocating its decoded representation.
        if len(encoded_audio) > ((MAX_AUDIO_UPLOAD_BYTES + 2) // 3) * 4:
            return _error("The uploaded recording is too large.", "audio_too_large", 413)
        try:
            audio_bytes = base64.b64decode(encoded_audio, validate=True)
        except (binascii.Error, ValueError):
            return _error("The audio recording is invalid.", "invalid_audio", 400)
        if not audio_bytes:
            return _error("The uploaded recording is empty.", "empty_audio", 400)
        if len(audio_bytes) > MAX_AUDIO_UPLOAD_BYTES:
            return _error("The uploaded recording is too large.", "audio_too_large", 413)
        extension = ALLOWED_AUDIO_TYPES[audio_type]
        return client.post(
            "/api/transcribe",
            data={
                "interview_id": str(payload.get("interview_id") or ""),
                "question_order": str(payload.get("question_order") or ""),
                "preview": "1" if action == "transcribe_preview" else "0",
                "audio": (BytesIO(audio_bytes), f"answer{extension}", audio_type),
            },
            content_type="multipart/form-data",
        )

    if action in GENERAL_ROUTES:
        method, path = GENERAL_ROUTES[action]
        # student_id is never taken from the caller's payload for these
        # actions either -- always the session's own verified identity.
        body = {**{key: value for key, value in payload.items() if key != "student_id"}, "student_id": student_id}
        return client.open(path, method=method, json=body)

    return _error("Unknown action", "unknown_action", 400)


@bp.post("/invoke")
def invoke():
    request_body = request.get_json(silent=True) or {}
    if not isinstance(request_body, dict):
        return _error("Request body must be an object", "invalid_request", 400)
    action = str(request_body.get("action") or "").strip()
    payload = request_body.get("payload") or {}
    if not isinstance(payload, dict):
        return _error("payload must be an object", "invalid_payload", 400)

    if action == "health":
        return jsonify(status="ok", agent_name=AGENT_NAME)
    if action == "usage_summary":
        return _usage_summary(payload)
    if action == "ensure_session":
        return _ensure_session(payload)
    if action in {"export_user_data", "delete_user_data"}:
        return _personal_data(action, payload)
    if action == "get_student_summary":
        return _student_summary(payload)

    logger.info("mock_interview invoke action=%s", action)
    return _dispatch(action, payload)

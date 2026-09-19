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
import logging

from flask import Blueprint, current_app, jsonify, request

import db
from session_auth import InvalidSessionToken, issue_session_token, student_id_from_token

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
    "history_detail", "record_focus_event", "download_report",
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
    if action == "ensure_session":
        return _ensure_session(payload)

    logger.info("mock_interview invoke action=%s", action)
    return _dispatch(action, payload)

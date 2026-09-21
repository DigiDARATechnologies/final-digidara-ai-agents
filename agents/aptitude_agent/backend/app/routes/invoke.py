"""Strategy F adapter for the existing Aptitude REST API.

The business logic stays in the original blueprints. This adapter only
translates the common ``{action, payload}`` contract into internal requests.
"""
from __future__ import annotations

import base64
import logging
import re
import time
import uuid

from flask import Blueprint, current_app, g, request, jsonify

from ..extensions import db
from ..models import Student
from ..services.auth_service import issue_token

bp = Blueprint("strategy_f_invoke", __name__)
logger = logging.getLogger("backend.app.integration")


@bp.before_request
def _log_invoke_start():
    body = request.get_json(silent=True) or {}
    g.strategy_f_action = str(body.get("action") or "unknown") if isinstance(body, dict) else "invalid"
    g.strategy_f_started = time.perf_counter()
    logger.info("Aptitude invoke started action=%s", g.strategy_f_action)


@bp.after_request
def _log_invoke_complete(response):
    started = getattr(g, "strategy_f_started", time.perf_counter())
    logger.info(
        "Aptitude invoke completed action=%s status=%s duration_ms=%.2f",
        getattr(g, "strategy_f_action", "unknown"), response.status_code,
        (time.perf_counter() - started) * 1000,
    )
    return response


def _student_id(external_id: str, email: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9_-]", "-", external_id or email).strip("-") or str(uuid.uuid4())
    return f"digidara-{raw}"[:128]


def _ensure_session(payload: dict):
    verified_user_id = str(request.headers.get("X-DigiDARA-User-ID") or "").strip()
    requested_user_id = str(payload.get("user_id") or "").strip()
    if not verified_user_id or requested_user_id != verified_user_id:
        return jsonify(error="Verified DigiDARA identity is required", code="unverified_identity"), 401
    email = str(payload.get("email") or "").strip().lower()
    name = str(payload.get("name") or "Learner").strip()[:160] or "Learner"
    mobile = str(payload.get("mobile") or "").strip()[:24] or None
    if not email or "@" not in email:
        return jsonify(error="A valid email is required", code="invalid_email"), 400
    student = Student.query.filter_by(email=email).first()
    if student is None:
        student = Student(id=_student_id(str(payload.get("user_id") or ""), email), name=name, email=email, phone=mobile)
        db.session.add(student)
    else:
        student.name = name
        if mobile:
            student.phone = mobile
    db.session.commit()
    token, expires_at = issue_token(student, auth_source="strategy_f")
    return jsonify({"sessionToken": token, "expires_at": expires_at, "student": {"id": student.id, "name": student.name, "email": student.email, "mobile": student.phone or ""}})


def _personal_data(action: str, payload: dict):
    """DPDP export/erasure on behalf of the platform account bridge.

    Only the gateway-verified identity header authorizes this; the email comes
    from the orchestrator's own account record, and the request then re-enters
    the learner's normal privacy routes under a token for that one student.
    """
    if not str(request.headers.get("X-DigiDARA-User-ID") or "").strip():
        return jsonify(error="Verified DigiDARA identity is required", code="unverified_identity"), 401
    email = str(payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify(error="A valid email is required", code="invalid_email"), 400
    if current_app.config["SINGLE_USER_MODE"]:
        # In single-user mode every request is served as one shared student
        # whatever token it carries, so an export or erasure would act on the
        # wrong person. Refuse rather than touch someone else's data.
        return jsonify(error="Personal-data requests are unavailable while SINGLE_USER_MODE is on", code="single_user_mode"), 503
    student = Student.query.filter_by(email=email).first()
    if student is None:
        return jsonify({"profile": None} if action == "export_user_data" else {"status": "no_data"})
    token, _ = issue_token(student, auth_source="strategy_f")
    headers = {"Authorization": f"Bearer {token}"}
    client = current_app.test_client()
    if action == "export_user_data":
        return client.get("/api/aptitude/me/export", headers=headers)
    return client.delete("/api/aptitude/me", headers=headers)


ROUTES = {
    "dashboard": ("GET", "/api/aptitude/dashboard"),
    "history": ("GET", "/api/aptitude/history"),
    "analytics": ("GET", "/api/aptitude/analytics"),
    "usage_summary": ("GET", "/api/aptitude/usage"),
    "profile": ("GET", "/api/aptitude/me"),
    "mixed_test_config": ("GET", "/api/learner/mixed-test-config"),
    "save_mixed_test_config": ("PUT", "/api/learner/mixed-test-config"),
    "create_test": ("POST", "/api/aptitude/tests"),
}


def _invoke_internal(action: str, payload: dict):
    if action in ROUTES:
        method, path = ROUTES[action]
        body = payload.copy()
    else:
        test_id = str(payload.get("test_id") or "").strip()
        if not test_id:
            return jsonify(error="test_id is required", code="test_id_required"), 400
        endpoint = {"status": "status", "question": "question", "answer": "answer", "hint": "hint", "skip": "skip", "abandon": "abandon", "results": ""}.get(action)
        if endpoint is None:
            return jsonify(error="Unknown action", code="unknown_action"), 400
        method = "POST" if action in {"answer", "hint", "skip", "abandon"} else "GET"
        path = f"/api/aptitude/tests/{test_id}" + (f"/{endpoint}" if endpoint else "")
        body = {key: value for key, value in payload.items() if key != "test_id"}
    token = str(body.pop("sessionToken", "") or "")
    if not token:
        return jsonify(error="sessionToken is required", code="session_required"), 401
    headers = {"Authorization": f"Bearer {token}"}
    client = current_app.test_client()
    if method == "GET":
        query = {key: value for key, value in body.items() if key != "sessionToken"}
        response = client.get(path, query_string=query, headers=headers)
    else:
        response = client.open(path, method=method, headers={**headers, "Content-Type": "application/json"}, json=body)
    if response.status_code >= 400:
        error_payload = response.get_json(silent=True) or {}
        logger.error(
            "Aptitude invoke failed action=%s test_id=%s status=%s code=%s error=%s request_id=%s",
            action,
            test_id if action not in ROUTES else None,
            response.status_code,
            error_payload.get("code"),
            str(error_payload.get("error") or response.status)[:500],
            error_payload.get("request_id"),
        )
    return response


@bp.post("/api/invoke")
def invoke():
    request_body = request.get_json(silent=True) or {}
    if not isinstance(request_body, dict):
        return jsonify(error="Request body must be an object", code="invalid_request"), 400
    action = str(request_body.get("action") or "").strip()
    payload = request_body.get("payload") or {}
    if not isinstance(payload, dict):
        return jsonify(error="payload must be an object", code="invalid_payload"), 400
    if action == "health":
        return jsonify(status="ok", agent_name="aptitude_agent")
    if action == "ensure_session":
        return _ensure_session(payload)
    if action in {"export_user_data", "delete_user_data"}:
        return _personal_data(action, payload)
    if action == "usage_summary":
        response = _invoke_internal(action, payload)
        if response.status_code != 200:
            return response
        raw = response.get_json() or {}
        totals = (raw.get("summary") or {}).get("today") or {}
        return jsonify({"agent_name": "aptitude_agent", "total_requests": len(raw.get("per_questions") or []),
                        "total_tokens": totals.get("total_tokens", 0), "prompt_tokens": totals.get("input_tokens", 0),
                        "completion_tokens": totals.get("output_tokens", 0), "by_request_type": {}})
    if action == "download_report":
        token = payload.get("sessionToken")
        test_id = payload.get("test_id")
        if not token or not test_id:
            return jsonify(error="sessionToken and test_id are required", code="invalid_payload"), 400
        # The normal results endpoint is JSON; use the dedicated download route.
        pdf = current_app.test_client().get(
            f"/api/aptitude/tests/{test_id}/download",
            headers={"Authorization": f"Bearer {token}", "X-Student-Timezone": str(payload.get("timezone") or "")},
        )
        if pdf.status_code != 200:
            return pdf
        return jsonify(content_type="application/pdf", filename="test-results.pdf", data=base64.b64encode(pdf.data).decode("ascii"))
    return _invoke_internal(action, payload)

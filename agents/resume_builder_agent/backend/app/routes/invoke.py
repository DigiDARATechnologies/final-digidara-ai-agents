"""Strategy F adapter which re-enters existing request-context routes in-process."""
from __future__ import annotations

import json
import os
from io import BytesIO
from urllib.parse import urlencode

from flask import Blueprint, Response, current_app, jsonify, request

from app.extensions import db
from app.models import User
from app.routes.resumes import USER_ID_PATTERN
from app.security import dev_header_allowed, _invoke_reentry

invoke_bp = Blueprint("invoke", __name__)

ACTION_ROUTE_MAP = {
    "create_resume": ("POST", "/api/resumes"), "get_resumes": ("GET", "/api/resumes"),
    "get_resume": ("GET", "/api/resumes/{resume_id}"), "update_resume": ("PUT", "/api/resumes/{resume_id}"),
    "delete_resume": ("DELETE", "/api/resumes/{resume_id}"), "analyze_upload": ("POST", "/api/resumes/import/analyze"),
    "create_import_draft": ("POST", "/api/resumes/import/draft"), "analyze_resume": ("POST", "/api/resumes/{resume_id}/ats"),
    "generate_resume": ("POST", "/api/ai/optimize-resume"), "suggest_resume_edit": ("POST", "/api/ai/suggest-resume-edit"), "generate_summary": ("POST", "/api/ai/generate-summary"),
    "generate_bullets": ("POST", "/api/ai/generate-bullets"), "generate_project_bullets": ("POST", "/api/ai/generate-project-bullets"),
    "improve_bullet": ("POST", "/api/ai/improve-bullet"), "suggest_skills": ("POST", "/api/ai/suggest-skills"),
    "analyze_job_description": ("POST", "/api/ai/analyze-job-description"), "generate_declaration": ("POST", "/api/ai/generate-declaration"),
    "tailor_to_job": ("POST", "/api/ai/tailor-to-jd"), "select_template": ("PUT", "/api/resumes/{resume_id}"),
    "list_templates": ("GET", "/api/templates"), "get_template": ("GET", "/api/templates/{template_id}"),
    "preview_resume": ("POST", "/api/resumes/preview"), "export_pdf": ("POST", "/api/resumes/{resume_id}/download"),
}


def _identity_headers(payload: dict) -> dict[str, str]:
    # Trust the orchestrator's own verified identity assertion first. This
    # header can only ever have been set by the orchestrator itself -- this
    # container's port is never published to the host or the internet
    # (Strategy F: gateway-only network access) -- so it is the "real
    # gateway assertion" the dev-only fallback below was always meant to
    # eventually be replaced by.
    gateway_user_id = request.headers.get("X-Digidara-User-Id")
    if isinstance(gateway_user_id, str) and USER_ID_PATTERN.fullmatch(gateway_user_id.strip()):
        return {"X-User-Id": gateway_user_id.strip()}

    # Dev-only fallback: a raw user_id supplied directly in the request
    # payload, only honored when ALLOW_DEV_USER_HEADER is explicitly
    # enabled (never in production -- see app/__init__.py's startup guard).
    user_id = payload.get("user_id")
    if not isinstance(user_id, str) or not USER_ID_PATTERN.fullmatch(user_id.strip()):
        return {}
    return {"X-User-Id": user_id.strip()} if dev_header_allowed() else {}


def _passthrough(response) -> Response:
    headers = {}
    for name in ("Content-Type", "Content-Disposition", "Retry-After"):
        if value := response.headers.get(name):
            headers[name] = value
    return Response(response.get_data(), status=response.status_code, headers=headers)


@invoke_bp.post("/invoke")
def invoke():
    if request.mimetype == "multipart/form-data":
        action = request.form.get("action")
        raw_payload = request.form.get("payload", "{}")
        try:
            payload = json.loads(raw_payload) if raw_payload else {}
        except json.JSONDecodeError:
            return jsonify({"success": False, "message": "payload must be valid JSON"}), 400
    else:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"success": False, "message": "A JSON object or multipart form is required"}), 400
        action, payload = body.get("action"), body.get("payload", {})
    if not isinstance(action, str) or not action:
        return jsonify({"success": False, "message": "action is required"}), 400
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "payload must be an object"}), 400
    if action == "health":
        return jsonify({"status": "ok", "agent_name": "resume_builder_agent", "version": "v1.0.0"})
    if os.getenv("FLASK_ENV") == "production":
        # The current gateway has no signed user-assertion channel. Refuse
        # operations rather than treating a raw payload identity as auth.
        return jsonify({"success": False, "message": "A verified production identity is required"}), 401
    if action == "ensure_profile":
        user_id = payload.get("user_id")
        name = payload.get("name")
        email = payload.get("email")
        if not isinstance(user_id, str) or not USER_ID_PATTERN.fullmatch(user_id.strip()):
            return jsonify({"success": False, "message": "A valid user_id is required"}), 400
        if not isinstance(name, str) or not name.strip() or not isinstance(email, str) or "@" not in email:
            return jsonify({"success": False, "message": "A name and email are required"}), 400
        normalized = user_id.strip()
        user = User.query.filter_by(user_id=normalized).first()
        if not user:
            user = User(user_id=normalized)
            db.session.add(user)
            db.session.commit()
        return jsonify({"success": True, "data": {"user_id": user.user_id}})
    route = ACTION_ROUTE_MAP.get(action)
    if not route:
        return jsonify({"success": False, "message": f"Unknown action: {action}"}), 404
    method, path = route
    try:
        path = path.format(**payload)
    except KeyError as exc:
        return jsonify({"success": False, "message": f"Missing route parameter: {exc.args[0]}"}), 400
    headers = _identity_headers(payload)
    _invoke_reentry.active = True
    try:
        if request.mimetype == "multipart/form-data":
            # Rebuild each upload from bytes rather than forwarding its live
            # request stream. The stream may already have been consumed while
            # Flask parsed multipart fields, which otherwise makes a valid
            # browser upload arrive at the analyzer as a zero-byte file.
            data = {key: value for key, value in request.form.items() if key not in {"action", "payload"}}
            for key, file in request.files.items():
                data[key] = (BytesIO(file.read()), file.filename, file.mimetype)
            upstream = current_app.test_client().open(path, method=method, data=data, headers=headers, content_type=None)
        else:
            query = payload.get("query") if isinstance(payload.get("query"), dict) else {}
            if query:
                path = f"{path}?{urlencode(query, doseq=True)}"
            upstream = current_app.test_client().open(path, method=method, json=payload, headers=headers)
    finally:
        _invoke_reentry.active = False
    return _passthrough(upstream)

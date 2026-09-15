"""Strategy F adapter: POST /api/invoke, re-entering this app's own
/api/jobs/* routes in-process via current_app.test_client() — the same
shape agents/resume_builder_agent/backend/app/routes/invoke.py uses,
chosen because routes.py's handlers already read `request`/`g` directly
rather than exposing separate payload-taking functions (see
STRATEGY_F.md's dispatcher-shape guidance).

Identity is simpler and stronger here than the resume_builder precedent:
the orchestrator's gateway (agents/orchestrator/app/gateway/routes.py)
already verifies the platform login JWT for every non-health call and
forwards a server-derived `X-Digidara-User-Id` header (plus
`X-Digidara-Is-Admin` once the orchestrator's `is_admin` flag ships) — this
module only ever re-attaches headers the gateway itself set, never
anything read out of the JSON payload, so there is no raw-browser-identity
trust decision to gate behind an env flag the way resume_builder's
ALLOW_DEV_USER_HEADER does.
"""
from __future__ import annotations

import json
from urllib.parse import urlencode

from flask import Blueprint, Response, current_app, jsonify, request

from .db import get_db

invoke_bp = Blueprint("job_agent_invoke", __name__)

ACTION_ROUTE_MAP = {
    "get_profile": ("GET", "/api/jobs/me/profile"),
    "update_profile": ("PUT", "/api/jobs/me/profile"),
    "get_categories": ("GET", "/api/jobs/me/categories"),
    "get_feed": ("GET", "/api/jobs/me/feed"),
    "get_saved_jobs": ("GET", "/api/jobs/me/saved"),
    "get_hidden_jobs": ("GET", "/api/jobs/me/hidden"),
    "job_action": ("PUT", "/api/jobs/me/jobs/{job_id}/action"),
    "get_applications": ("GET", "/api/jobs/me/applications"),
    "export_user_data": ("GET", "/api/jobs/me/data"),
    "delete_user_data": ("DELETE", "/api/jobs/me/data"),

    "admin_list_users": ("GET", "/api/jobs/admin/users"),
    "admin_update_plan": ("PUT", "/api/jobs/admin/users/{user_id}/plan"),
    "admin_list_sources": ("GET", "/api/jobs/admin/sources"),
    "admin_get_automation": ("GET", "/api/jobs/admin/automation"),
    "admin_update_automation": ("PUT", "/api/jobs/admin/automation"),
    "admin_create_source": ("POST", "/api/jobs/admin/sources"),
    "admin_update_source_status": ("PUT", "/api/jobs/admin/sources/{source_id}/status"),
    "admin_run_source": ("POST", "/api/jobs/admin/sources/{source_id}/run"),
    "admin_list_runs": ("GET", "/api/jobs/admin/runs"),
    "admin_list_jobs": ("GET", "/api/jobs/admin/jobs"),
    "admin_create_job": ("POST", "/api/jobs/admin/jobs"),
    "admin_update_job_status": ("PUT", "/api/jobs/admin/jobs/{job_id}/status"),
    "admin_bulk_update_job_status": ("PUT", "/api/jobs/admin/jobs/bulk-status"),
    "admin_list_categories": ("GET", "/api/jobs/admin/categories"),
    "admin_greenhouse_companies": ("GET", "/api/jobs/admin/providers/greenhouse/companies"),
    "admin_greenhouse_summary": ("GET", "/api/jobs/admin/providers/greenhouse/summary"),
    "admin_greenhouse_pending_companies": ("GET", "/api/jobs/admin/providers/greenhouse/pending-companies"),
    "admin_greenhouse_revalidate": ("POST", "/api/jobs/admin/providers/greenhouse/sources/{source_id}/revalidate"),
    "admin_greenhouse_sync": ("POST", "/api/jobs/admin/providers/greenhouse/sync"),
    "admin_greenhouse_run": ("POST", "/api/jobs/admin/providers/greenhouse/run"),
    "admin_apify_status": ("GET", "/api/jobs/admin/providers/apify/status"),
    "admin_apify_actors": ("GET", "/api/jobs/admin/providers/apify/actors"),
    "admin_apify_run": ("POST", "/api/jobs/admin/providers/apify/run"),
    "admin_tn_coverage": ("GET", "/api/jobs/admin/tn-coverage"),
}

# Path/query parameter names ACTION_ROUTE_MAP templates pull out of the
# payload rather than passing through as the JSON body.
_PATH_PARAMS = {"job_id", "source_id", "user_id"}
_QUERY_KEYS = {"q", "work_mode", "category", "location", "saved", "status", "published_at", "limit", "offset"}


def _identity_headers() -> dict[str, str]:
    """Re-attach only what the gateway itself verified and set — see module docstring."""
    headers = {}
    if user_id := request.headers.get("X-Digidara-User-Id"):
        headers["X-Digidara-User-Id"] = user_id
    if is_admin := request.headers.get("X-Digidara-Is-Admin"):
        headers["X-Digidara-Is-Admin"] = is_admin
    return headers


def _passthrough(response) -> Response:
    return Response(response.get_data(), status=response.status_code, headers={"Content-Type": "application/json"})


@invoke_bp.post("/api/invoke")
def invoke():
    is_multipart = request.mimetype == "multipart/form-data"
    if is_multipart:
        action = request.form.get("action")
        raw_payload = request.form.get("payload", "{}")
        try:
            payload = json.loads(raw_payload) if raw_payload else {}
        except json.JSONDecodeError:
            return jsonify({"error": "payload must be valid JSON"}), 400
    else:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "A JSON object body is required"}), 400
        action = body.get("action")
        payload = body.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    if not isinstance(action, str) or not action:
        return jsonify({"error": "action is required"}), 400

    if action == "health":
        return jsonify({"status": "ok", "agent_name": "job_agent", "version": "v1.0.0"})

    identity_headers = _identity_headers()
    user_id = identity_headers.get("X-Digidara-User-Id")
    if not user_id:
        return jsonify({"error": "Authentication required"}), 401

    if action == "upload_resume":
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "A resume file is required"}), 400
        upstream = current_app.test_client().open(
            "/api/jobs/me/resume",
            method="POST",
            data={"file": (file.stream, file.filename, file.mimetype)},
            headers=identity_headers,
            content_type=None,
        )
        return _passthrough(upstream)

    if action == "ensure_profile":
        db = get_db()
        cursor = db.cursor()
        try:
            cursor.execute("INSERT IGNORE INTO user_job_profiles (user_id) VALUES (%s)", (user_id,))
            db.commit()
            cursor.execute(
                "SELECT profile_completed, plan_tier FROM user_job_profiles WHERE user_id=%s", (user_id,)
            )
            row = cursor.fetchone()
        finally:
            cursor.close()
            db.close()
        return jsonify({
            "user_id": user_id,
            "profile_completed": bool(row[0]) if row else False,
            "plan_tier": row[1] if row else "free",
        })

    route = ACTION_ROUTE_MAP.get(action)
    if not route:
        return jsonify({"error": f"Unknown action: {action}"}), 404
    method, path_template = route

    path_kwargs = {key: payload[key] for key in _PATH_PARAMS if key in payload}
    try:
        path = path_template.format(**path_kwargs)
    except KeyError as exc:
        return jsonify({"error": f"Missing route parameter: {exc.args[0]}"}), 400

    if method == "GET":
        # Query-key extraction only makes sense for GET filters — some key
        # names (e.g. "status") are reused as a PUT body field elsewhere
        # (admin_update_job_status), so this must never run for non-GET
        # methods or it silently strips that field out of the JSON body.
        query = {key: payload[key] for key in _QUERY_KEYS if key in payload}
        if query:
            path = f"{path}?{urlencode(query, doseq=True)}"
        upstream = current_app.test_client().open(path, method=method, headers=identity_headers)
    else:
        body_payload = {k: v for k, v in payload.items() if k not in _PATH_PARAMS}
        upstream = current_app.test_client().open(path, method=method, json=body_payload, headers=identity_headers)
    return _passthrough(upstream)

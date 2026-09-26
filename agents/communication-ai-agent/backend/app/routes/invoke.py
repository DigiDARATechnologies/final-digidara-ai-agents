"""Common Strategy F contract (`POST /api/invoke`) used by the
registry-resolved orchestrator gateway.

The orchestrator gateway forwards only `Content-Type` + the raw request body
— it never signs anything and never forwards cookies or an `Authorization`
header, which is what every *existing* route here relies on
(`flask_jwt_extended`'s `@jwt_required()` reads the JWT from that header).

Rather than hand-porting ~45 routes across 8 blueprints (dashboard, daily
challenges, history, practice, pronunciation, speaking, writing, profile)
into a parallel payload-taking map, this dispatcher re-enters the app's own
routes unmodified through an in-process test client
(`current_app.test_client()`), using a static `{action: (method, path)}`
map. Every protected action carries an `authToken` — the JWT issued by
`bridge_identity` — inside the JSON `payload`; the dispatcher attaches it as
a normal `Authorization: Bearer` header on the re-entered request, so
`@jwt_required()` sees exactly what it would from a real browser call.

`bridge_identity` is this agent's identity-bridge action (see
`agents/communication-ai-agent/INTEGRATION.md`): it turns DigiDARA's
dev-mode login (name/email) into a `users` row and a real JWT, without going
through `/api/auth/register` or `/api/auth/login` — both require a password
DigiDARA's dev-mode login never collects.
"""

import re
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import User

invoke_bp = Blueprint("invoke", __name__)

# action -> (http_method, path_template). `{name}` segments are popped from
# the JSON payload to build the path; everything left in the payload after
# that (and after `authToken`) is forwarded as the query string (GET) or the
# JSON body (POST/PUT/DELETE) of the re-entered request.
ACTION_MAP = {
    "dashboard": ("GET", "/api/dashboard"),
    "daily_challenge_today": ("GET", "/api/daily-challenges/today"),
    "history_list": ("GET", "/api/history"),
    "history_detail": ("GET", "/api/history/{session_id}"),
    "history_speaking_detail": ("GET", "/api/history/speaking/{session_id}"),
    "history_writing_detail": ("GET", "/api/history/writing/{session_id}"),
    "history_pronunciation_detail": ("GET", "/api/history/pronunciation/{attempt_id}"),
    "practice_generate_topic": ("POST", "/api/practice/generate-topic"),
    "practice_generate_topics": ("POST", "/api/practice/generate-topics"),
    "profile_get": ("GET", "/api/profile"),
    "profile_update": ("PUT", "/api/profile"),
    "writing_topics": ("GET", "/api/writing/topics"),
    "writing_daily": ("GET", "/api/writing/daily"),
    "writing_daily_status": ("GET", "/api/writing/daily-challenge-status"),
    "writing_start": ("POST", "/api/writing/start"),
    "writing_chat": ("POST", "/api/writing/chat"),
    "writing_respond": ("POST", "/api/writing/respond"),
    "writing_end": ("POST", "/api/writing/end"),
    "writing_active": ("GET", "/api/writing/active"),
    "writing_session": ("GET", "/api/writing/session/{session_id}"),
    "writing_progress": ("GET", "/api/writing/progress"),
    "writing_report_pdf": ("GET", "/api/writing/report/{session_id}/pdf"),
    "writing_insights": ("GET", "/api/writing/insights"),
    "writing_hint": ("POST", "/api/writing/hint"),
    "writing_tone": ("POST", "/api/writing/tone"),
    "writing_rewrite_generate": ("POST", "/api/writing/rewrite/generate"),
    "writing_rewrite_evaluate": ("POST", "/api/writing/rewrite/evaluate"),
    "writing_draft_save": ("PUT", "/api/writing/draft"),
    "writing_draft_delete": ("DELETE", "/api/writing/draft"),
    "speaking_topics": ("GET", "/api/speaking/topics"),
    "speaking_generated_topics": ("GET", "/api/speaking/generated-topics"),
    "speaking_daily": ("GET", "/api/speaking/daily"),
    "speaking_daily_status": ("GET", "/api/speaking/daily-challenge-status"),
    "speaking_start": ("POST", "/api/speaking/start"),
    "speaking_respond": ("POST", "/api/speaking/respond"),
    "speaking_end": ("POST", "/api/speaking/end"),
    "speaking_active": ("GET", "/api/speaking/active"),
    "speaking_session": ("GET", "/api/speaking/session/{session_id}"),
    "speaking_progress": ("GET", "/api/speaking/progress"),
    "speaking_report_pdf": ("GET", "/api/speaking/report/{session_id}/pdf"),
    "pronunciation_item": ("GET", "/api/pronunciation/item"),
    "pronunciation_generate": ("POST", "/api/pronunciation/generate"),
    "pronunciation_daily_challenge": ("GET", "/api/pronunciation/daily-challenge"),
    "pronunciation_daily_status": ("GET", "/api/pronunciation/daily-challenge-status"),
    "pronunciation_start_attempt": ("POST", "/api/pronunciation/start"),
    "pronunciation_session_start": ("POST", "/api/pronunciation/session/start"),
    "pronunciation_session_get": ("GET", "/api/pronunciation/session/{session_id}"),
    "pronunciation_submit": ("POST", "/api/pronunciation/submit"),
    "pronunciation_session_end": ("POST", "/api/pronunciation/session/end"),
    "pronunciation_history": ("GET", "/api/pronunciation/history"),
    "pronunciation_insights": ("GET", "/api/pronunciation/insights"),
    "pronunciation_progress": ("GET", "/api/pronunciation/progress"),
    "pronunciation_streak": ("GET", "/api/pronunciation/streak"),
}

_PATH_PARAM = re.compile(r"{(\w+)}")


def _error(message, error_code, status=400):
    return jsonify({"message": message, "error_code": error_code}), status


def _bridge_identity(payload):
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    if not name or not email:
        return _error("name and email are required.", "invalid_parameter")

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email)
        # Unusable password: this identity is only ever reached through the
        # bridge (a real JWT is minted below), never through /api/auth/login.
        user.set_password(f"digidara-bridge:{uuid4().hex}")
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            # Concurrent bridge calls for a brand-new email (React strict
            # mode / a retried request) can race to create the same row.
            db.session.rollback()
            user = User.query.filter_by(email=email).first()
            if not user:
                raise
    elif name and user.name != name:
        user.name = name
        db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "authToken": token})


def _stringify(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _forward(action, payload):
    method, path_template = ACTION_MAP[action]
    remaining = dict(payload)

    path_params = {}
    for name in _PATH_PARAM.findall(path_template):
        if name not in remaining:
            return _error(f"{name} is required.", "invalid_parameter")
        path_params[name] = remaining.pop(name)
    path = path_template.format(**path_params)

    token = remaining.pop("authToken", None)
    if not token:
        return _error("Authentication is required.", "unauthenticated", 401)

    kwargs = {"headers": {"Authorization": f"Bearer {token}"}}
    if method == "GET":
        kwargs["query_string"] = {k: _stringify(v) for k, v in remaining.items() if v is not None}
    else:
        kwargs["json"] = remaining

    upstream = current_app.test_client().open(path, method=method, **kwargs)
    return current_app.response_class(upstream.data, status=upstream.status_code, content_type=upstream.content_type)


@invoke_bp.post("/api/invoke")
def invoke():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _error("A JSON request body is required.", "invalid_json")
    action = body.get("action")
    payload = body.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    if action == "health":
        return jsonify({"status": "ok", "agent_name": "communication_agent"})
    if action == "bridge_identity":
        return _bridge_identity(payload)
    if action == "usage_summary":
        # Scoped to the verified DigiDARA identity the orchestrator gateway
        # forwards via X-DigiDARA-User-Id — no session required, matching
        # capstone_project_agent/codeforge_agent's own usage_summary actions.
        from ..services.groq_usage import get_usage_summary
        return jsonify(get_usage_summary(request.headers.get("X-DigiDARA-User-Id")))
    if action not in ACTION_MAP:
        return _error(f"Unknown action: {action!r}", "unknown_action")
    return _forward(action, payload)

from flask import Blueprint, jsonify, session

from app.security import ensure_browser_session


session_bp = Blueprint("session_api", __name__)


@session_bp.get("/session")
def session_info():
    user_id, csrf_token = ensure_browser_session()
    return jsonify(
        {
            "success": True,
            "data": {
                "userId": user_id,
                "csrfToken": csrf_token,
                "authMode": "secure-guest-session",
            },
        }
    )


@session_bp.delete("/session")
def clear_session():
    session.clear()
    return jsonify({"success": True, "message": "Session cleared"})

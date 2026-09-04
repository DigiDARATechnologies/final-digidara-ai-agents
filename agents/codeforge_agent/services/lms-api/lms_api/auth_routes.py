import re

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_service, require_student
from .errors import ApiError


accounts = Blueprint("accounts", __name__, url_prefix="/api/auth")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def repo():
    return current_app.extensions["repository"]


@accounts.post("/register")
@require_service
def register():
    payload = _json_body()
    email = _email(payload.get("email"))
    password = _password(payload.get("password"))
    display_name = _display_name(payload.get("displayName"))
    student, token, expires_at = repo().register_account(email, password, display_name)
    return jsonify({"student": student, "sessionToken": token, "expiresAt": expires_at}), 201


@accounts.post("/login")
@require_service
def login():
    payload = _json_body()
    email = _email(payload.get("email"))
    password = _password(payload.get("password"), enforce_strength=False)
    student, token, expires_at = repo().login_account(email, password)
    return jsonify({"student": student, "sessionToken": token, "expiresAt": expires_at})


@accounts.get("/session")
@require_student
def session():
    return jsonify({"student": g.student})


@accounts.post("/logout")
@require_student
def logout():
    repo().revoke_session(g.session_token)
    return jsonify({"loggedOut": True})


def _json_body():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ApiError("A JSON request body is required.", 400, "invalid_json")
    return payload


def _email(value):
    email = str(value or "").strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ApiError("Enter a valid email address.", 400, "invalid_email")
    return email


def _password(value, enforce_strength=True):
    password = str(value or "")
    if len(password) > 128 or len(password) < (8 if enforce_strength else 1):
        raise ApiError("Password must contain 8 to 128 characters.", 400, "invalid_password")
    return password


def _display_name(value):
    display_name = str(value or "").strip()
    if not 2 <= len(display_name) <= 120:
        raise ApiError("Display name must contain 2 to 120 characters.", 400, "invalid_display_name")
    return display_name

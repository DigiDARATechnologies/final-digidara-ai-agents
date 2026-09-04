import hashlib
import hmac
import time
from functools import wraps

from flask import current_app, g, request

from .errors import ApiError


def require_service(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_app.config["CODING_PRACTICE_ENABLED"]:
            raise ApiError("Coding Practice is currently unavailable.", 404, "feature_disabled")
        identity = _verify_service_request()
        repository = current_app.extensions["repository"]
        if not repository.claim_request(identity["request_id"], identity["timestamp"]):
            raise ApiError("This request has already been processed.", 401, "replayed_request")
        g.session_token = identity["session_token"]
        return view(*args, **kwargs)

    return wrapped


def require_student(view):
    @require_service
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.session_token:
            raise ApiError("Authentication is required.", 401, "unauthenticated")
        student = current_app.extensions["repository"].student_for_session(g.session_token)
        if not student:
            raise ApiError("Your session has expired. Please sign in again.", 401, "invalid_session")
        if not student["is_active"]:
            raise ApiError("This student account is inactive.", 403, "inactive_student")
        g.student = student
        return view(*args, **kwargs)

    return wrapped


def _verify_service_request():
    timestamp_text = request.headers.get("X-CodeForge-Timestamp", "")
    request_id = request.headers.get("X-CodeForge-Request-Id", "").strip()
    signature = request.headers.get("X-CodeForge-Signature", "").strip()
    session_token = request.headers.get("X-CodeForge-Session", "").strip()
    if not all((timestamp_text, request_id, signature)):
        raise ApiError("Authentication is required.", 401, "unauthenticated")
    try:
        timestamp = int(timestamp_text)
    except ValueError as exc:
        raise ApiError("Authentication is invalid.", 401, "invalid_signature") from exc
    if abs(int(time.time()) - timestamp) > current_app.config["SIGNATURE_MAX_AGE_SECONDS"]:
        raise ApiError("Authentication has expired.", 401, "expired_signature")

    body_hash = hashlib.sha256(request.get_data(cache=True)).hexdigest()
    session_hash = hashlib.sha256(session_token.encode()).hexdigest() if session_token else ""
    canonical = "\n".join((timestamp_text, request_id, request.method.upper(), request.path, body_hash, session_hash))
    expected = hmac.new(
        current_app.config["LMS_API_SHARED_SECRET"].encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ApiError("Authentication is invalid.", 401, "invalid_signature")
    return {"timestamp": timestamp, "request_id": request_id, "session_token": session_token}

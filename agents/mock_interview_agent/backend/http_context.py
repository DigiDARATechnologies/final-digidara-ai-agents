"""Shared request correlation, structured logging, and error handlers."""

import logging
import re
from time import perf_counter
from uuid import uuid4

from flask import g, jsonify, request
from werkzeug.exceptions import HTTPException

from structured_logging import log_event
from validation import ValidationError


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def set_log_context(*, student_id=None, interview_id=None):
    if student_id is not None:
        g.student_id = student_id
    if interview_id is not None:
        g.interview_id = interview_id


def log(level, event, message, *, exc_info=False, **fields):
    from flask import current_app

    log_event(
        current_app.logger,
        level,
        event,
        message,
        exc_info=exc_info,
        **fields,
    )


def register_http_context(app):
    @app.before_request
    def assign_request_context():
        incoming_request_id = request.headers.get("X-Request-ID", "").strip()
        g.request_id = (
            incoming_request_id
            if REQUEST_ID_PATTERN.fullmatch(incoming_request_id)
            else uuid4().hex
        )
        g.request_started_at = perf_counter()
        view_args = request.view_args or {}
        g.student_id = view_args.get("student_id")
        g.interview_id = view_args.get("interview_id")

    @app.after_request
    def attach_request_id_and_log(response):
        response.headers["X-Request-ID"] = g.request_id
        log(
            logging.INFO,
            "request_completed",
            "HTTP request completed",
            status_code=response.status_code,
            method=request.method,
            path=request.path,
            duration_ms=round(
                (perf_counter() - g.request_started_at) * 1000,
                2,
            ),
        )
        return response


def register_error_handlers(app):
    @app.errorhandler(ValidationError)
    def handle_validation_error(exc):
        return jsonify({"error": str(exc)}), 400

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        return jsonify({"error": exc.description}), exc.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        log(
            logging.ERROR,
            "unhandled_api_error",
            "Unhandled API error",
            exc_info=True,
        )
        return jsonify({"error": "An unexpected server error occurred."}), 500

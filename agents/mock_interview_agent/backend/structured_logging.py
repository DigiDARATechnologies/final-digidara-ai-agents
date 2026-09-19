"""Machine-parseable JSON logging shared by the Flask application."""

import json
import logging
import os
from datetime import datetime, timezone

from flask import g, has_request_context


class JsonLogFormatter(logging.Formatter):
    def format(self, record):
        request_context = has_request_context()
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "request_id": getattr(record, "request_id", None)
            or (getattr(g, "request_id", None) if request_context else None),
            "student_id": getattr(record, "student_id", None)
            or (getattr(g, "student_id", None) if request_context else None),
            "interview_id": getattr(record, "interview_id", None)
            or (getattr(g, "interview_id", None) if request_context else None),
            "event": getattr(record, "event", record.name),
            "message": record.getMessage(),
        }
        for field in (
            "question_order",
            "status_code",
            "method",
            "path",
            "duration_ms",
            "old_interview_id",
            "file_name",
            "elapsed_seconds",
            "total_seconds",
            "skill_inference_seconds",
            "question_generation_seconds",
            "db_write_seconds",
            "background_schedule_seconds",
            "role_subjects_resolved_seconds",
            "other_seconds",
            "question_number",
            "skill_area",
            "collision_retry_occurred",
            "attempts",
            "cache_source",
            "model_name",
            "prompt_tokens",
            "completion_tokens",
        ):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_root_structured_logging():
    """Route process logs through one JSON formatter."""
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def configure_structured_logging(app):
    """Configure root JSON logging and attach the Flask logger to it."""
    configure_root_structured_logging()
    level = logging.getLogger().level

    app.logger.handlers.clear()
    app.logger.setLevel(level)
    app.logger.propagate = True


def log_event(logger, level, event, message, *, exc_info=False, **fields):
    """Emit a structured event without accepting request bodies or credentials."""
    allowed_fields = {
        key: value
        for key, value in fields.items()
        if key in {
            "request_id",
            "student_id",
            "interview_id",
            "question_order",
            "status_code",
            "method",
            "path",
            "duration_ms",
            "old_interview_id",
            "file_name",
            "elapsed_seconds",
            "total_seconds",
            "skill_inference_seconds",
            "question_generation_seconds",
            "db_write_seconds",
            "background_schedule_seconds",
            "role_subjects_resolved_seconds",
            "other_seconds",
            "question_number",
            "skill_area",
            "collision_retry_occurred",
            "attempts",
            "cache_source",
            "model_name",
            "prompt_tokens",
            "completion_tokens",
        }
    }
    logger.log(
        level,
        message,
        extra={"event": event, **allowed_fields},
        exc_info=exc_info,
    )

"""Flask application factory and shared HTTP configuration."""

import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS

from http_context import register_error_handlers, register_http_context
from routes import register_blueprints
from settings import ALLOWED_ORIGINS, MAX_AUDIO_UPLOAD_BYTES
from structured_logging import configure_structured_logging


def create_app():
    # Validate the AI configuration before routes can receive real requests.
    from ai.chat_client import validate_configured_models

    validate_configured_models()

    # gunicorn boots multiple workers (-w 4) without --preload, so every
    # worker runs this schema bootstrap independently -- two workers racing
    # to create the same table/apply the same migration file raise a
    # duplicate-object error here. It only takes one worker to succeed, so
    # log and keep booting instead of crashing every worker's startup over
    # a race that already resolved itself (mirrors capstone's init_db()
    # startup, agents/project_AI_Agent/app/api/main.py).
    import migrate as _migrate

    try:
        _migrate.main()
    except Exception:
        logging.getLogger("mock_interview.startup").exception("Database schema bootstrap failed")

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_AUDIO_UPLOAD_BYTES
    CORS(
        app,
        resources={r"/api/*": {"origins": ALLOWED_ORIGINS}},
        expose_headers=["X-Request-ID"],
    )
    configure_structured_logging(app)
    register_http_context(app)
    register_error_handlers(app)
    register_blueprints(app)

    @app.get("/health")
    def health():
        return jsonify(status="ok", agent_name="mock_interview_agent")

    return app


app = create_app()

from integration.registry_client import start as _start_registry  # noqa: E402

_start_registry()


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "false").lower()
        in {"1", "true", "yes", "on"},
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", "5000")),
    )

import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter.errors import RateLimitExceeded
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from .config import Config, PLACEHOLDER_SECRETS
from .extensions import db, limiter
from .routes.auth import auth_bp
from .routes.dashboard import dashboard_bp
from .routes.daily_challenges import daily_challenges_bp
from .routes.history import history_bp
from .routes.invoke import invoke_bp
from .routes.practice import practice_bp
from .routes.pronunciation import pronunciation_bp
from .routes.profile import profile_bp
from .routes.speaking import speaking_bp
from .routes.writing import writing_bp


def _configure_terminal_logging(app):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    app.logger.setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _ensure_result_schema():
    db.create_all()
    inspector = inspect(db.engine)
    planned = {
        "speaking_sessions": {
            "strengths_json": "ADD COLUMN strengths_json TEXT NULL AFTER summary_feedback",
            "weaknesses_json": "ADD COLUMN weaknesses_json TEXT NULL AFTER strengths_json",
            "common_mistakes_json": "ADD COLUMN common_mistakes_json TEXT NULL AFTER weaknesses_json",
            "recommendation": "ADD COLUMN recommendation TEXT NULL AFTER common_mistakes_json",
            "next_practice_suggestion": "ADD COLUMN next_practice_suggestion TEXT NULL AFTER recommendation",
        },
        "writing_sessions": {
            "strengths_json": "ADD COLUMN strengths_json TEXT NULL AFTER summary_feedback",
            "weaknesses_json": "ADD COLUMN weaknesses_json TEXT NULL AFTER strengths_json",
            "common_mistakes_json": "ADD COLUMN common_mistakes_json TEXT NULL AFTER weaknesses_json",
            "recommendation": "ADD COLUMN recommendation TEXT NULL AFTER common_mistakes_json",
            "next_practice_suggestion": "ADD COLUMN next_practice_suggestion TEXT NULL AFTER recommendation",
        },
        "writing_turns": {
            "overall_score": "ADD COLUMN overall_score FLOAT NULL AFTER knowledge_score",
            "corrected_answer": "ADD COLUMN corrected_answer TEXT NULL AFTER user_response",
            "better_natural_answer": "ADD COLUMN better_natural_answer TEXT NULL AFTER corrected_answer",
            "feedback_json": "ADD COLUMN feedback_json TEXT NULL AFTER better_natural_answer",
            "weak_area_tags": "ADD COLUMN weak_area_tags TEXT NULL AFTER feedback_json",
            "completed_at": "ADD COLUMN completed_at DATETIME NULL AFTER weak_area_tags",
        },
        "pronunciation_items": {
            "metadata_json": "ADD COLUMN metadata_json TEXT NULL AFTER source",
        },
        "pronunciation_attempts": {
            "session_id": "ADD COLUMN session_id INTEGER NULL AFTER item_id",
            "turn_number": "ADD COLUMN turn_number INTEGER NULL AFTER session_id",
            "sound_tags_json": "ADD COLUMN sound_tags_json TEXT NULL AFTER status",
            "effective_difficulty": "ADD COLUMN effective_difficulty VARCHAR(20) NULL AFTER sound_tags_json",
        },
        "users": {
            "streak_count": "ADD COLUMN streak_count INTEGER NOT NULL DEFAULT 0",
            "last_completed_date": "ADD COLUMN last_completed_date DATE NULL",
            "phone": "ADD COLUMN phone VARCHAR(30) NULL",
            "course_name": "ADD COLUMN course_name VARCHAR(120) NULL",
            "photo_url": "ADD COLUMN photo_url VARCHAR(300) NULL",
            "email_verified": "ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE",
            "total_xp": "ADD COLUMN total_xp INTEGER NOT NULL DEFAULT 0",
        },
    }
    for table, alters in planned.items():
        if table not in inspector.get_table_names():
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        for column, ddl in alters.items():
            if column not in columns:
                db.session.execute(text(f"ALTER TABLE {table} {ddl}"))
    db.session.commit()
    
    # Run route specific schema check as well
    from .routes.pronunciation import _ensure_pronunciation_schema
    _ensure_pronunciation_schema()


def create_app(config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    if not app.config.get("TESTING"):
        for key in ("SECRET_KEY", "JWT_SECRET_KEY"):
            value = app.config.get(key)
            if not value or value in PLACEHOLDER_SECRETS:
                raise RuntimeError(
                    f"{key} is not set (or is still a known placeholder value). "
                    f"Generate one with `openssl rand -hex 32` and set it before starting this app."
                )

    _configure_terminal_logging(app)

    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}}, supports_credentials=True)
    db.init_app(app)
    limiter.init_app(app)
    jwt = JWTManager(app)

    @jwt.expired_token_loader
    def expired_token_callback(_jwt_header, _jwt_payload):
        return jsonify({"message": "Your session has expired. Please sign in again.", "error_code": "TOKEN_EXPIRED"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(_error_string):
        return jsonify({"message": "Your session is invalid. Please sign in again.", "error_code": "TOKEN_INVALID"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(_error_string):
        return jsonify({"message": "Please sign in to use this feature.", "error_code": "TOKEN_MISSING"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(_jwt_header, _jwt_payload):
        return jsonify({"message": "Your session was signed out. Please sign in again.", "error_code": "TOKEN_REVOKED"}), 401

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(daily_challenges_bp, url_prefix="/api/daily-challenges")
    app.register_blueprint(speaking_bp, url_prefix="/api/speaking")
    app.register_blueprint(writing_bp, url_prefix="/api/writing")
    app.register_blueprint(practice_bp, url_prefix="/api/practice")
    app.register_blueprint(pronunciation_bp, url_prefix="/api/pronunciation")
    app.register_blueprint(history_bp, url_prefix="/api/history")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(invoke_bp)

    from .commands import register_commands
    register_commands(app)

    with app.app_context():
        try:
            _ensure_result_schema()
        except OperationalError:
            app.logger.exception("Database schema check failed during startup")

    if not app.config.get("TESTING"):
        from integration import registry_client
        registry_client.start()

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "communication-module-api"})

    @app.get("/api/health/db")
    def database_health():
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok", "database": "connected"})

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"message": "Resource not found"}), 404

    @app.errorhandler(500)
    def server_error(_error):
        return jsonify({"message": "Unexpected server error"}), 500

    @app.errorhandler(RateLimitExceeded)
    def rate_limit_error(_error):
        return jsonify({
            "success": False,
            "message": "Too many answer submissions. Please wait a moment and try again.",
            "error_code": "RATE_LIMITED",
        }), 429

    @app.errorhandler(OperationalError)
    def database_error(_error):
        return jsonify({
            "message": "Database connection failed. Check DATABASE_URL in backend/.env and confirm MySQL is running.",
        }), 500

    return app

import os
from pathlib import Path
from urllib.parse import quote_plus

from flask import Flask, request
from flask_cors import CORS
from sqlalchemy import inspect, text
from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.errors import database_error_response
from app.extensions import db
from app.routes.ai import ai_bp
from app.routes.health import health_bp
from app.routes.invoke import invoke_bp
from app.routes.resumes import resumes_bp
from app.routes.session_api import session_bp
from app.security import verify_csrf


INSECURE_DEFAULT_SECRET_KEY = "dev-secret-key"


def env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def build_database_uri() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    db_user = os.getenv("DB_USER", "root")
    db_password = quote_plus(os.getenv("DB_PASSWORD", ""))
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "3306")
    db_name = os.getenv("DB_NAME", "ai_resume_builder")
    return (
        f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        "?charset=utf8mb4"
    )


def ensure_schema_updates(app):
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            if not inspector.has_table("education"):
                return

            columns = {column["name"] for column in inspector.get_columns("education")}
            if "cgpa" not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE education ADD COLUMN cgpa VARCHAR(20)"))

            project_columns = {column["name"] for column in inspector.get_columns("projects")}
            if "ai_generated_bullets" not in project_columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE projects ADD COLUMN ai_generated_bullets JSON"))

            experience_columns = {column["name"] for column in inspector.get_columns("experience")}
            if "is_current" not in experience_columns:
                with db.engine.begin() as connection:
                    connection.execute(text("ALTER TABLE experience ADD COLUMN is_current BOOLEAN NOT NULL DEFAULT FALSE"))

            resume_columns = {column["name"] for column in inspector.get_columns("resumes")}
            resume_updates = {
                "target_role": "ALTER TABLE resumes ADD COLUMN target_role VARCHAR(255)",
                "profile_photo": "ALTER TABLE resumes ADD COLUMN profile_photo VARCHAR(500)",
                "experience_level": "ALTER TABLE resumes ADD COLUMN experience_level VARCHAR(20)",
                "status": "ALTER TABLE resumes ADD COLUMN status VARCHAR(30) NOT NULL DEFAULT 'draft'",
                "last_downloaded_at": "ALTER TABLE resumes ADD COLUMN last_downloaded_at DATETIME",
                "declaration": "ALTER TABLE resumes ADD COLUMN declaration TEXT",
                "ats_score": "ALTER TABLE resumes ADD COLUMN ats_score INT",
                "job_match_score": "ALTER TABLE resumes ADD COLUMN job_match_score INT",
                "download_count": "ALTER TABLE resumes ADD COLUMN download_count INT NOT NULL DEFAULT 0",
                "last_analyzed_at": "ALTER TABLE resumes ADD COLUMN last_analyzed_at DATETIME",
            }
            with db.engine.begin() as connection:
                for column_name, statement in resume_updates.items():
                    if column_name not in resume_columns:
                        connection.execute(text(statement))
                if not inspector.has_table("ats_analyses"):
                    from app.models import AtsAnalysis
                    AtsAnalysis.__table__.create(bind=connection)
                if not inspector.has_table("achievements"):
                    from app.models import Achievement
                    Achievement.__table__.create(bind=connection)
                if not inspector.has_table("publications"):
                    from app.models import Publication
                    Publication.__table__.create(bind=connection)
                from app.template_catalog import LEGACY_TEMPLATE_ALIASES
                legacy_template_updates = LEGACY_TEMPLATE_ALIASES
                for old_value, new_value in legacy_template_updates.items():
                    connection.execute(
                        text(
                            "UPDATE resumes "
                            "SET template_choice = :new_value "
                            "WHERE template_choice = :old_value"
                        ),
                        {"old_value": old_value, "new_value": new_value},
                    )
        except OperationalError:
            if os.getenv("FLASK_ENV") == "production":
                raise
            app.logger.warning(
                "Database is unavailable during startup; continuing so health checks remain available.",
                exc_info=True,
            )
            return


def cors_origins():
    origins = {"http://localhost:5173", "http://127.0.0.1:5173"}
    configured = os.getenv("FRONTEND_ORIGINS") or os.getenv("FRONTEND_ORIGIN")
    if configured:
        origins.update(origin.strip() for origin in configured.split(",") if origin.strip())
    return sorted(origins)


def create_app(config_object: str | None = None) -> Flask:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

    app = Flask(__name__)
    if config_object:
        app.config.from_object(config_object)
    from integration.agent_signing import install as install_gateway_signing
    install_gateway_signing(app, "resume_builder_agent")

    is_production = os.getenv("FLASK_ENV") == "production"
    secret_key = app.config.get("SECRET_KEY") or os.getenv("SECRET_KEY")
    insecure_defaults_allowed = app.testing or os.getenv("FLASK_ENV") == "development"
    if not secret_key:
        if not insecure_defaults_allowed:
            raise RuntimeError(
                "SECRET_KEY must be configured outside explicit development or testing."
            )
        secret_key = INSECURE_DEFAULT_SECRET_KEY
    if secret_key == INSECURE_DEFAULT_SECRET_KEY and not insecure_defaults_allowed:
        raise RuntimeError(
            "SECRET_KEY must not use the insecure development default outside explicit "
            "development or testing."
        )
    app.config["SECRET_KEY"] = secret_key
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = build_database_uri()
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("MAX_CONTENT_LENGTH", 6 * 1024 * 1024)
    app.config.setdefault("MAX_FORM_MEMORY_SIZE", 6 * 1024 * 1024)
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", 60 * 60 * 24 * 30)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", is_production)
    app.config.setdefault(
        "ALLOW_DEV_USER_HEADER",
        os.getenv("ALLOW_DEV_USER_HEADER", "").lower() in {"1", "true", "yes"},
    )
    if is_production and app.config["ALLOW_DEV_USER_HEADER"]:
        raise RuntimeError("ALLOW_DEV_USER_HEADER cannot be enabled in production.")

    db.init_app(app)
    from app import models  # noqa: F401

    ensure_schema_updates(app)

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": cors_origins(),
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "X-CSRF-Token", "X-User-Id"],
                "supports_credentials": True,
            }
        },
    )

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(invoke_bp, url_prefix="/api")
    app.register_blueprint(session_bp, url_prefix="/api")
    app.register_blueprint(resumes_bp, url_prefix="/api")
    app.register_blueprint(ai_bp, url_prefix="/api")
    app.before_request(verify_csrf)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'self'",
        )
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        if is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        if request.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(exc):
        db.session.rollback()
        return database_error_response(exc)

    if os.getenv("AUTO_CREATE_TABLES", "").lower() in {"1", "true", "yes"}:
        with app.app_context():
            db.create_all()

    # Registration failure is deliberately non-fatal: standalone Resume Builder
    # remains usable while the orchestrator is restarting or unavailable.
    if not app.testing and os.getenv("STRATEGY_F_ENABLED", "true").lower() in {"1", "true", "yes", "on"}:
        from integration.registry_client import start as start_registry_client
        start_registry_client()

    return app
